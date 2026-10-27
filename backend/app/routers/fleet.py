"""
Ambulance Fleet Router — Phase 2

POST   /api/v1/fleet/               — register ambulance
GET    /api/v1/fleet/               — list ambulances (dispatcher)
GET    /api/v1/fleet/{unit_id}      — get unit details
PATCH  /api/v1/fleet/{unit_id}/telemetry — push GPS update
PATCH  /api/v1/fleet/{unit_id}/status   — update unit status
POST   /api/v1/fleet/{unit_id}/offers/{offer_id}/respond — accept/decline offer
WS     /api/v1/fleet/{unit_id}/ws   — unit live connection
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.logging import logger
from app.core.security import get_current_user, require_role
from app.models.ambulance import (
    Ambulance, AmbulanceCreate, AmbulanceStatus, AmbulanceSummary, TelemetryUpdate,
)
from app.models.base import new_id, utcnow
from app.models.dispatch import OfferResponse
from app.services.dispatch_service import accept_offer, decline_offer
from app.state_machines.ambulance_fsm import build_ambulance_status_update, InvalidAmbulanceTransitionError
from app.websockets.manager import ws_manager

router = APIRouter(prefix="/fleet", tags=["Fleet"])


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_ambulance(
    payload: AmbulanceCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "operator")),
):
    unit = Ambulance(
        id=new_id(),
        registration=payload.registration,
        operator_id=payload.operator_id,
        capabilities=payload.capabilities,
        crew=payload.crew,
    )
    await db.ambulances.insert_one(unit.model_dump(by_alias=True))
    return unit.model_dump(by_alias=True, mode="json")


@router.get("/", response_model=list[dict])
async def list_ambulances(
    status_filter: AmbulanceStatus | None = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("dispatcher", "admin", "operator")),
):
    query = {}
    if status_filter:
        query["status"] = status_filter.value
    cursor = db.ambulances.find(query, limit=200)
    units = await cursor.to_list(length=200)
    return units


@router.get("/{unit_id}", response_model=dict)
async def get_unit(
    unit_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    unit = await db.ambulances.find_one({"_id": unit_id})
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


@router.patch("/{unit_id}/telemetry", status_code=status.HTTP_204_NO_CONTENT)
async def update_telemetry(
    unit_id: str,
    telemetry: TelemetryUpdate,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Push GPS telemetry from ambulance app. Also broadcasts to dispatchers."""
    now = utcnow()
    update = {
        "location": {
            "type": "Point",
            "coordinates": [telemetry.longitude, telemetry.latitude],
        },
        "last_seen_at": now,
        "updated_at": now,
    }
    if telemetry.heading_deg is not None:
        update["heading_deg"] = telemetry.heading_deg
    if telemetry.speed_kmh is not None:
        update["speed_kmh"] = telemetry.speed_kmh

    result = await db.ambulances.update_one({"_id": unit_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Unit not found")

    # Push to dispatcher WebSocket
    await ws_manager.broadcast_to_dispatchers({
        "unit_id": unit_id,
        "latitude": telemetry.latitude,
        "longitude": telemetry.longitude,
        "heading_deg": telemetry.heading_deg,
        "speed_kmh": telemetry.speed_kmh,
        "timestamp": now.isoformat(),
    })


@router.patch("/{unit_id}/status", response_model=dict)
async def update_unit_status(
    unit_id: str,
    target_status: AmbulanceStatus,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("dispatcher", "admin", "operator", "unit")),
):
    unit = await db.ambulances.find_one({"_id": unit_id})
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    try:
        status_update = build_ambulance_status_update(
            AmbulanceStatus(unit["status"]), target_status
        )
    except InvalidAmbulanceTransitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result = await db.ambulances.find_one_and_update(
        {"_id": unit_id},
        {"$set": status_update, "$inc": {"version": 1}},
        return_document=True,
    )
    return result


@router.post("/{unit_id}/offers/{offer_id}/respond", response_model=dict)
async def respond_to_offer(
    unit_id: str,
    offer_id: str,
    response: OfferResponse,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Ambulance crew accepts or declines a dispatch offer."""
    request_id = str(uuid.uuid4())
    if response.accepted:
        assignment = await accept_offer(
            db, offer_id=offer_id, unit_id=unit_id,
            actor_id=current_user["user_id"], request_id=request_id,
        )
        return assignment.model_dump(by_alias=True, mode="json")
    else:
        await decline_offer(
            db, offer_id=offer_id, unit_id=unit_id,
            reason=response.reason, request_id=request_id,
        )
        return {"status": "declined"}


@router.websocket("/{unit_id}/ws")
async def unit_websocket(websocket: WebSocket, unit_id: str):
    """Live connection for ambulance unit — receives dispatch offers."""
    await ws_manager.connect_unit(websocket, unit_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect_unit(unit_id)
