"""Ambulance / unit data models."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.base import BaseDocument, GeoJSONPoint, utcnow


class AmbulanceStatus(StrEnum):
    OFF_DUTY = "OFF_DUTY"
    AVAILABLE = "AVAILABLE"
    OFFERED = "OFFERED"
    DISPATCHED = "DISPATCHED"
    EN_ROUTE = "EN_ROUTE"
    ON_SCENE = "ON_SCENE"
    TRANSPORTING = "TRANSPORTING"
    HANDOVER = "HANDOVER"
    MAINTENANCE = "MAINTENANCE"


# Valid ambulance status transitions
AMBULANCE_TRANSITIONS: dict[AmbulanceStatus, set[AmbulanceStatus]] = {
    AmbulanceStatus.OFF_DUTY: {AmbulanceStatus.AVAILABLE, AmbulanceStatus.MAINTENANCE},
    AmbulanceStatus.AVAILABLE: {AmbulanceStatus.OFFERED, AmbulanceStatus.OFF_DUTY, AmbulanceStatus.MAINTENANCE},
    AmbulanceStatus.OFFERED: {AmbulanceStatus.DISPATCHED, AmbulanceStatus.AVAILABLE},  # offer accepted or expired
    AmbulanceStatus.DISPATCHED: {AmbulanceStatus.EN_ROUTE, AmbulanceStatus.AVAILABLE},
    AmbulanceStatus.EN_ROUTE: {AmbulanceStatus.ON_SCENE},
    AmbulanceStatus.ON_SCENE: {AmbulanceStatus.TRANSPORTING, AmbulanceStatus.AVAILABLE},
    AmbulanceStatus.TRANSPORTING: {AmbulanceStatus.HANDOVER},
    AmbulanceStatus.HANDOVER: {AmbulanceStatus.AVAILABLE},
    AmbulanceStatus.MAINTENANCE: {AmbulanceStatus.AVAILABLE, AmbulanceStatus.OFF_DUTY},
}


class VehicleCapability(StrEnum):
    ALS = "ALS"              # Advanced Life Support
    BLS = "BLS"              # Basic Life Support
    VENTILATOR = "VENTILATOR"
    BARIATRIC = "BARIATRIC"
    NEONATAL = "NEONATAL"
    HAZMAT = "HAZMAT"
    BICYCLE = "BICYCLE"      # First-responder bicycle unit


class CrewMember(BaseModel):
    name: str
    role: str  # paramedic, EMT, driver
    license_number: str | None = None


class Ambulance(BaseDocument):
    """Ambulance / response unit document."""
    registration: str  # vehicle plate
    operator_id: str   # owning organisation
    status: AmbulanceStatus = AmbulanceStatus.OFF_DUTY
    capabilities: list[VehicleCapability] = Field(default_factory=list)
    crew: list[CrewMember] = Field(default_factory=list)
    location: GeoJSONPoint | None = None
    heading_deg: float | None = None
    speed_kmh: float | None = None
    last_seen_at: datetime = Field(default_factory=utcnow)
    shift_end_at: datetime | None = None
    active_incident_id: str | None = None  # set when OFFERED / DISPATCHED / etc.
    version: int = 0


class TelemetryUpdate(BaseModel):
    """Sent by ambulance app to update location."""
    latitude: float
    longitude: float
    accuracy_m: float = 10.0
    heading_deg: float | None = None
    speed_kmh: float | None = None


class AmbulanceSummary(BaseModel):
    id: str = Field(alias="_id")
    registration: str
    status: AmbulanceStatus
    capabilities: list[VehicleCapability]
    location: GeoJSONPoint | None
    last_seen_at: datetime
    active_incident_id: str | None

    model_config = {"populate_by_name": True}


class AmbulanceCreate(BaseModel):
    registration: str
    operator_id: str
    capabilities: list[VehicleCapability] = Field(default_factory=list)
    crew: list[CrewMember] = Field(default_factory=list)
