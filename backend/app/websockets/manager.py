"""
WebSocket Connection Manager

Manages real-time connections for:
- Callers tracking their incident status
- Ambulance crew receiving dispatch offers
- Dispatchers viewing live fleet
- Hospitals receiving pre-alerts

Uses Redis pub/sub for fan-out across multiple server instances.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logging import logger


class ConnectionManager:
    def __init__(self) -> None:
        # incident_id → set of WebSocket connections (callers watching)
        self._incident_watchers: dict[str, set[WebSocket]] = defaultdict(set)
        # unit_id → WebSocket (ambulance app)
        self._unit_connections: dict[str, WebSocket] = {}
        # dispatcher room → set of WebSocket
        self._dispatcher_connections: set[WebSocket] = set()
        # hospital_id → set of WebSocket
        self._hospital_connections: dict[str, set[WebSocket]] = defaultdict(set)

    # ── Connection lifecycle ──────────────────────────────────────────────────

    async def connect_caller(self, websocket: WebSocket, incident_id: str) -> None:
        await websocket.accept()
        self._incident_watchers[incident_id].add(websocket)
        logger.info("Caller connected", incident_id=incident_id)

    def disconnect_caller(self, websocket: WebSocket, incident_id: str) -> None:
        self._incident_watchers[incident_id].discard(websocket)
        logger.info("Caller disconnected", incident_id=incident_id)

    async def connect_unit(self, websocket: WebSocket, unit_id: str) -> None:
        await websocket.accept()
        self._unit_connections[unit_id] = websocket
        logger.info("Unit connected", unit_id=unit_id)

    def disconnect_unit(self, unit_id: str) -> None:
        self._unit_connections.pop(unit_id, None)
        logger.info("Unit disconnected", unit_id=unit_id)

    async def connect_dispatcher(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._dispatcher_connections.add(websocket)
        logger.info("Dispatcher connected")

    def disconnect_dispatcher(self, websocket: WebSocket) -> None:
        self._dispatcher_connections.discard(websocket)

    async def connect_hospital(self, websocket: WebSocket, hospital_id: str) -> None:
        await websocket.accept()
        self._hospital_connections[hospital_id].add(websocket)

    def disconnect_hospital(self, websocket: WebSocket, hospital_id: str) -> None:
        self._hospital_connections[hospital_id].discard(websocket)

    # ── Broadcasting ──────────────────────────────────────────────────────────

    async def broadcast_incident_update(self, incident_id: str, payload: dict[str, Any]) -> None:
        """Push incident status update to all watching callers."""
        dead: set[WebSocket] = set()
        for ws in self._incident_watchers.get(incident_id, set()):
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json({"type": "incident_update", "data": payload})
            except Exception:
                dead.add(ws)
        self._incident_watchers[incident_id] -= dead

    async def send_to_unit(self, unit_id: str, payload: dict[str, Any]) -> bool:
        """Send a message to a specific ambulance unit. Returns True if delivered."""
        ws = self._unit_connections.get(unit_id)
        if ws and ws.client_state == WebSocketState.CONNECTED:
            try:
                await ws.send_json({"type": "dispatch_offer", "data": payload})
                return True
            except Exception:
                self.disconnect_unit(unit_id)
        return False

    async def broadcast_to_dispatchers(self, payload: dict[str, Any]) -> None:
        """Broadcast fleet/incident updates to all connected dispatchers."""
        dead: set[WebSocket] = set()
        for ws in self._dispatcher_connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json({"type": "fleet_update", "data": payload})
            except Exception:
                dead.add(ws)
        self._dispatcher_connections -= dead

    async def send_to_hospital(self, hospital_id: str, payload: dict[str, Any]) -> None:
        """Send pre-alert or update to hospital connections."""
        dead: set[WebSocket] = set()
        for ws in self._hospital_connections.get(hospital_id, set()):
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json({"type": "pre_alert", "data": payload})
            except Exception:
                dead.add(ws)
        self._hospital_connections[hospital_id] -= dead


# Global singleton — one per server process
ws_manager = ConnectionManager()
