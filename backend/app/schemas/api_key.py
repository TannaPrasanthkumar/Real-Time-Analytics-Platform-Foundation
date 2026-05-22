import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class APIKeyCreate(BaseModel):
    """Payload to create a new API Key."""
    name: str = Field(..., max_length=255)
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """API response contract representing details of an API Key."""
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    prefix: str
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreatedResponse(APIKeyResponse):
    """API response including the full unhashed API key secret (only shown once at creation)."""
    raw_key: str
