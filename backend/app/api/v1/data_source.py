import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, status

from app.api.deps import get_db, RequireRole
from app.models.user import UserRole
from app.schemas.data_source import DataSourceCreate, DataSourceUpdate, DataSourceResponse
from app.services.data_source import DataSourceService

router = APIRouter(tags=["Data Sources"])


@router.post(
    "/organizations/{org_id}/data-sources",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def create_data_source(
    org_id: uuid.UUID,
    schema: DataSourceCreate,
    db=Depends(get_db),
) -> DataSourceResponse:
    """Create a new data source (API, CSV, Webhook) under an organization. Requires Analyst clearance."""
    service = DataSourceService(db)
    return await service.create_source(org_id, schema)


@router.get(
    "/organizations/{org_id}/data-sources",
    response_model=List[DataSourceResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def list_data_sources(
    org_id: uuid.UUID,
    db=Depends(get_db),
) -> List[DataSourceResponse]:
    """List all active data sources for an organization. Requires Viewer clearance."""
    service = DataSourceService(db)
    return await service.get_org_sources(org_id)


@router.get(
    "/organizations/{org_id}/data-sources/{source_id}",
    response_model=DataSourceResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def get_data_source(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    db=Depends(get_db),
) -> DataSourceResponse:
    """Get active details of a specific data source. Requires Viewer clearance."""
    service = DataSourceService(db)
    return await service.get_org_source(org_id, source_id)


@router.put(
    "/organizations/{org_id}/data-sources/{source_id}",
    response_model=DataSourceResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def update_data_source(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    schema: DataSourceUpdate,
    db=Depends(get_db),
) -> DataSourceResponse:
    """Update configurations of an existing data source. Requires Analyst clearance."""
    service = DataSourceService(db)
    return await service.update_source(org_id, source_id, schema)


@router.delete(
    "/organizations/{org_id}/data-sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def delete_data_source(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    db=Depends(get_db),
) -> None:
    """Soft-delete an existing data source. Requires Analyst clearance."""
    service = DataSourceService(db)
    await service.delete_source(org_id, source_id)


@router.post(
    "/organizations/{org_id}/data-sources/{source_id}/upload-csv",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def upload_csv_file(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    file: UploadFile = File(...),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Upload and asynchronously ingest analytics events parsed from a CSV file. Requires Analyst clearance."""
    service = DataSourceService(db)
    content = await file.read()
    csv_text = content.decode("utf-8")
    return await service.process_csv_upload(org_id, source_id, csv_text)
