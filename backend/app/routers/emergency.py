"""
Emergency SOS Router — Phase 1 Core

POST /api/v1/emergency/sos
GET  /api/v1/emergency/{incident_id}
PATCH /api/v1/emergency/{incident_id}/status
WS   /api/v1/emergency/{incident_id}/ws
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any
try:
    from arq import ArqRedis
except ImportError:
    ArqRedis = Any
from fastapi import APIRouter, Depends, Header, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.incident import (
    IncidentStatus, SOSRequest, SOSResponse, IncidentStatusUpdate,
)
from app.services.incident_service import create_incident, transition_incident, get_incident
from app.state_machines.incident_fsm import InvalidTransitionError
from app.websockets.manager import ws_manager

router = APIRouter(prefix="/emergency", tags=["Emergency"])


def _get_arq(request: Request) -> ArqRedis | None:
    return getattr(request.app.state, "arq", None)


@router.post("/sos", response_model=SOSResponse, status_code=status.HTTP_201_CREATED)
async def create_sos(
    sos_req: SOSRequest,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """
    Submit an emergency SOS. Requires Idempotency-Key header.
    Safe to retry — duplicate keys replay the original response.
    """
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )

    request_id = str(uuid.uuid4())
    caller_id = current_user["user_id"]
    ip = request.client.host if request.client else None

    incident = await create_incident(
        db,
        caller_id=caller_id,
        idempotency_key=idempotency_key,
        request=sos_req,
        request_id=request_id,
        ip_address=ip,
    )

    # Enqueue dispatch via Arq (non-blocking with fallback)
    if incident.status == IncidentStatus.RECEIVED:
        try:
            arq = _get_arq(request)
            if arq:
                await arq.enqueue_job("process_dispatch", incident.id)
        except Exception as e:
            logger.warning("Arq dispatch enqueue skipped", error=str(e))

    # Broadcast to dispatcher console WebSockets
    try:
        await ws_manager.broadcast_dispatcher({
            "type": "incident_update",
            "data": {
                "incident_id": incident.id,
                "status": incident.status.value,
                "severity": incident.severity.value,
                "location": incident.location.model_dump() if incident.location else None,
                "caller_info": incident.caller_info,
            },
        })
    except Exception as e:
        logger.warning("Dispatcher WS broadcast skipped", error=str(e))

    return SOSResponse(
        incident_id=incident.id,
        status=incident.status,
        message=(
            "Emergency received. Help is being dispatched."
            if incident.status == IncidentStatus.RECEIVED
            else "Your request has been linked to an active incident."
        ),
        eta_seconds=incident.eta_seconds,
    )


@router.get("/{incident_id}", response_model=dict)
async def get_incident_status(
    incident_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get current incident details."""
    incident = await get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Only allow caller to see their own incident (unless dispatcher/admin)
    if current_user["role"] == "caller" and incident.caller_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return incident.model_dump(by_alias=True, mode="json")


@router.patch("/{incident_id}/status", response_model=dict)
async def update_incident_status(
    incident_id: str,
    update: IncidentStatusUpdate,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Apply a manual status transition (dispatcher/operator only)."""
    if current_user["role"] not in {"dispatcher", "operator", "admin"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        updated = await transition_incident(
            db,
            incident_id=incident_id,
            target_status=update.status,
            actor_id=current_user["user_id"],
            actor_role=current_user["role"],
            request_id=str(uuid.uuid4()),
            ip_address=request.client.host if request.client else None,
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return updated.model_dump(by_alias=True, mode="json")


@router.websocket("/{incident_id}/ws")
async def incident_websocket(websocket: WebSocket, incident_id: str):
    """
    WebSocket endpoint for callers to receive live incident status updates.
    """
    await ws_manager.connect_caller(websocket, incident_id)
    try:
        while True:
            # Keep alive — receive any ping from client
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect_caller(websocket, incident_id)
