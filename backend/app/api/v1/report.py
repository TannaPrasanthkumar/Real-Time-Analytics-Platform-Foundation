import uuid
from typing import List
import os
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_db, RequireRole
from app.models.user import UserRole
from app.schemas.report import (
    ReportScheduleCreate,
    ReportScheduleUpdate,
    ReportScheduleOut,
    ReportHistoryOut
)
from app.services.report import ReportService

router = APIRouter(tags=["Reports"])


# ------------------------------------------------------------------------------
# Report Schedule Endpoints
# ------------------------------------------------------------------------------

@router.post(
    "/organizations/{org_id}/reports/schedules",
    response_model=ReportScheduleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def create_report_schedule(
    org_id: uuid.UUID,
    schema: ReportScheduleCreate,
    db=Depends(get_db)
) -> ReportScheduleOut:
    """Create a new recurring report schedule. Requires Analyst role or higher."""
    service = ReportService(db)
    return await service.create_schedule_for_org(org_id, schema)


@router.get(
    "/organizations/{org_id}/reports/schedules",
    response_model=List[ReportScheduleOut],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def list_report_schedules(
    org_id: uuid.UUID,
    db=Depends(get_db)
) -> List[ReportScheduleOut]:
    """List all report schedules for the organization. Requires Viewer role or higher."""
    service = ReportService(db)
    return await service.get_multi_schedules_for_org(org_id)


@router.get(
    "/organizations/{org_id}/reports/schedules/{schedule_id}",
    response_model=ReportScheduleOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def get_report_schedule(
    org_id: uuid.UUID,
    schedule_id: uuid.UUID,
    db=Depends(get_db)
) -> ReportScheduleOut:
    """Get a single report schedule by ID. Requires Viewer role or higher."""
    service = ReportService(db)
    return await service.get_schedule_for_org(org_id, schedule_id)


@router.put(
    "/organizations/{org_id}/reports/schedules/{schedule_id}",
    response_model=ReportScheduleOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def update_report_schedule(
    org_id: uuid.UUID,
    schedule_id: uuid.UUID,
    schema: ReportScheduleUpdate,
    db=Depends(get_db)
) -> ReportScheduleOut:
    """Update a report schedule. Requires Analyst role or higher."""
    service = ReportService(db)
    return await service.update_schedule_for_org(org_id, schedule_id, schema)


@router.delete(
    "/organizations/{org_id}/reports/schedules/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def delete_report_schedule(
    org_id: uuid.UUID,
    schedule_id: uuid.UUID,
    db=Depends(get_db)
) -> None:
    """Soft delete a report schedule. Requires Analyst role or higher."""
    service = ReportService(db)
    await service.delete_schedule_for_org(org_id, schedule_id)


@router.post(
    "/organizations/{org_id}/reports/schedules/{schedule_id}/trigger",
    response_model=ReportHistoryOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def trigger_report_schedule(
    org_id: uuid.UUID,
    schedule_id: uuid.UUID,
    db=Depends(get_db)
) -> ReportHistoryOut:
    """Manually trigger instant evaluation and snapshot generation of a report. Requires Analyst role or higher."""
    service = ReportService(db)
    # Perform instant synchronous compilation for testing and immediate feedback loop
    return await service.generate_dashboard_report(schedule_id)


# ------------------------------------------------------------------------------
# Report History & Archive Endpoints
# ------------------------------------------------------------------------------

@router.get(
    "/organizations/{org_id}/reports/history",
    response_model=List[ReportHistoryOut],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def list_report_history(
    org_id: uuid.UUID,
    db=Depends(get_db)
) -> List[ReportHistoryOut]:
    """List all historical report audits for the organization. Requires Viewer role or higher."""
    service = ReportService(db)
    return await service.get_multi_histories_for_org(org_id)


@router.get(
    "/organizations/{org_id}/reports/history/{history_id}/download",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def download_report_snapshot(
    org_id: uuid.UUID,
    history_id: uuid.UUID,
    db=Depends(get_db)
) -> FileResponse:
    """Download a compiled HTML report snapshot file. Requires Viewer role or higher."""
    service = ReportService(db)
    history = await service.get_history_for_org(org_id, history_id)
    if not history.file_path or not os.path.exists(history.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compiled report file snapshot was not found on local disk storage."
        )
    return FileResponse(
        path=history.file_path,
        media_type="text/html",
        filename=os.path.basename(history.file_path)
    )
