"""
Incident Service — Phase 1: Reliable Core

Implements:
- Idempotent SOS creation with atomic Incident + OutboxEvent write
- Coordinate validation
- Status transition with FSM validation
- Audit logging on every state change
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.logging import logger
from app.models.base import new_id, utcnow, sha256_hex, GeoJSONPoint
from app.models.incident import (
    Incident, IncidentStatus, IncidentSeverity, SOSRequest, CallerInfo,
)
from app.models.support import OutboxEvent
from app.services.audit_service import log_audit
from app.services.outbox_service import enqueue_event
from app.state_machines.incident_fsm import build_status_update, InvalidTransitionError


def _compute_request_hash(caller_id: str, lat: float, lon: float) -> str:
    """
    Hash that groups duplicate SOS submissions from same caller+location
    within a 60-second bucket.
    """
    bucket = int(datetime.now(UTC).timestamp() / 60)  # 1-minute dedup window
    raw = f"{caller_id}:{lat:.4f}:{lon:.4f}:{bucket}"
    return sha256_hex(raw)


async def create_incident(
    db: AsyncIOMotorDatabase,
    *,
    caller_id: str,
    idempotency_key: str,
    request: SOSRequest,
    request_id: str,
    ip_address: str | None = None,
) -> Incident:
    """
    Idempotently create an incident.

    - If idempotency_key already exists → return the existing incident.
    - Otherwise, atomically write Incident + OutboxEvent in a replica-set transaction.
    """
    # Check idempotency
    existing = await db.incidents.find_one({"idempotency_key": idempotency_key})
    if existing:
        logger.info("Idempotent replay", idempotency_key=idempotency_key, incident_id=existing["_id"])
        return Incident(**existing)

    request_hash = _compute_request_hash(caller_id, request.latitude, request.longitude)

    # Check for near-duplicate (same request_hash) — link as duplicate
    near_dup = await db.incidents.find_one({"request_hash": request_hash, "status": {"$ne": IncidentStatus.CANCELLED}})

    location = GeoJSONPoint(coordinates=[request.longitude, request.latitude])
    incident_id = new_id()

    incident = Incident(
        id=incident_id,
        caller_id=caller_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        location=location,
        accuracy_m=request.accuracy_m,
        severity=request.severity,
        status=IncidentStatus.RECEIVED if not near_dup else IncidentStatus.DUPLICATE_LINKED,
        caller_info=request.caller_info,
        parent_incident_id=near_dup["_id"] if near_dup else None,
    )

    # Atomic transaction: insert Incident + OutboxEvent together
    async with await db.client.start_session() as session:
        async with session.start_transaction():
            await db.incidents.insert_one(incident.model_dump(by_alias=True), session=session)
            await enqueue_event(
                db,
                aggregate_id=incident_id,
                aggregate_type="Incident",
                event_type="IncidentCreated",
                payload={
                    "incident_id": incident_id,
                    "caller_id": caller_id,
                    "status": incident.status.value,
                    "severity": incident.severity.value,
                    "location": location.model_dump(),
                    "accuracy_m": request.accuracy_m,
                    "is_duplicate": near_dup is not None,
                    "parent_incident_id": incident.parent_incident_id,
                },
                session=session,
            )

    # Audit log (outside transaction — best-effort)
    await log_audit(
        db,
        actor_id=caller_id,
        actor_role="caller",
        action="CREATE_INCIDENT",
        target_type="Incident",
        target_id=incident_id,
        request_id=request_id,
        after_state={"status": incident.status.value, "severity": incident.severity.value},
        ip_address=ip_address,
    )

    logger.info("Incident created", incident_id=incident_id, status=incident.status.value, caller_id=caller_id)
    return incident


async def transition_incident(
    db: AsyncIOMotorDatabase,
    *,
    incident_id: str,
    target_status: IncidentStatus,
    actor_id: str,
    actor_role: str,
    request_id: str,
    extra_fields: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> Incident:
    """
    Apply a validated FSM transition to an incident.
    Uses optimistic concurrency (version field).
    """
    doc = await db.incidents.find_one({"_id": incident_id})
    if not doc:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    incident = Incident(**doc)
    before_status = incident.status

    status_update = build_status_update(before_status, target_status)
    if extra_fields:
        status_update.update(extra_fields)

    result = await db.incidents.find_one_and_update(
        {"_id": incident_id, "version": incident.version},
        {"$set": status_update, "$inc": {"version": 1}},
        return_document=True,
    )
    if not result:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=409, detail="Concurrent modification — retry")

    updated = Incident(**result)

    # Outbox + Audit
    async with await db.client.start_session() as session:
        async with session.start_transaction():
            await enqueue_event(
                db,
                aggregate_id=incident_id,
                aggregate_type="Incident",
                event_type=f"Incident{target_status.value.title().replace('_', '')}",
                payload={"incident_id": incident_id, "status": target_status.value},
                session=session,
            )

    await log_audit(
        db,
        actor_id=actor_id,
        actor_role=actor_role,
        action=f"TRANSITION_{before_status.value}_TO_{target_status.value}",
        target_type="Incident",
        target_id=incident_id,
        request_id=request_id,
        before_state={"status": before_status.value},
        after_state={"status": target_status.value},
        ip_address=ip_address,
    )

    logger.info(
        "Incident transitioned",
        incident_id=incident_id,
        from_status=before_status.value,
        to_status=target_status.value,
    )
    return updated


async def get_incident(db: AsyncIOMotorDatabase, incident_id: str) -> Incident | None:
    doc = await db.incidents.find_one({"_id": incident_id})
    return Incident(**doc) if doc else None
