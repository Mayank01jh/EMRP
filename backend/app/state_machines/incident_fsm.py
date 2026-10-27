"""Incident Finite State Machine."""
from __future__ import annotations

from datetime import UTC, datetime

from app.models.incident import INCIDENT_TRANSITIONS, IncidentStatus


class InvalidTransitionError(Exception):
    def __init__(self, current: IncidentStatus, target: IncidentStatus) -> None:
        super().__init__(f"Invalid incident transition: {current} → {target}")
        self.current = current
        self.target = target


def validate_transition(current: IncidentStatus, target: IncidentStatus) -> None:
    """Raise InvalidTransitionError if the transition is not allowed."""
    allowed = INCIDENT_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError(current, target)


def build_status_update(current: IncidentStatus, target: IncidentStatus) -> dict:
    """
    Return a MongoDB $set dict for the status transition.
    Sets the relevant timestamp field and increments version.
    """
    validate_transition(current, target)
    now = datetime.now(UTC)
    update: dict = {
        "status": target.value,
        "updated_at": now,
    }
    # Map status → timestamp field
    timestamp_map: dict[IncidentStatus, str] = {
        IncidentStatus.QUEUED: "queued_at",
        IncidentStatus.ASSIGNED: "assigned_at",
        IncidentStatus.EN_ROUTE: "en_route_at",
        IncidentStatus.ON_SCENE: "on_scene_at",
        IncidentStatus.TRANSPORTING: "transporting_at",
        IncidentStatus.HANDED_OVER: "handed_over_at",
        IncidentStatus.CLOSED: "closed_at",
        IncidentStatus.CANCELLED: "cancelled_at",
    }
    if ts_field := timestamp_map.get(target):
        update[ts_field] = now
    return update
