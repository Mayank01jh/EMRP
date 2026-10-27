"""Dispatch offer and assignment models."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.base import BaseDocument, utcnow


class OfferStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class AssignmentState(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    RELEASED = "RELEASED"


class DispatchOffer(BaseDocument):
    """
    Represents a single offer sent to one ambulance unit for one incident.
    The transactional CAS pattern operates on this document.
    """
    incident_id: str
    unit_id: str
    offer_number: int           # monotonically increasing per incident
    status: OfferStatus = OfferStatus.PENDING
    offered_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime        # offered_at + OFFER_EXPIRY_SECONDS
    responded_at: datetime | None = None
    road_eta_seconds: int | None = None
    straight_line_km: float | None = None
    version: int = 0


class Assignment(BaseDocument):
    """
    Active link between an incident and an ambulance unit.
    Unique partial index on (unit_id, state=ACTIVE) enforces single active assignment.
    """
    incident_id: str
    unit_id: str
    offer_id: str
    state: AssignmentState = AssignmentState.ACTIVE
    accepted_at: datetime = Field(default_factory=utcnow)
    released_at: datetime | None = None
    completed_at: datetime | None = None


class OfferResponse(BaseModel):
    """Sent by ambulance crew to accept/decline an offer."""
    accepted: bool
    reason: str | None = None   # required if declined
