"""Incident data models and state machine definitions."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.models.base import BaseDocument, GeoJSONPoint, new_id, utcnow


class IncidentStatus(StrEnum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    OFFERING = "OFFERING"
    ASSIGNED = "ASSIGNED"
    EN_ROUTE = "EN_ROUTE"
    ON_SCENE = "ON_SCENE"
    TRANSPORTING = "TRANSPORTING"
    HANDED_OVER = "HANDED_OVER"
    CLOSED = "CLOSED"
    # Exception states
    CANCELLED = "CANCELLED"
    DUPLICATE_LINKED = "DUPLICATE_LINKED"
    ESCALATED_MANUAL = "ESCALATED_MANUAL"
    NO_RESOURCE = "NO_RESOURCE"
    FAILED_REQUIRES_OPERATOR = "FAILED_REQUIRES_OPERATOR"


class IncidentSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Valid state transitions
INCIDENT_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.RECEIVED: {IncidentStatus.VALIDATING, IncidentStatus.CANCELLED},
    IncidentStatus.VALIDATING: {IncidentStatus.QUEUED, IncidentStatus.CANCELLED, IncidentStatus.FAILED_REQUIRES_OPERATOR},
    IncidentStatus.QUEUED: {IncidentStatus.OFFERING, IncidentStatus.NO_RESOURCE, IncidentStatus.CANCELLED, IncidentStatus.ESCALATED_MANUAL},
    IncidentStatus.OFFERING: {IncidentStatus.ASSIGNED, IncidentStatus.NO_RESOURCE, IncidentStatus.CANCELLED, IncidentStatus.ESCALATED_MANUAL},
    IncidentStatus.ASSIGNED: {IncidentStatus.EN_ROUTE, IncidentStatus.QUEUED, IncidentStatus.CANCELLED},
    IncidentStatus.EN_ROUTE: {IncidentStatus.ON_SCENE, IncidentStatus.CANCELLED},
    IncidentStatus.ON_SCENE: {IncidentStatus.TRANSPORTING, IncidentStatus.CLOSED, IncidentStatus.CANCELLED},
    IncidentStatus.TRANSPORTING: {IncidentStatus.HANDED_OVER},
    IncidentStatus.HANDED_OVER: {IncidentStatus.CLOSED},
    IncidentStatus.CLOSED: set(),
    IncidentStatus.CANCELLED: set(),
    IncidentStatus.DUPLICATE_LINKED: set(),
    IncidentStatus.ESCALATED_MANUAL: {IncidentStatus.ASSIGNED, IncidentStatus.CLOSED, IncidentStatus.CANCELLED},
    IncidentStatus.NO_RESOURCE: {IncidentStatus.QUEUED, IncidentStatus.CANCELLED, IncidentStatus.ESCALATED_MANUAL},
    IncidentStatus.FAILED_REQUIRES_OPERATOR: {IncidentStatus.QUEUED, IncidentStatus.CANCELLED},
}


class CallerInfo(BaseModel):
    name: str | None = None
    phone: str | None = None
    notes: str | None = None


class Incident(BaseDocument):
    """Core incident document."""
    caller_id: str
    idempotency_key: str
    request_hash: str  # sha256 of caller_id + coordinates + timestamp bucket
    location: GeoJSONPoint
    accuracy_m: float  # GPS accuracy in metres
    address: str | None = None
    severity: IncidentSeverity = IncidentSeverity.HIGH
    status: IncidentStatus = IncidentStatus.RECEIVED
    caller_info: CallerInfo = Field(default_factory=CallerInfo)

    # Links
    assigned_unit_id: str | None = None
    destination_hospital_id: str | None = None
    parent_incident_id: str | None = None  # MCI parent
    child_incident_ids: list[str] = Field(default_factory=list)

    # Timestamps for each status transition
    received_at: datetime = Field(default_factory=utcnow)
    queued_at: datetime | None = None
    assigned_at: datetime | None = None
    en_route_at: datetime | None = None
    on_scene_at: datetime | None = None
    transporting_at: datetime | None = None
    handed_over_at: datetime | None = None
    closed_at: datetime | None = None
    cancelled_at: datetime | None = None

    # Dispatch tracking
    offer_round: int = 0
    eta_seconds: int | None = None

    # Optimistic concurrency
    version: int = 0


# --- API Schemas ---

class SOSRequest(BaseModel):
    """POST /api/v1/emergency/sos request body."""
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]
    accuracy_m: Annotated[float, Field(ge=0, le=10000)] = 100.0
    severity: IncidentSeverity = IncidentSeverity.HIGH
    caller_info: CallerInfo = Field(default_factory=CallerInfo)

    @field_validator("accuracy_m")
    @classmethod
    def warn_low_accuracy(cls, v: float) -> float:
        # Still accept but flag; front-end should warn user
        return v


class SOSResponse(BaseModel):
    incident_id: str
    status: IncidentStatus
    message: str
    eta_seconds: int | None = None


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus
    reason: str | None = None


class IncidentSummary(BaseModel):
    id: str = Field(alias="_id")
    status: IncidentStatus
    severity: IncidentSeverity
    caller_id: str
    location: GeoJSONPoint
    accuracy_m: float
    assigned_unit_id: str | None
    eta_seconds: int | None
    received_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}
