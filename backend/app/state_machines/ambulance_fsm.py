"""Ambulance Finite State Machine."""
from __future__ import annotations

from app.models.ambulance import AMBULANCE_TRANSITIONS, AmbulanceStatus


class InvalidAmbulanceTransitionError(Exception):
    def __init__(self, current: AmbulanceStatus, target: AmbulanceStatus) -> None:
        super().__init__(f"Invalid ambulance transition: {current} → {target}")
        self.current = current
        self.target = target


def validate_ambulance_transition(current: AmbulanceStatus, target: AmbulanceStatus) -> None:
    allowed = AMBULANCE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidAmbulanceTransitionError(current, target)


def build_ambulance_status_update(current: AmbulanceStatus, target: AmbulanceStatus) -> dict:
    validate_ambulance_transition(current, target)
    from datetime import UTC, datetime
    return {
        "status": target.value,
        "updated_at": datetime.now(UTC),
    }
