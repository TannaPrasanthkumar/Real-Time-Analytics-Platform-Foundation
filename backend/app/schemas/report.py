import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr


# ------------------------------------------------------------------------------
# Report Schedule Schemas
# ------------------------------------------------------------------------------

class ReportScheduleBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    dashboard_id: Optional[uuid.UUID] = None
    frequency: str = Field(min_length=1, max_length=50)  # daily, weekly, monthly
    recipients: List[EmailStr] = Field(default_factory=list)
    is_active: bool = Field(default=True)


class ReportScheduleCreate(ReportScheduleBase):
    pass


class ReportScheduleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    dashboard_id: Optional[uuid.UUID] = None
    frequency: Optional[str] = Field(default=None, min_length=1, max_length=50)
    recipients: Optional[List[EmailStr]] = None
    is_active: Optional[bool] = None


class ReportScheduleOut(ReportScheduleBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------------------------
# Report History Schemas
# ------------------------------------------------------------------------------

class ReportHistoryOut(BaseModel):
    id: uuid.UUID
    report_schedule_id: uuid.UUID
    organization_id: uuid.UUID
    triggered_at: datetime
    status: str
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
