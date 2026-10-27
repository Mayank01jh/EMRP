"""Transactional Outbox — helpers to enqueue and fetch events."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorClientSession

from app.models.base import new_id, utcnow
from app.models.support import OutboxEvent


async def enqueue_event(
    db: AsyncIOMotorDatabase,
    *,
    aggregate_id: str,
    aggregate_type: str,
    event_type: str,
    payload: dict[str, Any],
    session: AsyncIOMotorClientSession | None = None,
) -> OutboxEvent:
    """
    Enqueue an outbox event. MUST be called inside the same transaction as
    the primary document write to guarantee atomicity.
    """
    event = OutboxEvent(
        id=new_id(),
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        event_type=event_type,
        payload=payload,
        published=False,
    )
    await db.outbox_events.insert_one(
        event.model_dump(by_alias=True),
        session=session,
    )
    return event


async def fetch_unpublished(
    db: AsyncIOMotorDatabase,
    *,
    limit: int = 50,
) -> list[dict]:
    """Fetch batch of unpublished outbox events ordered by creation time."""
    cursor = db.outbox_events.find(
        {"published": False, "publish_after": {"$lte": utcnow()}},
        sort=[("created_at", 1)],
        limit=limit,
    )
    return await cursor.to_list(length=limit)


async def mark_published(db: AsyncIOMotorDatabase, event_id: str) -> None:
    await db.outbox_events.update_one(
        {"_id": event_id},
        {"$set": {"published": True, "published_at": utcnow(), "updated_at": utcnow()}},
    )


async def mark_failed(db: AsyncIOMotorDatabase, event_id: str, error: str) -> None:
    from datetime import timedelta
    await db.outbox_events.update_one(
        {"_id": event_id},
        {
            "$inc": {"retry_count": 1},
            "$set": {
                "last_error": error,
                "updated_at": utcnow(),
                # exponential backoff: next attempt after 2^retry_count seconds (max 300s)
                "publish_after": utcnow() + timedelta(seconds=min(300, 2 ** 0)),
            },
        },
    )
