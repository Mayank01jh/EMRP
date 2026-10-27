"""
AI Medical Triage Service — Hugging Face Inference Integration
"""
from __future__ import annotations

import json
import httpx
from typing import Any
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import logger
from app.models.incident import IncidentSeverity


class TriageAssessment(BaseModel):
    severity: IncidentSeverity
    triage_category: str  # RED, YELLOW, GREEN, BLUE
    suspected_condition: str
    confidence: float
    recommended_vehicle_type: str  # ALS, BLS
    immediate_pre_arrival_guidance: list[str]
    ai_model_used: str


class TriageService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def analyze_incident_symptoms(self, description: str) -> TriageAssessment:
        """
        Analyze symptoms using Hugging Face model repository or rule-based fallback.
        """
        clean_desc = description.strip()
        if not clean_desc:
            return self._default_assessment()

        # If Hugging Face token is provided, attempt HF Inference
        if self.settings.hf_api_key:
            try:
                hf_result = await self._query_huggingface_model(clean_desc)
                if hf_result:
                    return hf_result
            except Exception as e:
                logger.warning("Hugging Face triage query failed, using rule-based fallback", error=str(e))

        # Rule-based clinical heuristic fallback
        return self._rule_based_triage(clean_desc)

    async def _query_huggingface_model(self, description: str) -> TriageAssessment | None:
        """Send prompt to Hugging Face Inference API."""
        url = f"{self.settings.hf_inference_url}/{self.settings.hf_repo_id}"
        headers = {
            "Authorization": f"Bearer {self.settings.hf_api_key}",
            "Content-Type": "application/json",
        }

        prompt = (
            f"You are an Emergency Medical Dispatch triage AI. Analyze this caller report:\n"
            f"Report: \"{description}\"\n"
            f"Respond with JSON containing: "
            f'{{"category": "RED"|"YELLOW"|"GREEN"|"BLUE", "condition": "...", "als_required": true|false, "instructions": ["..."]}}'
        )

        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 200, "temperature": 0.1, "return_full_text": False},
        }

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                generated_text = ""
                if isinstance(data, list) and len(data) > 0:
                    generated_text = data[0].get("generated_text", "")
                elif isinstance(data, dict):
                    generated_text = data.get("generated_text", "")

                # Parse JSON output from model
                try:
                    start_idx = generated_text.find("{")
                    end_idx = generated_text.rfind("}") + 1
                    if start_idx != -1 and end_idx != -1:
                        parsed = json.loads(generated_text[start_idx:end_idx])
                        cat = parsed.get("category", "YELLOW").upper()
                        severity_map = {
                            "RED": IncidentSeverity.CRITICAL,
                            "YELLOW": IncidentSeverity.HIGH,
                            "GREEN": IncidentSeverity.MEDIUM,
                            "BLUE": IncidentSeverity.LOW,
                        }
                        return TriageAssessment(
                            severity=severity_map.get(cat, IncidentSeverity.HIGH),
                            triage_category=cat,
                            suspected_condition=parsed.get("condition", "Medical Emergency"),
                            confidence=0.88,
                            recommended_vehicle_type="ALS" if parsed.get("als_required", True) else "BLS",
                            immediate_pre_arrival_guidance=parsed.get("instructions", ["Keep patient calm and still."]),
                            ai_model_used=self.settings.hf_repo_id,
                        )
                except Exception:
                    pass

        return None

    def _rule_based_triage(self, text: str) -> TriageAssessment:
        """Reliable rule-based clinical decision support."""
        lower = text.lower()

        # Resuscitation / Immediate Life Threat (RED)
        if any(w in lower for w in ["unconscious", "not breathing", "cpr", "cardiac", "heart attack", "collapsed", "severe bleeding", "arterial", "anaphylaxis"]):
            return TriageAssessment(
                severity=IncidentSeverity.CRITICAL,
                triage_category="RED",
                suspected_condition="Cardiac Arrest / Severe Life Threat",
                confidence=0.95,
                recommended_vehicle_type="ALS",
                immediate_pre_arrival_guidance=[
                    "Check responsiveness and airway immediately.",
                    "If not breathing, begin chest compressions at 100-120 bpm in center of chest.",
                    "Send someone to find nearest AED if in public facility.",
                ],
                ai_model_used="emrp-clinical-heuristics-v1",
            )

        # High Acuity / Emergent (YELLOW)
        if any(w in lower for w in ["chest pain", "shortness of breath", "stroke", "slurred speech", "head injury", "severe fall", "fracture", "accident", "mva", "burn"]):
            return TriageAssessment(
                severity=IncidentSeverity.HIGH,
                triage_category="YELLOW",
                suspected_condition="Acute Trauma / Cardiovascular Warning",
                confidence=0.90,
                recommended_vehicle_type="ALS",
                immediate_pre_arrival_guidance=[
                    "Keep patient seated or resting in comfortable position.",
                    "Do not give food or drink.",
                    "Loosen tight clothing around neck and chest.",
                    "Monitor breathing and consciousness continuously.",
                ],
                ai_model_used="emrp-clinical-heuristics-v1",
            )

        # Moderate / Urgent (GREEN)
        if any(w in lower for w in ["sprain", "swelling", "fever", "cut", "dizzy", "vomiting", "stomach pain", "abdominal"]):
            return TriageAssessment(
                severity=IncidentSeverity.MEDIUM,
                triage_category="GREEN",
                suspected_condition="Urgent Non-Life-Threatening Condition",
                confidence=0.85,
                recommended_vehicle_type="BLS",
                immediate_pre_arrival_guidance=[
                    "Keep patient comfortable and resting.",
                    "If bleeding, apply direct pressure with a clean cloth.",
                    "Stay on line until emergency personnel arrive.",
                ],
                ai_model_used="emrp-clinical-heuristics-v1",
            )

        return self._default_assessment()

    def _default_assessment(self) -> TriageAssessment:
        return TriageAssessment(
            severity=IncidentSeverity.HIGH,
            triage_category="YELLOW",
            suspected_condition="Emergency Medical Dispatch Required",
            confidence=0.75,
            recommended_vehicle_type="ALS",
            immediate_pre_arrival_guidance=[
                "Stay calm and ensure patient airway is clear.",
                "Keep patient still and warm until ambulance arrives.",
            ],
            ai_model_used="emrp-clinical-heuristics-v1",
        )


triage_service = TriageService()
