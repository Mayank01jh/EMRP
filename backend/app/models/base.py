"""Shared base types and GeoJSON helpers."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
try:
    from ulid import ULID
    def new_id() -> str:
        """Generate a sortable ULID string."""
        return str(ULID())
except ImportError:
    import time
    import uuid
    def new_id() -> str:
        """Fallback sortable unique identifier when ulid is unavailable."""
        return f"{int(time.time()*1000):012x}{uuid.uuid4().hex[:14]}"


def utcnow() -> datetime:
    return datetime.now(UTC)


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


class GeoJSONPoint(BaseModel):
    """GeoJSON Point as stored in MongoDB."""
    type: Literal["Point"] = "Point"
    coordinates: Annotated[list[float], Field(min_length=2, max_length=3)]  # [lon, lat, alt?]

    @property
    def longitude(self) -> float:
        return self.coordinates[0]

    @property
    def latitude(self) -> float:
        return self.coordinates[1]


class BaseDocument(BaseModel):
    """Base for all MongoDB documents."""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: str = Field(default_factory=new_id, alias="_id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""
    items: list[Any]
    total: int
    page: int
    page_size: int
    has_next: bool
