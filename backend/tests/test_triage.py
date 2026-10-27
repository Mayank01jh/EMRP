"""
Unit tests for AI Triage Service
"""
from __future__ import annotations

import pytest
from app.models.incident import IncidentSeverity
from app.services.triage_service import triage_service


@pytest.mark.asyncio
async def test_critical_cardiac_triage():
    result = await triage_service.analyze_incident_symptoms("Patient collapsed, unconscious, not breathing")
    assert result.severity == IncidentSeverity.CRITICAL
    assert result.triage_category == "RED"
    assert result.recommended_vehicle_type == "ALS"
    assert len(result.immediate_pre_arrival_guidance) > 0


@pytest.mark.asyncio
async def test_trauma_chest_pain_triage():
    result = await triage_service.analyze_incident_symptoms("Severe crushing chest pain radiating to left arm")
    assert result.severity == IncidentSeverity.HIGH
    assert result.triage_category == "YELLOW"
    assert result.recommended_vehicle_type == "ALS"


@pytest.mark.asyncio
async def test_moderate_injury_triage():
    result = await triage_service.analyze_incident_symptoms("Sprained ankle after falling, mild swelling")
    assert result.severity == IncidentSeverity.MEDIUM
    assert result.triage_category == "GREEN"
    assert result.recommended_vehicle_type == "BLS"
