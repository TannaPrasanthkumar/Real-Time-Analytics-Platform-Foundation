import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class DataSourceCreate(BaseModel):
    """Payload to create a new data source."""
    name: str = Field(..., max_length=255)
    type: str = Field(default="api", pattern="^(api|csv|webhook)$")
    config: dict | None = Field(default=None)


class DataSourceUpdate(BaseModel):
    """Payload to update an existing data source."""
    name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = Field(default=None)
    config: dict | None = Field(default=None)


class DataSourceResponse(BaseModel):
    """API response representing a DataSource."""
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    type: str
    config: dict | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
