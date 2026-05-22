from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class InvitationCreate(BaseModel):
    """Payload to request/create a new team onboarding workspace invitation."""
    email: EmailStr
    role: UserRole = Field(default=UserRole.VIEWER)


class InvitationResponse(BaseModel):
    """API response contract representing structured details of an invitation."""
    id: uuid.UUID
    email: EmailStr
    organization_id: uuid.UUID
    organization_name: str
    role: UserRole
    token: str
    expires_at: datetime
    is_accepted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InvitationAccept(BaseModel):
    """Payload to complete onboarding and join organization via invitation token."""
    token: str
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)
