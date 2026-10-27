"""
Dispatch Engine — Phase 2

Implements:
- Geo-query candidate shortlisting via $nearSphere
- Candidate ranking: road ETA + capability matching + crew qualification
- Atomic CAS ambulance leasing (AVAILABLE → OFFERED)
- Offer creation with expiry timer
- Offer acceptance / decline / expiry handling with CAS release
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.logging import logger
from app.models.ambulance import AmbulanceStatus, VehicleCapability
from app.models.base import new_id, utcnow
from app.models.dispatch import (
    AssignmentState, DispatchOffer, OfferStatus, Assignment,
)
from app.models.incident import Incident, IncidentStatus, IncidentSeverity
from app.services.audit_service import log_audit
from app.services.outbox_service import enqueue_event
from app.services.routing_service import get_road_eta_seconds
from app.state_machines.ambulance_fsm import build_ambulance_status_update


CAPABILITY_PRIORITY: dict[IncidentSeverity, list[VehicleCapability]] = {
    IncidentSeverity.CRITICAL: [VehicleCapability.ALS, VehicleCapability.VENTILATOR],
    IncidentSeverity.HIGH: [VehicleCapability.ALS, VehicleCapability.BLS],
    IncidentSeverity.MEDIUM: [VehicleCapability.BLS],
    IncidentSeverity.LOW: [VehicleCapability.BLS],
}


async def _shortlist_candidates(
    db: AsyncIOMotorDatabase,
    incident: Incident,
    already_offered: set[str],
) -> list[dict]:
    """Geo-query for nearby available ambulances."""
    settings = get_settings()
    radius_m = settings.max_dispatch_radius_km * 1000
    cursor = db.ambulances.find(
        {
            "status": AmbulanceStatus.AVAILABLE.value,
            "_id": {"$nin": list(already_offered)},
            "location": {
                "$nearSphere": {
                    "$geometry": incident.location.model_dump(),
                    "$maxDistance": radius_m,
                }
            },
        },
        limit=20,  # shortlist top 20 by distance, then rank by road ETA
    )
    return await cursor.to_list(length=20)


async def _rank_candidates(
    candidates: list[dict],
    incident: Incident,
) -> list[tuple[dict, int, float]]:
    """
    Rank candidates by: (1) required capability match, (2) road ETA.
    Returns sorted list of (unit_doc, eta_seconds, dist_km).
    """
    required_caps = set(CAPABILITY_PRIORITY.get(incident.severity, []))
    ranked: list[tuple[dict, int, float]] = []

    for unit in candidates:
        unit_caps = set(unit.get("capabilities", []))
        cap_score = len(required_caps & unit_caps)  # higher is better

        loc = unit.get("location", {}).get("coordinates", [0, 0])
        eta_s, dist_km = await get_road_eta_seconds(
            loc[1], loc[0],                      # unit lat/lon
            incident.location.latitude,
            incident.location.longitude,
        )
        ranked.append((unit, eta_s, dist_km, cap_score))

    # Sort: descending cap_score, then ascending ETA
    ranked.sort(key=lambda x: (-x[3], x[1]))
    return [(u, eta, dist) for u, eta, dist, _ in ranked]


async def dispatch_incident(
    db: AsyncIOMotorDatabase,
    incident: Incident,
    request_id: str,
) -> DispatchOffer | None:
    """
    Find the best available ambulance and atomically send a dispatch offer.
    Returns the created DispatchOffer, or None if no units available.
    """
    settings = get_settings()

    # Get already-offered units for this incident to avoid re-offering
    existing_offers_cursor = db.dispatch_offers.find(
        {"incident_id": incident.id},
        projection={"unit_id": 1},
    )
    existing_offers = await existing_offers_cursor.to_list(length=100)
    already_offered = {o["unit_id"] for o in existing_offers}

    candidates = await _shortlist_candidates(db, incident, already_offered)
    if not candidates:
        logger.warning("No available ambulances found", incident_id=incident.id)
        return None

    ranked = await _rank_candidates(candidates, incident)

    for unit, eta_s, dist_km in ranked:
        unit_id = unit["_id"]
        offer_id = new_id()
        expires_at = utcnow() + timedelta(seconds=settings.offer_expiry_seconds)

        # Determine offer number
        offer_count = await db.dispatch_offers.count_documents({"incident_id": incident.id})

        # Atomic CAS: AVAILABLE → OFFERED
        # Only succeeds if status is still AVAILABLE and version matches
        result = await db.ambulances.find_one_and_update(
            {"_id": unit_id, "status": AmbulanceStatus.AVAILABLE.value, "version": unit.get("version", 0)},
            {
                "$set": {
                    "status": AmbulanceStatus.OFFERED.value,
                    "active_incident_id": incident.id,
                    "updated_at": utcnow(),
                },
                "$inc": {"version": 1},
            },
            return_document=True,
        )
        if not result:
            # Race condition: another incident claimed this unit — try next candidate
            logger.info("CAS miss on unit, trying next", unit_id=unit_id)
            continue

        # Create DispatchOffer
        offer = DispatchOffer(
            id=offer_id,
            incident_id=incident.id,
            unit_id=unit_id,
            offer_number=offer_count + 1,
            expires_at=expires_at,
            road_eta_seconds=eta_s,
            straight_line_km=dist_km,
        )

        async with await db.client.start_session() as session:
            async with session.start_transaction():
                await db.dispatch_offers.insert_one(offer.model_dump(by_alias=True), session=session)
                # Update incident status → OFFERING + update ETA
                await db.incidents.update_one(
                    {"_id": incident.id},
                    {
                        "$set": {
                            "status": IncidentStatus.OFFERING.value,
                            "offer_round": offer_count + 1,
                            "eta_seconds": eta_s,
                            "updated_at": utcnow(),
                        },
                        "$inc": {"version": 1},
                    },
                    session=session,
                )
                await enqueue_event(
                    db,
                    aggregate_id=incident.id,
                    aggregate_type="Incident",
                    event_type="DispatchOfferSent",
                    payload={
                        "incident_id": incident.id,
                        "offer_id": offer_id,
                        "unit_id": unit_id,
                        "eta_seconds": eta_s,
                        "expires_at": expires_at.isoformat(),
                    },
                    session=session,
                )

        logger.info(
            "Dispatch offer sent",
            incident_id=incident.id,
            unit_id=unit_id,
            offer_id=offer_id,
            eta_s=eta_s,
        )
        return offer

    return None  # all candidates failed CAS


async def accept_offer(
    db: AsyncIOMotorDatabase,
    *,
    offer_id: str,
    unit_id: str,
    actor_id: str,
    request_id: str,
) -> Assignment:
    """
    Ambulance crew accepts the offer.
    CAS: offer must still be PENDING and not expired.
    """
    now = utcnow()
    offer_doc = await db.dispatch_offers.find_one({"_id": offer_id, "unit_id": unit_id})
    if not offer_doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Offer not found")

    if offer_doc["status"] != OfferStatus.PENDING.value:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=f"Offer already {offer_doc['status']}")

    if now > offer_doc["expires_at"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=410, detail="Offer has expired")

    assignment_id = new_id()
    assignment = Assignment(
        id=assignment_id,
        incident_id=offer_doc["incident_id"],
        unit_id=unit_id,
        offer_id=offer_id,
        state=AssignmentState.ACTIVE,
        accepted_at=now,
    )

    async with await db.client.start_session() as session:
        async with session.start_transaction():
            # Mark offer ACCEPTED
            await db.dispatch_offers.update_one(
                {"_id": offer_id},
                {"$set": {"status": OfferStatus.ACCEPTED.value, "responded_at": now, "updated_at": now}},
                session=session,
            )
            # Create assignment
            await db.assignments.insert_one(assignment.model_dump(by_alias=True), session=session)
            # Ambulance: OFFERED → DISPATCHED
            await db.ambulances.update_one(
                {"_id": unit_id},
                {"$set": {"status": AmbulanceStatus.DISPATCHED.value, "updated_at": now}, "$inc": {"version": 1}},
                session=session,
            )
            # Incident: OFFERING → ASSIGNED
            await db.incidents.update_one(
                {"_id": offer_doc["incident_id"]},
                {
                    "$set": {
                        "status": IncidentStatus.ASSIGNED.value,
                        "assigned_unit_id": unit_id,
                        "assigned_at": now,
                        "updated_at": now,
                    },
                    "$inc": {"version": 1},
                },
                session=session,
            )
            await enqueue_event(
                db,
                aggregate_id=offer_doc["incident_id"],
                aggregate_type="Incident",
                event_type="IncidentAssigned",
                payload={"incident_id": offer_doc["incident_id"], "unit_id": unit_id, "assignment_id": assignment_id},
                session=session,
            )

    logger.info("Offer accepted, unit dispatched", offer_id=offer_id, unit_id=unit_id, incident_id=offer_doc["incident_id"])
    return assignment


async def decline_offer(
    db: AsyncIOMotorDatabase,
    *,
    offer_id: str,
    unit_id: str,
    reason: str | None,
    request_id: str,
) -> None:
    """Ambulance crew declines offer. Release unit back to AVAILABLE."""
    now = utcnow()
    offer_doc = await db.dispatch_offers.find_one({"_id": offer_id, "unit_id": unit_id})
    if not offer_doc or offer_doc["status"] != OfferStatus.PENDING.value:
        return

    async with await db.client.start_session() as session:
        async with session.start_transaction():
            await db.dispatch_offers.update_one(
                {"_id": offer_id},
                {"$set": {"status": OfferStatus.DECLINED.value, "responded_at": now, "updated_at": now}},
                session=session,
            )
            # Release unit back to AVAILABLE
            await db.ambulances.update_one(
                {"_id": unit_id},
                {
                    "$set": {"status": AmbulanceStatus.AVAILABLE.value, "active_incident_id": None, "updated_at": now},
                    "$inc": {"version": 1},
                },
                session=session,
            )
            # Incident back to QUEUED for re-dispatch
            await db.incidents.update_one(
                {"_id": offer_doc["incident_id"]},
                {"$set": {"status": IncidentStatus.QUEUED.value, "updated_at": now}, "$inc": {"version": 1}},
                session=session,
            )

    logger.info("Offer declined, unit released", offer_id=offer_id, unit_id=unit_id, reason=reason)
