"""
Hospital Router — Phase 4

POST   /api/v1/hospitals/                    — register hospital
GET    /api/v1/hospitals/                    — list hospitals
PATCH  /api/v1/hospitals/{id}/capacity       — update capacity snapshot
POST   /api/v1/hospitals/{id}/pre-alerts/{alert_id}/acknowledge — ack pre-alert
WS     /api/v1/hospitals/{id}/ws             — hospital console live feed
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.base import new_id, utcnow
from app.models.support import (
    CapacitySnapshot, Hospital, HospitalCapability, PreAlert,
)
from app.websockets.manager import ws_manager

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])


class HospitalCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    address: str
    phone: str
    capabilities: list[HospitalCapability] = []
    helipad: bool = False


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_hospital(
    payload: HospitalCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    from app.models.base import GeoJSONPoint
    hospital = Hospital(
        id=new_id(),
        name=payload.name,
        location=GeoJSONPoint(coordinates=[payload.longitude, payload.latitude]),
        address=payload.address,
        phone=payload.phone,
        capabilities=payload.capabilities,
        helipad=payload.helipad,
    )
    await db.hospitals.insert_one(hospital.model_dump(by_alias=True))
    return hospital.model_dump(by_alias=True, mode="json")


@router.get("/", response_model=list[dict])
async def list_hospitals(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    cursor = db.hospitals.find({}, limit=100)
    return await cursor.to_list(length=100)


@router.patch("/{hospital_id}/capacity", status_code=status.HTTP_204_NO_CONTENT)
async def update_capacity(
    hospital_id: str,
    capacity: CapacitySnapshot,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("hospital_admin", "admin")),
):
    result = await db.hospitals.update_one(
        {"_id": hospital_id},
        {"$set": {"capacity": capacity.model_dump(), "updated_at": utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Hospital not found")


@router.post("/{hospital_id}/pre-alerts/{alert_id}/acknowledge", response_model=dict)
async def acknowledge_pre_alert(
    hospital_id: str,
    alert_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("hospital_admin", "admin")),
):
    now = utcnow()
    result = await db.pre_alerts.find_one_and_update(
        {"_id": alert_id, "hospital_id": hospital_id},
        {
            "$set": {
                "acknowledged_at": now,
                "acknowledged_by": current_user["user_id"],
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Pre-alert not found")
    return result


@router.websocket("/{hospital_id}/ws")
async def hospital_websocket(websocket: WebSocket, hospital_id: str):
    await ws_manager.connect_hospital(websocket, hospital_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect_hospital(websocket, hospital_id)
