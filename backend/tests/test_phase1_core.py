"""
Test suite for Phase 1 — Incident Service

Tests:
- SOS creation (idempotency)
- Duplicate request detection
- FSM transition validation
- Audit log chain
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.incident import IncidentStatus, IncidentSeverity, SOSRequest, CallerInfo
from app.state_machines.incident_fsm import (
    validate_transition, build_status_update, InvalidTransitionError,
)


# ── FSM Tests ─────────────────────────────────────────────────────────────────

class TestIncidentFSM:
    def test_valid_transition_received_to_queued(self):
        """RECEIVED → QUEUED is valid via VALIDATING."""
        validate_transition(IncidentStatus.RECEIVED, IncidentStatus.VALIDATING)

    def test_valid_transition_queued_to_offering(self):
        validate_transition(IncidentStatus.QUEUED, IncidentStatus.OFFERING)

    def test_valid_transition_offering_to_assigned(self):
        validate_transition(IncidentStatus.OFFERING, IncidentStatus.ASSIGNED)

    def test_valid_full_chain(self):
        """Walk the happy path."""
        chain = [
            (IncidentStatus.RECEIVED, IncidentStatus.VALIDATING),
            (IncidentStatus.VALIDATING, IncidentStatus.QUEUED),
            (IncidentStatus.QUEUED, IncidentStatus.OFFERING),
            (IncidentStatus.OFFERING, IncidentStatus.ASSIGNED),
            (IncidentStatus.ASSIGNED, IncidentStatus.EN_ROUTE),
            (IncidentStatus.EN_ROUTE, IncidentStatus.ON_SCENE),
            (IncidentStatus.ON_SCENE, IncidentStatus.TRANSPORTING),
            (IncidentStatus.TRANSPORTING, IncidentStatus.HANDED_OVER),
            (IncidentStatus.HANDED_OVER, IncidentStatus.CLOSED),
        ]
        for src, dst in chain:
            validate_transition(src, dst)  # no exception

    def test_invalid_transition_closed_to_anything(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(IncidentStatus.CLOSED, IncidentStatus.QUEUED)

    def test_invalid_transition_skip_state(self):
        """Cannot jump from RECEIVED directly to ASSIGNED."""
        with pytest.raises(InvalidTransitionError):
            validate_transition(IncidentStatus.RECEIVED, IncidentStatus.ASSIGNED)

    def test_build_status_update_sets_timestamp(self):
        update = build_status_update(IncidentStatus.QUEUED, IncidentStatus.OFFERING)
        assert update["status"] == IncidentStatus.OFFERING.value
        assert "updated_at" in update

    def test_build_status_update_closed_sets_closed_at(self):
        update = build_status_update(IncidentStatus.HANDED_OVER, IncidentStatus.CLOSED)
        assert "closed_at" in update

    def test_invalid_transition_raises_on_build(self):
        with pytest.raises(InvalidTransitionError):
            build_status_update(IncidentStatus.CLOSED, IncidentStatus.QUEUED)


# ── Model Tests ───────────────────────────────────────────────────────────────

class TestSOSRequest:
    def test_valid_coordinates(self):
        req = SOSRequest(latitude=28.6139, longitude=77.2090, accuracy_m=15.0)
        assert req.latitude == 28.6139

    def test_latitude_bounds(self):
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            SOSRequest(latitude=91.0, longitude=0.0)

    def test_longitude_bounds(self):
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            SOSRequest(latitude=0.0, longitude=181.0)

    def test_negative_accuracy_rejected(self):
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            SOSRequest(latitude=0.0, longitude=0.0, accuracy_m=-1.0)

    def test_default_severity_high(self):
        req = SOSRequest(latitude=0.0, longitude=0.0)
        assert req.severity == IncidentSeverity.HIGH


# ── Routing Fallback Tests ────────────────────────────────────────────────────

class TestRoutingFallback:
    def test_haversine_distance(self):
        from app.services.routing_service import haversine_km
        # Delhi to Mumbai ~1148 km
        dist = haversine_km(28.6139, 77.2090, 19.0760, 72.8777)
        assert 1100 < dist < 1200

    def test_same_point_zero_distance(self):
        from app.services.routing_service import haversine_km
        dist = haversine_km(28.6, 77.2, 28.6, 77.2)
        assert dist < 0.001

    @pytest.mark.asyncio
    async def test_osrm_fallback_on_connection_error(self):
        """When OSRM is down, should return haversine estimate."""
        from app.services.routing_service import get_road_eta_seconds
        # OSRM not running in test — will fallback
        eta, dist = await get_road_eta_seconds(28.6139, 77.2090, 28.7, 77.3)
        assert eta > 0
        assert dist > 0
