import uuid
from typing import List, Dict, Any, Optional
import csv
import io
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.repositories.data_source import DataSourceRepository
from app.models.data_source import DataSource
from app.schemas.data_source import DataSourceCreate, DataSourceUpdate
from app.core.exceptions import NotFoundException, BadRequestException
from app.worker.tasks.ingestion import ingest_event_batch


class DataSourceService(BaseService[DataSource, DataSourceRepository]):
    """Service layer orchestrating multi-format data ingestion sources."""

    def __init__(self, session: AsyncSession):
        super().__init__(DataSourceRepository(session))

    async def create_source(
        self, organization_id: uuid.UUID, schema: DataSourceCreate
    ) -> DataSource:
        """Provision a new data source under an organization."""
        source_data = {
            "organization_id": organization_id,
            "name": schema.name,
            "type": schema.type,
            "config": schema.config or {},
            "is_active": True,
        }
        return await self.repository.create(source_data)

    async def get_org_sources(self, organization_id: uuid.UUID) -> List[DataSource]:
        """Retrieve all active data sources for an organization."""
        return await self.repository.get_by_org(organization_id)

    async def get_org_source(
        self, organization_id: uuid.UUID, source_id: uuid.UUID
    ) -> DataSource:
        """Retrieve a specific active data source for an organization."""
        source = await self.repository.get_by_org_and_id(organization_id, source_id)
        if not source:
            raise NotFoundException(message="Data Source was not found.")
        return source

    async def update_source(
        self, organization_id: uuid.UUID, source_id: uuid.UUID, schema: DataSourceUpdate
    ) -> DataSource:
        """Update an existing data source's configuration."""
        source = await self.get_org_source(organization_id, source_id)
        update_data = schema.model_dump(exclude_unset=True)
        return await self.repository.update(source, update_data)

    async def delete_source(self, organization_id: uuid.UUID, source_id: uuid.UUID) -> None:
        """Soft-delete an existing data source."""
        source = await self.get_org_source(organization_id, source_id)
        await self.repository.soft_delete(source)

    async def process_csv_upload(
        self, organization_id: uuid.UUID, source_id: uuid.UUID, csv_content: str
    ) -> Dict[str, Any]:
        """Asynchronously process analytics events imported via CSV uploads."""
        source = await self.get_org_source(organization_id, source_id)
        if source.type != "csv":
            raise BadRequestException(message="This data source does not support CSV uploads.")
            
        if not csv_content.strip():
            raise BadRequestException(message="CSV file is empty.")
            
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            events = []
            
            # Map CSV rows into standard Event schemas
            for row in reader:
                # Expect columns: event_name, timestamp (optional, falls back to now), and rest as payload
                event_name = row.get("event_name") or row.get("event")
                if not event_name:
                    continue  # skip invalid rows
                    
                timestamp_str = row.get("timestamp") or row.get("time")
                timestamp = datetime.now(timezone.utc)
                if timestamp_str:
                    try:
                        # Attempt standard ISO 8601 parsing
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    except ValueError:
                        pass
                        
                # Extrapolate dynamic custom properties excluding core keys
                payload = {k: v for k, v in row.items() if k not in ["event_name", "event", "timestamp", "time"]}
                
                events.append({
                    "id": str(uuid.uuid4()),
                    "organization_id": str(organization_id),
                    "data_source_id": str(source_id),
                    "event_name": event_name,
                    "timestamp": timestamp.isoformat(),
                    "payload": payload,
                })
                
            if not events:
                raise BadRequestException(message="No valid event entries parsed from CSV.")
                
            # Trigger asynchronous ingestion batch task
            task = ingest_event_batch.delay(events)
            
            return {
                "success": True,
                "task_id": task.id,
                "parsed_records": len(events),
                "message": "CSV upload queued for ingestion successfully.",
            }
            
        except Exception as e:
            if isinstance(e, BadRequestException):
                raise e
            raise BadRequestException(message=f"Failed to parse CSV upload: {str(e)}")

    async def process_webhook_payload(
        self, organization_id: uuid.UUID, source_id: uuid.UUID, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert a standard external webhook post into standard events and ingest."""
        source = await self.get_org_source(organization_id, source_id)
        if source.type != "webhook":
            raise BadRequestException(message="This data source does not support webhook payloads.")
            
        # Extrapolate event details based on DataSource mapping config if any
        # By default, match payload properties or fallback to direct ingestion
        config = source.config or {}
        event_name_path = config.get("event_name_path", "event")
        timestamp_path = config.get("timestamp_path", "timestamp")
        
        event_name = payload.get(event_name_path, "webhook_event")
        timestamp_str = payload.get(timestamp_path)
        timestamp = datetime.now(timezone.utc)
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                pass
                
        event_data = {
            "id": str(uuid.uuid4()),
            "organization_id": str(organization_id),
            "data_source_id": str(source_id),
            "event_name": str(event_name),
            "timestamp": timestamp.isoformat(),
            "payload": payload,
        }
        
        # Dispatch to ingestion pipeline
        task = ingest_event_batch.delay([event_data])
        
        return {
            "success": True,
            "task_id": task.id,
            "message": "Webhook payload received and queued successfully.",
        }
