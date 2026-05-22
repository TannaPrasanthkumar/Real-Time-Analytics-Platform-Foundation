from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field


class EventIngestSingle(BaseModel):
    """Schema for a single event ingestion payload."""
    event_name: str = Field(..., max_length=255, min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict = Field(default_factory=dict)
    data_source_id: uuid.UUID | None = Field(default=None)


class EventIngestBatch(BaseModel):
    """Schema for a batched events ingestion payload."""
    events: list[EventIngestSingle] = Field(..., min_length=1)


class EventResponse(BaseModel):
    """Schema representing an event detail."""
    id: uuid.UUID
    organization_id: uuid.UUID
    data_source_id: uuid.UUID | None
    event_name: str
    timestamp: datetime
    payload: dict
    created_at: datetime

    class Config:
        from_attributes = True
