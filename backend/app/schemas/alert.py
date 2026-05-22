from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, Field


# ------------------------------------------------------------------------------
# Alert Rule Schemas
# ------------------------------------------------------------------------------

class AlertRuleBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    is_enabled: bool = Field(default=True)
    metric_type: str = Field(min_length=1, max_length=50)  # error_count, page_views, bounce_rate, error_rate, unique_visitors
    operator: str = Field(min_length=1, max_length=10)  # >, <, >=, <=, ==
    threshold: float
    time_window_minutes: int = Field(default=10, ge=1)
    snooze_duration_minutes: int = Field(default=30, ge=1)
    slack_webhook: Optional[str] = Field(default=None, max_length=500)
    email_recipient: Optional[str] = Field(default=None, max_length=255)


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    is_enabled: Optional[bool] = None
    metric_type: Optional[str] = Field(default=None, min_length=1, max_length=50)
    operator: Optional[str] = Field(default=None, min_length=1, max_length=10)
    threshold: Optional[float] = None
    time_window_minutes: Optional[int] = Field(default=None, ge=1)
    snooze_duration_minutes: Optional[int] = Field(default=None, ge=1)
    slack_webhook: Optional[str] = Field(default=None, max_length=500)
    email_recipient: Optional[str] = Field(default=None, max_length=255)


class AlertRuleSnooze(BaseModel):
    snooze_duration_minutes: int = Field(default=30, ge=1)


class AlertRuleOut(AlertRuleBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    current_state: str
    muted_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------------------------
# Alert History Schemas
# ------------------------------------------------------------------------------

class AlertHistoryOut(BaseModel):
    id: uuid.UUID
    alert_rule_id: uuid.UUID
    organization_id: uuid.UUID
    state: str
    value: float
    threshold: float
    details: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
