"""
Triage Router — AI Symptom Assessment via Hugging Face or Heuristics
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.services.triage_service import triage_service, TriageAssessment

router = APIRouter(prefix="/triage", tags=["AI Triage"])


class TriageRequest(BaseModel):
    description: str = Field(..., description="Chief complaint, symptoms, or emergency transcript")


@router.post("/assess", response_model=TriageAssessment)
async def assess_incident_symptoms(
    payload: TriageRequest,
):
    """
    Classify emergency urgency and pre-arrival instructions using Hugging Face model or clinical rules.
    """
    return await triage_service.analyze_incident_symptoms(payload.description)
