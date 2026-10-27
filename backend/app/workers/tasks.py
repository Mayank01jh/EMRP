"""
Arq Worker Tasks

Task definitions for:
1. outbox_relay     — process unpublished outbox events → dispatch via WebSocket + Redis
2. offer_sweeper    — expire stale dispatch offers, release units, re-queue incidents
3. process_dispatch — enqueue dispatch for a newly created incident
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from arq import ArqRedis

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import logger
from app.models.ambulance import AmbulanceStatus
from app.models.base import utcnow
from app.models.dispatch import OfferStatus
from app.models.incident import IncidentStatus, Incident
from app.services.dispatch_service import dispatch_incident
from app.services.outbox_service import fetch_unpublished, mark_published, mark_failed
from app.websockets.manager import ws_manager


async def process_dispatch(ctx: dict, incident_id: str) -> None:
    """
    Triggered after incident creation. Attempts to find and offer an ambulance.
    Retried by Arq if it fails.
    """
    db = get_db()
    doc = await db.incidents.find_one({"_id": incident_id})
    if not doc:
        logger.warning("Dispatch task: incident not found", incident_id=incident_id)
        return

    incident = Incident(**doc)
    if incident.status not in {IncidentStatus.RECEIVED, IncidentStatus.QUEUED}:
        logger.info("Dispatch task: incident no longer needs dispatch", incident_id=incident_id, status=incident.status.value)
        return

    # Move to QUEUED first
    await db.incidents.update_one(
        {"_id": incident_id, "status": IncidentStatus.RECEIVED.value},
        {"$set": {"status": IncidentStatus.QUEUED.value, "queued_at": utcnow(), "updated_at": utcnow()}, "$inc": {"version": 1}},
    )

    offer = await dispatch_incident(db, incident, request_id="arq-dispatch")
    if not offer:
        settings = get_settings()
        rounds_used = incident.offer_round
        if rounds_used >= settings.max_offer_rounds:
            await db.incidents.update_one(
                {"_id": incident_id},
                {"$set": {"status": IncidentStatus.NO_RESOURCE.value, "updated_at": utcnow()}, "$inc": {"version": 1}},
            )
            logger.error("Incident escalated to NO_RESOURCE", incident_id=incident_id)
        else:
            # Schedule retry in 30 seconds
            logger.warning("No unit available, will retry dispatch", incident_id=incident_id)
            raise Exception("No available unit — retry scheduled")


async def outbox_relay(ctx: dict) -> None:
    """
    Periodic task: relay unpublished outbox events.
    Pushes events to Redis pub/sub for cross-instance fan-out.
    """
    db = get_db()
    redis: ArqRedis = ctx["redis"]
    events = await fetch_unpublished(db, limit=50)
    if not events:
        return

    logger.info("Outbox relay processing", count=len(events))
    for event in events:
        try:
            # Publish to Redis channel
            channel = f"emrp:events:{event['aggregate_type'].lower()}"
            await redis.publish(channel, json.dumps({
                "event_type": event["event_type"],
                "payload": event["payload"],
            }, default=str))

            # Push WebSocket notification based on event type
            await _handle_ws_notification(event)

            await mark_published(db, event["_id"])
        except Exception as exc:
            logger.error("Outbox relay failed for event", event_id=event["_id"], error=str(exc))
            await mark_failed(db, event["_id"], str(exc))


async def _handle_ws_notification(event: dict) -> None:
    """Push WebSocket messages for relevant event types."""
    payload = event.get("payload", {})
    event_type = event.get("event_type", "")
    incident_id = payload.get("incident_id")

    if incident_id:
        await ws_manager.broadcast_incident_update(incident_id, payload)
        await ws_manager.broadcast_to_dispatchers(payload)

    if event_type == "DispatchOfferSent":
        unit_id = payload.get("unit_id")
        if unit_id:
            await ws_manager.send_to_unit(unit_id, payload)


async def offer_sweeper(ctx: dict) -> None:
    """
    Periodic task: find expired PENDING offers, release units, re-queue incidents.
    Runs every OFFER_EXPIRY_SECONDS / 3 (i.e. ~5s) to keep latency low.
    """
    db = get_db()
    now = utcnow()

    expired_offers = await db.dispatch_offers.find(
        {"status": OfferStatus.PENDING.value, "expires_at": {"$lt": now}},
        limit=50,
    ).to_list(length=50)

    if not expired_offers:
        return

    logger.info("Sweeping expired offers", count=len(expired_offers))

    for offer in expired_offers:
        offer_id = offer["_id"]
        unit_id = offer["unit_id"]
        incident_id = offer["incident_id"]

        async with await db.client.start_session() as session:
            async with session.start_transaction():
                # Mark offer expired
                await db.dispatch_offers.update_one(
                    {"_id": offer_id},
                    {"$set": {"status": OfferStatus.EXPIRED.value, "updated_at": now}},
                    session=session,
                )
                # CAS release unit back to AVAILABLE
                await db.ambulances.update_one(
                    {"_id": unit_id, "status": AmbulanceStatus.OFFERED.value},
                    {
                        "$set": {"status": AmbulanceStatus.AVAILABLE.value, "active_incident_id": None, "updated_at": now},
                        "$inc": {"version": 1},
                    },
                    session=session,
                )
                # Re-queue incident for next dispatch round
                incident_doc = await db.incidents.find_one({"_id": incident_id}, session=session)
                if incident_doc and incident_doc["status"] == IncidentStatus.OFFERING.value:
                    await db.incidents.update_one(
                        {"_id": incident_id},
                        {"$set": {"status": IncidentStatus.QUEUED.value, "updated_at": now}, "$inc": {"version": 1}},
                        session=session,
                    )

        # Enqueue next dispatch attempt
        redis: ArqRedis = ctx["redis"]
        await redis.enqueue_job("process_dispatch", incident_id)
        logger.info("Offer expired, re-dispatching", offer_id=offer_id, incident_id=incident_id)
