"""Async MongoDB connection management."""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, GEOSPHERE, IndexModel

from app.core.config import get_settings

_client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    """Initialise Motor client and ensure indexes exist."""
    global _client
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)
    # verify connectivity
    await _client.admin.command('ping')
    db = _client[settings.mongo_db]
    await _ensure_indexes(db)


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        _client = None


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("Database not initialised. Call connect_db() first.")
    settings = get_settings()
    return _client[settings.mongo_db]


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create all required indexes (idempotent)."""
    # --- incidents ---
    await db.incidents.create_indexes([
        IndexModel([("idempotency_key", ASCENDING)], unique=True, sparse=True),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("created_at", ASCENDING)]),
        IndexModel([("location", GEOSPHERE)]),
    ])

    # --- ambulances ---
    await db.ambulances.create_indexes([
        IndexModel([("status", ASCENDING)]),
        IndexModel([("location.coordinates", GEOSPHERE)]),
        IndexModel([("operator_id", ASCENDING)]),
    ])

    # --- dispatch offers ---
    await db.dispatch_offers.create_indexes([
        IndexModel([("incident_id", ASCENDING), ("unit_id", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("expires_at", ASCENDING)]),
    ])

    # --- assignments ---
    await db.assignments.create_indexes([
        IndexModel([("incident_id", ASCENDING)]),
        IndexModel([("unit_id", ASCENDING)]),
        # enforce at most one active assignment per unit
        IndexModel(
            [("unit_id", ASCENDING), ("state", ASCENDING)],
            unique=True,
            partialFilterExpression={"state": "ACTIVE"},
        ),
    ])

    # --- outbox events ---
    await db.outbox_events.create_indexes([
        IndexModel([("published", ASCENDING), ("retry_count", ASCENDING)]),
        IndexModel([("aggregate_id", ASCENDING)]),
        IndexModel([("created_at", ASCENDING)]),
    ])

    # --- audit events ---
    await db.audit_events.create_indexes([
        IndexModel([("target_id", ASCENDING)]),
        IndexModel([("actor_id", ASCENDING)]),
        IndexModel([("created_at", ASCENDING)]),
    ])

    # --- hospitals ---
    await db.hospitals.create_indexes([
        IndexModel([("location", GEOSPHERE)]),
        IndexModel([("name", ASCENDING)]),
    ])
