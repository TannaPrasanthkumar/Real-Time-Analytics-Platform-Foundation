import uuid
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, status

from app.api.deps import get_db, validate_api_key, RequireRole
from app.models.api_key import APIKey
from app.models.user import UserRole
from app.schemas.event import EventIngestSingle, EventResponse
from app.services.event import EventService
from app.services.data_source import DataSourceService

router = APIRouter(tags=["Ingestion & Events"])


@router.post(
    "/ingest",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_single_event(
    schema: EventIngestSingle,
    api_key: APIKey = Depends(validate_api_key),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Ingest a single analytics event. Requires X-API-Key header authentication and rate limit clearance."""
    service = EventService(db)
    return await service.ingest_events(api_key.organization_id, [schema])


@router.post(
    "/ingest/batch",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_batch_events(
    schemas: List[EventIngestSingle],
    api_key: APIKey = Depends(validate_api_key),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Ingest a batch array of analytics events. Requires X-API-Key header authentication and rate limit clearance."""
    service = EventService(db)
    return await service.ingest_events(api_key.organization_id, schemas)


@router.post(
    "/ingest/webhooks/{source_id}",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_webhook_payload(
    source_id: uuid.UUID,
    payload: Dict[str, Any],
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Receive an external webhook payload and ingest asynchronously into workspace events."""
    service = DataSourceService(db)
    # Fetch data source first to find its organization
    ds = await service.repository.get(source_id)
    if not ds or not ds.is_active or ds.is_deleted or ds.type != "webhook":
        from app.core.exceptions import NotFoundException
        raise NotFoundException(message="Webhook data source was not found.")
        
    return await service.process_webhook_payload(ds.organization_id, source_id, payload)


@router.get(
    "/organizations/{org_id}/events",
    response_model=List[EventResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def list_workspace_events(
    org_id: uuid.UUID,
    limit: int = 100,
    skip: int = 0,
    db=Depends(get_db),
) -> List[EventResponse]:
    """Retrieve historical chronologically ordered analytics events for a tenant. Requires Analyst clearance."""
    service = EventService(db)
    return await service.get_org_events(org_id, limit=limit, skip=skip)
