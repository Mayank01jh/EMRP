"""Audit logging service — immutable chain-linked audit events."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.base import sha256_hex, new_id, utcnow
from app.models.support import AuditEvent


async def log_audit(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    actor_role: str,
    action: str,
    target_type: str,
    target_id: str,
    request_id: str,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    """
    Write a chain-linked audit event. Each event includes the hash of the
    previous audit event for the same target_id, enabling tamper detection.
    """
    # Find previous audit entry hash for this target
    prev = await db.audit_events.find_one(
        {"target_id": target_id},
        sort=[("created_at", -1)],
        projection={"current_hash": 1},
    )
    prior_hash = prev["current_hash"] if prev else None

    # Build content hash
    content = json.dumps({
        "actor_id": actor_id,
        "action": action,
        "target_id": target_id,
        "after_state": after_state,
        "timestamp": utcnow().isoformat(),
        "prior_hash": prior_hash,
    }, sort_keys=True, default=str)
    current_hash = sha256_hex(content)

    event = AuditEvent(
        id=new_id(),
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        request_id=request_id,
        before_state=before_state,
        after_state=after_state,
        prior_hash=prior_hash,
        current_hash=current_hash,
        ip_address=ip_address,
    )
    await db.audit_events.insert_one(event.model_dump(by_alias=True))
    return event
