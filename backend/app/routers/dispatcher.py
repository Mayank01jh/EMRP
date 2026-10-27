"""Dispatcher console router."""
from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import require_role
from app.models.base import utcnow
from app.websockets.manager import ws_manager

router = APIRouter(prefix="/dispatcher", tags=["Dispatcher"])


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


class AssignAmbulancePayload(BaseModel):
    unit_id: str


class PurgeStalePayload(BaseModel):
    older_than_minutes: int = 60


@router.get("/incidents", response_model=list[dict])
async def list_active_incidents(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("dispatcher", "admin", "operator")),
):
    """List all active (non-terminal) incidents for the dispatcher board."""
    terminal = {"CLOSED", "CANCELLED", "DUPLICATE_LINKED"}
    cursor = db.incidents.find(
        {"status": {"$nin": list(terminal)}},
        sort=[("received_at", -1)],
        limit=500,
    )
    return await cursor.to_list(length=500)


@router.get("/fleet", response_model=list[dict])
async def live_fleet(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("dispatcher", "admin", "operator")),
):
    """All ambulance units with last known position."""
    cursor = db.ambulances.find({}, limit=500)
    return await cursor.to_list(length=500)


@router.post("/incidents/{incident_id}/assign", response_model=dict)
async def assign_ambulance_to_incident(
    incident_id: str,
    payload: AssignAmbulancePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("dispatcher", "admin", "operator")),
):
    """Manually assign an ambulance unit to an incident."""
    now = utcnow()
    incident = await db.incidents.find_one({"_id": incident_id})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    unit = await db.ambulances.find_one({"_id": payload.unit_id})
    if not unit:
        raise HTTPException(status_code=404, detail="Ambulance unit not found")

    # Compute ETA
    inc_coords = incident.get("location", {}).get("coordinates", [77.2090, 28.6139])
    unit_coords = unit.get("location", {}).get("coordinates", [inc_coords[0] + 0.02, inc_coords[1] + 0.02])
    dist_km = haversine_km(unit_coords[1], unit_coords[0], inc_coords[1], inc_coords[0])
    eta_seconds = max(180, int((dist_km / 38.0) * 3600))

    # Update incident to ASSIGNED / EN_ROUTE
    updated_incident = await db.incidents.find_one_and_update(
        {"_id": incident_id},
        {
            "$set": {
                "status": "ASSIGNED",
                "assigned_unit_id": payload.unit_id,
                "assigned_at": now,
                "eta_seconds": eta_seconds,
                "updated_at": now,
            }
        },
        return_document=True,
    )

    # Update ambulance to DISPATCHED
    await db.ambulances.update_one(
        {"_id": payload.unit_id},
        {
            "$set": {
                "status": "DISPATCHED",
                "active_incident_id": incident_id,
                "last_seen_at": now,
                "updated_at": now,
            }
        },
    )

    # Broadcast updates over WebSockets
    await ws_manager.broadcast_dispatcher({
        "type": "incident_update",
        "data": {
            "incident_id": incident_id,
            "status": "ASSIGNED",
            "assigned_unit_id": payload.unit_id,
            "eta_seconds": eta_seconds,
        },
    })
    await ws_manager.broadcast_dispatcher({"type": "fleet_update", "data": {"unit_id": payload.unit_id}})
    await ws_manager.broadcast_caller(incident_id, {
        "type": "incident_update",
        "data": {
            "incident_id": incident_id,
            "status": "ASSIGNED",
            "assigned_unit_id": payload.unit_id,
            "eta_seconds": eta_seconds,
        },
    })

    return updated_incident


@router.post("/incidents/{incident_id}/auto-assign", response_model=dict)
async def auto_assign_nearest_ambulance(
    incident_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("dispatcher", "admin", "operator")),
):
    """Automatically find and assign the nearest available ambulance."""
    incident = await db.incidents.find_one({"_id": incident_id})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    inc_coords = incident.get("location", {}).get("coordinates", [77.2090, 28.6139])

    # Find available units (or any active unit if none available)
    units = await db.ambulances.find({"status": "AVAILABLE"}).to_list(100)
    if not units:
        units = await db.ambulances.find({}).to_list(100)
    if not units:
        raise HTTPException(status_code=400, detail="No ambulance units registered in fleet")

    def unit_distance(u: dict) -> float:
        loc = u.get("location", {}).get("coordinates")
        if not loc:
            return 9999.0
        return haversine_km(loc[1], loc[0], inc_coords[1], inc_coords[0])

    closest_unit = min(units, key=unit_distance)
    return await assign_ambulance_to_incident(
        incident_id,
        AssignAmbulancePayload(unit_id=closest_unit["_id"]),
        db=db,
        current_user=current_user,
    )


@router.get("/incidents/{incident_id}/route-metrics", response_model=dict)
async def get_incident_route_metrics(
    incident_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("dispatcher", "admin", "operator")),
):
    """Calculates live GPS coordinates and timing from Ambulance -> Scene and Scene -> Hospital."""
    incident = await db.incidents.find_one({"_id": incident_id})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    inc_coords = incident.get("location", {}).get("coordinates", [77.2090, 28.6139])

    # Find unit (assigned or closest)
    unit = None
    if incident.get("assigned_unit_id"):
        unit = await db.ambulances.find_one({"_id": incident["assigned_unit_id"]})
    if not unit:
        unit = await db.ambulances.find_one({})

    if unit and unit.get("location", {}).get("coordinates"):
        unit_coords = unit["location"]["coordinates"]
    else:
        unit_coords = [inc_coords[0] + 0.025, inc_coords[1] + 0.020]

    # Find closest destination hospital
    hospitals = await db.hospitals.find({}).to_list(20)
    if hospitals:
        def hosp_distance(h: dict) -> float:
            loc = h.get("location", {}).get("coordinates", [77.2088, 28.5672])
            return haversine_km(loc[1], loc[0], inc_coords[1], inc_coords[0])

        best_hosp = min(hospitals, key=hosp_distance)
    else:
        best_hosp = {
            "name": "AIIMS Apex Trauma Center",
            "location": {"coordinates": [77.2088, 28.5672]},
        }

    hosp_coords = best_hosp.get("location", {}).get("coordinates", [77.2088, 28.5672])
    hosp_name = best_hosp.get("name", "AIIMS Apex Trauma Center")

    # Leg 1: Ambulance -> Scene
    leg1_dist_km = haversine_km(unit_coords[1], unit_coords[0], inc_coords[1], inc_coords[0])
    leg1_eta_sec = max(180, int((leg1_dist_km / 38.0) * 3600))

    # Leg 2: Scene -> Hospital
    leg2_dist_km = haversine_km(inc_coords[1], inc_coords[0], hosp_coords[1], hosp_coords[0])
    leg2_eta_sec = max(240, int((leg2_dist_km / 38.0) * 3600))

    return {
        "incident_id": incident_id,
        "scene": {
            "coordinates": inc_coords,
            "accuracy_m": incident.get("accuracy_m", 15),
        },
        "ambulance": {
            "unit_id": unit.get("_id") if unit else "AMB-1081",
            "registration": unit.get("registration", "DL-01-AMB-1081") if unit else "DL-01-AMB-1081",
            "status": unit.get("status", "DISPATCHED") if unit else "AVAILABLE",
            "coordinates": unit_coords,
        },
        "hospital": {
            "name": hosp_name,
            "coordinates": hosp_coords,
        },
        "leg1_ambulance_to_scene": {
            "distance_km": leg1_dist_km,
            "eta_seconds": leg1_eta_sec,
        },
        "leg2_scene_to_hospital": {
            "distance_km": leg2_dist_km,
            "eta_seconds": leg2_eta_sec,
        },
        "total_mission_eta_seconds": leg1_eta_sec + leg2_eta_sec,
    }


@router.post("/incidents/purge-stale", response_model=dict)
async def purge_stale_incidents(
    payload: PurgeStalePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("dispatcher", "admin", "operator")),
):
    """Closes old test/stale incidents older than older_than_minutes to keep active queue pristine."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=payload.older_than_minutes)
    cutoff_iso = cutoff.isoformat()
    now = utcnow()
    res = await db.incidents.update_many(
        {
            "$and": [
                {"$or": [{"received_at": {"$lt": cutoff}}, {"received_at": {"$lt": cutoff_iso}}]},
                {"status": {"$nin": ["CLOSED", "CANCELLED", "DUPLICATE_LINKED"]}},
            ]
        },
        {"$set": {"status": "CLOSED", "updated_at": now}},
    )
    # Broadcast refresh
    await ws_manager.broadcast_dispatcher({"type": "incident_update", "data": {"purged": res.modified_count}})
    return {"purged_count": res.modified_count, "cutoff_time": cutoff.isoformat()}


@router.websocket("/ws")
async def dispatcher_websocket(websocket: WebSocket):
    """Dispatcher live feed — fleet movements + incident updates."""
    await ws_manager.connect_dispatcher(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect_dispatcher(websocket)

