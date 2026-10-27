"""Hospital, triage, outbox, and audit models."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.models.base import BaseDocument, GeoJSONPoint, new_id, utcnow


# ── Hospital ──────────────────────────────────────────────────────────────────

class HospitalCapability(StrEnum):
    TRAUMA = "TRAUMA"
    CARDIAC = "CARDIAC"
    STROKE = "STROKE"
    BURNS = "BURNS"
    NEONATAL = "NEONATAL"
    PAEDIATRIC = "PAEDIATRIC"
    ORTHOPAEDIC = "ORTHOPAEDIC"
    PSYCHIATRIC = "PSYCHIATRIC"


class CapacitySnapshot(BaseModel):
    resus_beds_available: int = 0
    icu_beds_available: int = 0
    ed_wait_minutes: int | None = None
    last_updated_at: datetime = Field(default_factory=utcnow)


class Hospital(BaseDocument):
    name: str
    location: GeoJSONPoint
    address: str
    phone: str
    capabilities: list[HospitalCapability] = Field(default_factory=list)
    capacity: CapacitySnapshot = Field(default_factory=CapacitySnapshot)
    helipad: bool = False


class PreAlert(BaseDocument):
    """Pre-alert notification sent to receiving hospital."""
    incident_id: str
    hospital_id: str
    unit_id: str
    eta_seconds: int
    triage_category: str | None = None
    chief_complaint: str | None = None
    vitals_summary: str | None = None   # minimal clinical data
    sent_at: datetime = Field(default_factory=utcnow)
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None


# ── Triage ────────────────────────────────────────────────────────────────────

class TriageCategory(StrEnum):
    P1_IMMEDIATE = "P1_IMMEDIATE"
    P2_URGENT = "P2_URGENT"
    P3_DELAYED = "P3_DELAYED"
    P4_EXPECTANT = "P4_EXPECTANT"
    DECEASED = "DECEASED"


class TriageRecord(BaseDocument):
    incident_id: str
    patient_ref: str        # anonymised reference
    triage_category: TriageCategory
    chief_complaint: str | None = None
    vitals: dict[str, Any] = Field(default_factory=dict)  # HR, BP, SpO2, GCS...
    author_id: str
    triaged_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    prior_hash: str | None = None   # for audit chain
    current_hash: str | None = None


# ── Outbox ────────────────────────────────────────────────────────────────────

class OutboxEvent(BaseDocument):
    """Transactional outbox event for reliable async dispatch."""
    aggregate_id: str           # e.g. incident_id
    aggregate_type: str         # e.g. "Incident"
    event_type: str             # e.g. "IncidentCreated"
    payload: dict[str, Any]
    published: bool = False
    retry_count: int = 0
    last_error: str | None = None
    publish_after: datetime = Field(default_factory=utcnow)
    published_at: datetime | None = None


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditEvent(BaseDocument):
    """Immutable audit log entry."""
    actor_id: str
    actor_role: str
    action: str
    target_type: str
    target_id: str
    request_id: str
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    prior_hash: str | None = None   # hash of previous audit entry for the same target
    current_hash: str              # sha256 of this entry's content
    ip_address: str | None = None
