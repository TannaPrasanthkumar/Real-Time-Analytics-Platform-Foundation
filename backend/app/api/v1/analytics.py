from datetime import datetime, timedelta, timezone
import uuid
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_db, RequireRole
from app.models.user import UserRole
from app.schemas.analytics import (
    MetricOverview,
    TimeseriesResponse,
    BreakdownResponse,
    TimeInterval,
    MetricType,
    TimeseriesPoint,
    BreakdownItem,
)
from app.services.analytics import AnalyticsService

router = APIRouter(tags=["Analytics & Reporting"])


def _resolve_default_dates(
    start_time: datetime | None, end_time: datetime | None
) -> tuple[datetime, datetime]:
    """Helper to resolve default date bounds (defaults to past 30 days if unspecified)."""
    now = datetime.now(timezone.utc)
    resolved_end = end_time if end_time else now
    resolved_start = start_time if start_time else resolved_end - timedelta(days=30)
    
    # Ensure they are timezone aware
    if resolved_start.tzinfo is None:
        resolved_start = resolved_start.replace(tzinfo=timezone.utc)
    if resolved_end.tzinfo is None:
        resolved_end = resolved_end.replace(tzinfo=timezone.utc)
        
    return resolved_start, resolved_end


@router.get(
    "/organizations/{org_id}/analytics/overview",
    response_model=MetricOverview,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def get_analytics_overview(
    org_id: uuid.UUID,
    start_time: datetime | None = Query(default=None, description="Start range timestamp (UTC)"),
    end_time: datetime | None = Query(default=None, description="End range timestamp (UTC)"),
    use_cache: bool = Query(default=True, description="Enable Redis caching"),
    db=Depends(get_db),
) -> MetricOverview:
    """Fetch total metrics (Page Views, UVs, Bounce Rate, Duration) with period-over-period differences. Required: Viewer."""
    resolved_start, resolved_end = _resolve_default_dates(start_time, end_time)
    service = AnalyticsService(db)
    res = await service.get_overview(org_id, resolved_start, resolved_end, use_cache)
    return MetricOverview(**res)


@router.get(
    "/organizations/{org_id}/analytics/timeseries",
    response_model=TimeseriesResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def get_analytics_timeseries(
    org_id: uuid.UUID,
    metric: MetricType = Query(..., description="Target analytical metric type"),
    interval: TimeInterval = Query(default=TimeInterval.DAY, description="Time bucket interval"),
    start_time: datetime | None = Query(default=None, description="Start range timestamp (UTC)"),
    end_time: datetime | None = Query(default=None, description="End range timestamp (UTC)"),
    use_cache: bool = Query(default=True, description="Enable Redis caching"),
    db=Depends(get_db),
) -> TimeseriesResponse:
    """Fetch bucketed metric values alongside window-based rolling moving averages. Required: Viewer."""
    resolved_start, resolved_end = _resolve_default_dates(start_time, end_time)
    service = AnalyticsService(db)
    points_raw = await service.get_timeseries(
        org_id, resolved_start, resolved_end, interval.value, metric.value, use_cache
    )
    points = [TimeseriesPoint(**p) for p in points_raw]
    return TimeseriesResponse(metric=metric, interval=interval, points=points)


@router.get(
    "/organizations/{org_id}/analytics/breakdown",
    response_model=BreakdownResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def get_analytics_breakdown(
    org_id: uuid.UUID,
    property_key: str = Query(..., min_length=1, description="Payload JSONB key to segment"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum categories to retrieve"),
    start_time: datetime | None = Query(default=None, description="Start range timestamp (UTC)"),
    end_time: datetime | None = Query(default=None, description="End range timestamp (UTC)"),
    use_cache: bool = Query(default=True, description="Enable Redis caching"),
    db=Depends(get_db),
) -> BreakdownResponse:
    """Fetch event payload property segment breakdown with weight percentages. Required: Viewer."""
    resolved_start, resolved_end = _resolve_default_dates(start_time, end_time)
    service = AnalyticsService(db)
    items_raw = await service.get_breakdown(
        org_id, resolved_start, resolved_end, property_key, limit, use_cache
    )
    items = [BreakdownItem(**i) for i in items_raw]
    return BreakdownResponse(property_key=property_key, items=items)
