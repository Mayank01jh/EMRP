"""
Test suite for Phase 2 — Fleet & Ambulance FSM
"""
from __future__ import annotations

import pytest

from app.models.ambulance import (
    AMBULANCE_TRANSITIONS,
    AmbulanceStatus,
    VehicleCapability,
    AmbulanceCreate,
    TelemetryUpdate,
)
from app.state_machines.ambulance_fsm import (
    validate_ambulance_transition,
    build_ambulance_status_update,
    InvalidAmbulanceTransitionError,
)


class TestAmbulanceFSM:
    def test_valid_start_shift(self):
        validate_ambulance_transition(AmbulanceStatus.OFF_DUTY, AmbulanceStatus.AVAILABLE)

    def test_valid_offering_flow(self):
        validate_ambulance_transition(AmbulanceStatus.AVAILABLE, AmbulanceStatus.OFFERED)
        validate_ambulance_transition(AmbulanceStatus.OFFERED, AmbulanceStatus.DISPATCHED)
        validate_ambulance_transition(AmbulanceStatus.DISPATCHED, AmbulanceStatus.EN_ROUTE)
        validate_ambulance_transition(AmbulanceStatus.EN_ROUTE, AmbulanceStatus.ON_SCENE)
        validate_ambulance_transition(AmbulanceStatus.ON_SCENE, AmbulanceStatus.TRANSPORTING)
        validate_ambulance_transition(AmbulanceStatus.TRANSPORTING, AmbulanceStatus.HANDOVER)
        validate_ambulance_transition(AmbulanceStatus.HANDOVER, AmbulanceStatus.AVAILABLE)

    def test_offer_rejected_returns_to_available(self):
        validate_ambulance_transition(AmbulanceStatus.OFFERED, AmbulanceStatus.AVAILABLE)

    def test_invalid_skip_state(self):
        with pytest.raises(InvalidAmbulanceTransitionError):
            validate_ambulance_transition(AmbulanceStatus.OFF_DUTY, AmbulanceStatus.TRANSPORTING)

    def test_build_status_update(self):
        update = build_ambulance_status_update(
            AmbulanceStatus.AVAILABLE, AmbulanceStatus.OFFERED
        )
        assert update["status"] == AmbulanceStatus.OFFERED.value
        assert "updated_at" in update


class TestAmbulanceModels:
    def test_ambulance_create_defaults(self):
        model = AmbulanceCreate(
            registration="KA-01-EQ-9999",
            operator_id="EMRI-BLR",
            capabilities=[VehicleCapability.ALS],
        )
        assert model.registration == "KA-01-EQ-9999"
        assert VehicleCapability.ALS in model.capabilities
        assert len(model.crew) == 0

    def test_telemetry_model(self):
        telemetry = TelemetryUpdate(
            latitude=12.9716,
            longitude=77.5946,
            accuracy_m=5.0,
            speed_kmh=45.0,
        )
        assert telemetry.latitude == 12.9716
        assert telemetry.speed_kmh == 45.0
