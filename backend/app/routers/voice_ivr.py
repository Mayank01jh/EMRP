"""
Voice IVR & Gemini Automated Emergency Dispatch Router
Handles automated phone calls:
- Greets caller with automated voice
- Gathers severity & records address
- Transcribes and extracts medical parameters via Gemini
- Captures caller phone number & active location
- Creates incident in MongoDB Atlas
"""
from __future__ import annotations

import base64
import os
import uuid
from typing import Any
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.base import new_id, utcnow
from app.models.incident import IncidentSeverity, IncidentStatus
from app.services.gemini_service import analyze_speech_with_gemini, transcribe_and_triage_audio
from app.websockets.manager import ws_manager

router = APIRouter(prefix="/voice", tags=["Voice Emergency Hotline"])

# Designated Emergency Hotline Number
EMERGENCY_HOTLINE_NUMBER = os.getenv("EMERGENCY_HOTLINE_NUMBER", "+91 11 4084 9108")


class ProcessCallRequest(BaseModel):
    caller_phone: str = Field(..., description="Phone number captured during active call")
    caller_name: str | None = Field(default="Emergency Voice Caller")
    transcript: str | None = Field(default=None, description="Spoken voice transcript if pre-transcribed")
    audio_base64: str | None = Field(default=None, description="Raw recorded voice audio in base64")
    mime_type: str = Field(default="audio/webm")
    latitude: float = Field(default=28.6139, description="Active location latitude")
    longitude: float = Field(default=77.2090, description="Active location longitude")
    accuracy_m: float = Field(default=15.0)


@router.get("/hotline-config")
async def get_hotline_config():
    """Return the designated emergency hotline phone number and automated IVR script."""
    return {
        "hotline_number": EMERGENCY_HOTLINE_NUMBER,
        "ivr_system": "EMRP Automated Voice Dispatch Engine",
        "gemini_powered": True,
        "active_features": [
            "Automatic Caller ID (ANI) phone capture",
            "Automated Voice Prompt: What is the case?",
            "Instant End Call & Dispatch action",
            "Gemini AI voice-to-text triage & severity analysis",
            "Automatic location capture via active GPS telemetry",
            "Instant dispatcher console WebSocket broadcast",
        ],
        "script": {
            "step_1_greeting": "This is the Emergency Medical Response automated dispatch hotline. What is the case?",
            "step_2_confirmation": "Your emergency case has been recorded. Help is being dispatched.",
        },
    }


@router.post("/process-call", status_code=status.HTTP_201_CREATED)
async def process_emergency_call(
    payload: ProcessCallRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Process an emergency call:
    1. Transcribes audio & extracts severity level and address using Gemini.
    2. Saves caller phone number and active GPS coordinates.
    3. Persists incident into MongoDB Atlas.
    4. Notifies dispatcher consoles in real time.
    """
    triage_result: dict[str, Any] = {}

    if payload.audio_base64:
        try:
            audio_bytes = base64.b64decode(payload.audio_base64)
            triage_result = await transcribe_and_triage_audio(audio_bytes, payload.mime_type)
        except Exception as e:
            triage_result = await analyze_speech_with_gemini(payload.transcript or "Emergency medical assistance needed.")
    elif payload.transcript:
        triage_result = await analyze_speech_with_gemini(payload.transcript)
    else:
        triage_result = {
            "severity": "CRITICAL",
            "triage_category": "RED",
            "suspected_condition": "Voice Hotline Emergency",
            "extracted_address": "Caller Active Telemetry Location",
            "clinical_notes": "Immediate operator callback required.",
        }

    severity_str = triage_result.get("severity", "HIGH").upper()
    try:
        severity_enum = IncidentSeverity(severity_str)
    except ValueError:
        severity_enum = IncidentSeverity.HIGH

    incident_id = new_id()
    now = utcnow()

    incident_doc = {
        "_id": incident_id,
        "caller_id": f"voice-{payload.caller_phone.replace('+', '')}",
        "idempotency_key": f"voice-call-{incident_id}",
        "request_hash": f"voice-{incident_id}",
        "location": {
            "type": "Point",
            "coordinates": [payload.longitude, payload.latitude],
        },
        "accuracy_m": payload.accuracy_m,
        "address": triage_result.get("extracted_address") or "Active GPS Location",
        "severity": severity_enum.value,
        "status": IncidentStatus.RECEIVED.value,
        "caller_info": {
            "name": payload.caller_name or "Emergency Voice Caller",
            "phone": payload.caller_phone,
            "notes": f"[{triage_result.get('triage_category', 'RED')}] {triage_result.get('suspected_condition', 'Emergency')} — {triage_result.get('clinical_notes', '')}",
        },
        "assigned_unit_id": None,
        "destination_hospital_id": None,
        "parent_incident_id": None,
        "child_incident_ids": [],
        "received_at": now,
        "created_at": now,
        "updated_at": now,
        "offer_round": 0,
        "eta_seconds": None,
        "version": 0,
        "channel": "VOICE_IVR_GEMINI",
        "transcript": triage_result.get("transcript") or payload.transcript,
    }

    await db.incidents.insert_one(incident_doc)

    # Real-time WebSocket broadcast to Dispatchers
    try:
        await ws_manager.broadcast_dispatcher({
            "type": "incident_update",
            "data": incident_doc,
        })
    except Exception:
        pass

    return {
        "success": True,
        "incident_id": incident_id,
        "severity": severity_enum.value,
        "caller_phone": payload.caller_phone,
        "address": incident_doc["address"],
        "condition": triage_result.get("suspected_condition"),
        "triage_category": triage_result.get("triage_category"),
        "transcript": incident_doc["transcript"],
    }


@router.post("/twiml/inbound", response_class=Response)
async def twiml_inbound_voice(From: str = Form(default="+919876543210")):
    """
    Standard Telephony TwiML webhook (for Twilio, Exotel, or SIP trunk):
    Greets caller with automated voice and initiates address recording.
    """
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="en-IN">
        Emergency Medical Response dispatch hotline.
        Please describe what is the case after the beep. Hang up or press pound when finished.
    </Say>
    <Record 
        action="/api/v1/voice/twiml/recorded?CallerPhone={From}" 
        method="POST" 
        maxLength="60" 
        finishOnKey="#" 
        playBeep="true"
    />
    <Say voice="Polly.Aditi" language="en-IN">
        Thank you. Your emergency case has been recorded and help is being dispatched.
    </Say>
</Response>"""
    return Response(content=twiml_response, media_type="application/xml")
