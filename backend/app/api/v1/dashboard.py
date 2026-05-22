import uuid
from typing import List
from fastapi import APIRouter, Depends, status, Path

from app.api.deps import get_db, RequireRole
from app.models.user import UserRole
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardUpdate,
    DashboardOut,
    DashboardFullOut,
    DashboardShareUpdate,
    WidgetCreate,
    WidgetUpdate,
    WidgetOut
)
from app.services.dashboard import DashboardService

router = APIRouter(tags=["Dashboards"])


# ------------------------------------------------------------------------------
# Dashboard Endpoints
# ------------------------------------------------------------------------------

@router.post(
    "/organizations/{org_id}/dashboards",
    response_model=DashboardOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def create_dashboard(
    org_id: uuid.UUID,
    schema: DashboardCreate,
    db=Depends(get_db)
) -> DashboardOut:
    """Create a new custom dashboard. Requires Analyst role or higher."""
    service = DashboardService(db)
    return await service.create_dashboard_for_org(org_id, schema)


@router.post(
    "/organizations/{org_id}/dashboards/templates/{template_name}",
    response_model=DashboardFullOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def provision_dashboard_template(
    org_id: uuid.UUID,
    template_name: str = Path(..., description="Currently only 'web_analytics' is supported."),
    db=Depends(get_db)
) -> DashboardFullOut:
    """Provision a dashboard pre-populated with standard analytical widgets. Requires Analyst role."""
    service = DashboardService(db)
    return await service.create_dashboard_template(org_id, template_name)


@router.get(
    "/organizations/{org_id}/dashboards",
    response_model=List[DashboardOut],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def list_dashboards(
    org_id: uuid.UUID,
    db=Depends(get_db)
) -> List[DashboardOut]:
    """List all dashboards in the organization. Requires Viewer role or higher."""
    service = DashboardService(db)
    return await service.get_multi_dashboards_for_org(org_id)


@router.get(
    "/organizations/{org_id}/dashboards/{dashboard_id}",
    response_model=DashboardFullOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.VIEWER))],
)
async def get_dashboard(
    org_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    db=Depends(get_db)
) -> DashboardFullOut:
    """Get a detailed dashboard with its nested widgets. Requires Viewer role or higher."""
    service = DashboardService(db)
    return await service.get_dashboard_for_org(org_id, dashboard_id)


@router.put(
    "/organizations/{org_id}/dashboards/{dashboard_id}",
    response_model=DashboardOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def update_dashboard(
    org_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    schema: DashboardUpdate,
    db=Depends(get_db)
) -> DashboardOut:
    """Update a dashboard layout/metadata. Requires Analyst role or higher."""
    service = DashboardService(db)
    return await service.update_dashboard_for_org(org_id, dashboard_id, schema)


@router.delete(
    "/organizations/{org_id}/dashboards/{dashboard_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def delete_dashboard(
    org_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    db=Depends(get_db)
) -> None:
    """Soft delete a dashboard. Requires Analyst role or higher."""
    service = DashboardService(db)
    await service.delete_dashboard_for_org(org_id, dashboard_id)


@router.post(
    "/organizations/{org_id}/dashboards/{dashboard_id}/share",
    response_model=DashboardOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def toggle_sharing(
    org_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    schema: DashboardShareUpdate,
    db=Depends(get_db)
) -> DashboardOut:
    """Toggle public sharing of a dashboard. Requires Analyst role or higher."""
    service = DashboardService(db)
    return await service.toggle_dashboard_sharing(org_id, dashboard_id, schema.is_public)


@router.get(
    "/dashboards/share/{share_token}",
    response_model=DashboardFullOut,
    status_code=status.HTTP_200_OK,
)
async def get_shared_dashboard(
    share_token: str,
    db=Depends(get_db)
) -> DashboardFullOut:
    """Public read-only route to retrieve a shared dashboard using its cryptographic token."""
    service = DashboardService(db)
    return await service.get_dashboard_by_share_token(share_token)


# ------------------------------------------------------------------------------
# Widget Endpoints
# ------------------------------------------------------------------------------

@router.post(
    "/organizations/{org_id}/dashboards/{dashboard_id}/widgets",
    response_model=WidgetOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def add_widget(
    org_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    schema: WidgetCreate,
    db=Depends(get_db)
) -> WidgetOut:
    """Add a new widget to a dashboard. Requires Analyst role or higher."""
    service = DashboardService(db)
    return await service.add_widget_to_dashboard(org_id, dashboard_id, schema)


@router.put(
    "/organizations/{org_id}/dashboards/{dashboard_id}/widgets/{widget_id}",
    response_model=WidgetOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def update_widget(
    org_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    widget_id: uuid.UUID,
    schema: WidgetUpdate,
    db=Depends(get_db)
) -> WidgetOut:
    """Update widget configuration or coordinates. Requires Analyst role or higher."""
    service = DashboardService(db)
    return await service.update_dashboard_widget(org_id, dashboard_id, widget_id, schema)


@router.delete(
    "/organizations/{org_id}/dashboards/{dashboard_id}/widgets/{widget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequireRole(UserRole.ANALYST))],
)
async def delete_widget(
    org_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    widget_id: uuid.UUID,
    db=Depends(get_db)
) -> None:
    """Soft delete a widget. Requires Analyst role or higher."""
    service = DashboardService(db)
    await service.delete_dashboard_widget(org_id, dashboard_id, widget_id)


# ------------------------------------------------------------------------------
# Public Shared Dashboard Analytics Endpoints (Unauthenticated)
# ------------------------------------------------------------------------------

from datetime import datetime, timedelta, timezone
from app.schemas.analytics import (
    MetricOverview,
    TimeseriesResponse,
    BreakdownResponse,
    MetricType,
    TimeInterval,
    TimeseriesPoint,
    BreakdownItem,
)
from app.services.analytics import AnalyticsService
from fastapi import Query

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
    "/dashboards/share/{share_token}/overview",
    response_model=MetricOverview,
    status_code=status.HTTP_200_OK,
)
async def get_shared_analytics_overview(
    share_token: str,
    start_time: datetime | None = Query(default=None, description="Start range timestamp (UTC)"),
    end_time: datetime | None = Query(default=None, description="End range timestamp (UTC)"),
    db=Depends(get_db)
) -> MetricOverview:
    """Fetch total metrics for a shared dashboard without auth bounds."""
    dash_service = DashboardService(db)
    dashboard = await dash_service.get_dashboard_by_share_token(share_token)
    
    resolved_start, resolved_end = _resolve_default_dates(start_time, end_time)
    analytics_service = AnalyticsService(db)
    res = await analytics_service.get_overview(dashboard.organization_id, resolved_start, resolved_end, use_cache=True)
    return MetricOverview(**res)


@router.get(
    "/dashboards/share/{share_token}/timeseries",
    response_model=TimeseriesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_shared_analytics_timeseries(
    share_token: str,
    metric: MetricType = Query(..., description="Target analytical metric type"),
    interval: TimeInterval = Query(default=TimeInterval.DAY, description="Time bucket interval"),
    start_time: datetime | None = Query(default=None, description="Start range timestamp (UTC)"),
    end_time: datetime | None = Query(default=None, description="End range timestamp (UTC)"),
    db=Depends(get_db)
) -> TimeseriesResponse:
    """Fetch bucketed metric timeseries for a shared dashboard without auth bounds."""
    dash_service = DashboardService(db)
    dashboard = await dash_service.get_dashboard_by_share_token(share_token)
    
    resolved_start, resolved_end = _resolve_default_dates(start_time, end_time)
    analytics_service = AnalyticsService(db)
    points_raw = await analytics_service.get_timeseries(
        dashboard.organization_id, resolved_start, resolved_end, interval.value, metric.value, use_cache=True
    )
    points = [TimeseriesPoint(**p) for p in points_raw]
    return TimeseriesResponse(metric=metric, interval=interval, points=points)


@router.get(
    "/dashboards/share/{share_token}/breakdown",
    response_model=BreakdownResponse,
    status_code=status.HTTP_200_OK,
)
async def get_shared_analytics_breakdown(
    share_token: str,
    property_key: str = Query(..., min_length=1, description="Payload JSONB key to segment"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum categories to retrieve"),
    start_time: datetime | None = Query(default=None, description="Start range timestamp (UTC)"),
    end_time: datetime | None = Query(default=None, description="End range timestamp (UTC)"),
    db=Depends(get_db)
) -> BreakdownResponse:
    """Fetch event payload property segment breakdown for a shared dashboard without auth bounds."""
    dash_service = DashboardService(db)
    dashboard = await dash_service.get_dashboard_by_share_token(share_token)
    
    resolved_start, resolved_end = _resolve_default_dates(start_time, end_time)
    analytics_service = AnalyticsService(db)
    items_raw = await analytics_service.get_breakdown(
        dashboard.organization_id, resolved_start, resolved_end, property_key, limit, use_cache=True
    )
    items = [BreakdownItem(**i) for i in items_raw]
    return BreakdownResponse(property_key=property_key, items=items)
