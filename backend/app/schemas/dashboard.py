from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
import uuid
from pydantic import BaseModel, Field


# ------------------------------------------------------------------------------
# Widget Schemas
# ------------------------------------------------------------------------------

WidgetType = Literal["line", "bar", "pie", "kpi", "table"]


class WidgetBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: WidgetType
    layout: Dict[str, Any] = Field(
        default_factory=dict,
        description="Coordinates and sizes, e.g., {'x': 0, 'y': 0, 'w': 6, 'h': 4}"
    )
    query_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metrics query configuration, e.g., {'metric_type': 'page_views', 'interval': 'day'}"
    )


class WidgetCreate(WidgetBase):
    pass


class WidgetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    type: Optional[WidgetType] = None
    layout: Optional[Dict[str, Any]] = None
    query_config: Optional[Dict[str, Any]] = None


class WidgetOut(WidgetBase):
    id: uuid.UUID
    dashboard_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------------------------
# Dashboard Schemas
# ------------------------------------------------------------------------------

class DashboardBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    is_public: bool = Field(default=False)


class DashboardCreate(DashboardBase):
    pass


class DashboardUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    is_public: Optional[bool] = None


class DashboardOut(DashboardBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    share_token: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DashboardFullOut(DashboardOut):
    widgets: List[WidgetOut] = []


class DashboardShareUpdate(BaseModel):
    is_public: bool
