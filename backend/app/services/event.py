import uuid
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.repositories.event import EventRepository
from app.models.event import Event
from app.schemas.event import EventIngestSingle
from app.core.exceptions import BadRequestException
from app.repositories.data_source import DataSourceRepository
from app.worker.tasks.ingestion import ingest_event_batch


class EventService(BaseService[Event, EventRepository]):
    """Service layer coordinating analytical Event ingestions and queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(EventRepository(session))
        self.data_source_repo = DataSourceRepository(session)

    async def ingest_events(
        self, organization_id: uuid.UUID, event_schemas: List[EventIngestSingle]
    ) -> Dict[str, Any]:
        """Dispatch validated events directly to the Celery ingestion queue."""
        event_payloads = []
        
        for schema in event_schemas:
            # If data_source_id is provided, verify it exists under this organization
            if schema.data_source_id:
                ds = await self.data_source_repo.get_by_org_and_id(
                    organization_id, schema.data_source_id
                )
                if not ds or not ds.is_active:
                    raise BadRequestException(
                        message=f"Data source with ID '{schema.data_source_id}' is inactive or not found."
                    )
                    
            event_payloads.append({
                "id": str(uuid.uuid4()),
                "organization_id": str(organization_id),
                "data_source_id": str(schema.data_source_id) if schema.data_source_id else None,
                "event_name": schema.event_name,
                "timestamp": schema.timestamp.isoformat(),
                "payload": schema.payload,
            })
            
        # Dispatch to background task queue
        task = ingest_event_batch.delay(event_payloads)
        
        # Broadcast live events via Redis Pub/Sub WebSocket stream
        from app.services.websocket import publish_live_message
        for payload in event_payloads:
            await publish_live_message(
                organization_id,
                {
                    "type": "event",
                    "data": payload
                }
            )
        
        return {
            "success": True,
            "task_id": task.id,
            "count": len(event_payloads),
            "message": "Events successfully queued for background ingestion.",
        }


    async def get_org_events(
        self, organization_id: uuid.UUID, limit: int = 100, skip: int = 0
    ) -> List[Event]:
        """Retrieve historical events chronologically for analytical verification."""
        return await self.repository.get_by_org(organization_id, limit=limit, skip=skip)
