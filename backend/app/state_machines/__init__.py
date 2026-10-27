"""State machines package."""
from app.state_machines.incident_fsm import (
    validate_transition, build_status_update, InvalidTransitionError
)
from app.state_machines.ambulance_fsm import (
    validate_ambulance_transition, build_ambulance_status_update, InvalidAmbulanceTransitionError
)

__all__ = [
    "validate_transition", "build_status_update", "InvalidTransitionError",
    "validate_ambulance_transition", "build_ambulance_status_update", "InvalidAmbulanceTransitionError",
]
