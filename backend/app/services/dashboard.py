import secrets
from typing import List, Optional, Union, Dict, Any
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.repositories.dashboard import DashboardRepository, WidgetRepository
from app.models.dashboard import Dashboard, Widget
from app.schemas.dashboard import DashboardCreate, DashboardUpdate, WidgetCreate, WidgetUpdate
from app.core.exceptions import NotFoundException


class DashboardService(BaseService[Dashboard, DashboardRepository]):
    """Service orchestrating customizable dashboards, layouts, public sharing, and widgets CRUD."""

    def __init__(self, session: AsyncSession):
        super().__init__(DashboardRepository(session))
        self.widget_repository = WidgetRepository(session)
        self.session = session

    async def get_dashboard_for_org(self, organization_id: uuid.UUID, dashboard_id: uuid.UUID) -> Dashboard:
        """Fetch dashboard strictly inside organizational tenant boundary."""
        dashboard = await self.repository.get_by_org(organization_id, dashboard_id)
        if not dashboard:
            raise NotFoundException(
                message=f"Dashboard with ID '{dashboard_id}' was not found in this organization."
            )
        return dashboard

    async def get_multi_dashboards_for_org(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[Dashboard]:
        """Fetch multiple dashboards under a specific organization tenant."""
        return await self.repository.get_multi_by_org(organization_id, skip=skip, limit=limit)

    async def create_dashboard_for_org(self, organization_id: uuid.UUID, schema: DashboardCreate) -> Dashboard:
        """Create a new custom dashboard linked to the tenant organization."""
        obj_data = schema.model_dump()
        obj_data["organization_id"] = organization_id
        obj_data["share_token"] = None
        return await self.repository.create(obj_data)

    async def update_dashboard_for_org(
        self, organization_id: uuid.UUID, dashboard_id: uuid.UUID, schema: DashboardUpdate
    ) -> Dashboard:
        """Update a dashboard layout or metadata strictly inside organizational boundaries."""
        dashboard = await self.get_dashboard_for_org(organization_id, dashboard_id)
        return await self.repository.update(dashboard, schema)

    async def delete_dashboard_for_org(self, organization_id: uuid.UUID, dashboard_id: uuid.UUID) -> Dashboard:
        """Soft delete a dashboard strictly inside organizational boundaries."""
        dashboard = await self.get_dashboard_for_org(organization_id, dashboard_id)
        return await self.repository.soft_delete(dashboard)

    async def toggle_dashboard_sharing(
        self, organization_id: uuid.UUID, dashboard_id: uuid.UUID, is_public: bool
    ) -> Dashboard:
        """Toggle dashboard public visibility, allocating/clearing secure share tokens."""
        dashboard = await self.get_dashboard_for_org(organization_id, dashboard_id)
        
        share_token = secrets.token_urlsafe(32) if is_public else None
        update_data = {
            "is_public": is_public,
            "share_token": share_token
        }
        return await self.repository.update(dashboard, update_data)

    async def get_dashboard_by_share_token(self, share_token: str) -> Dashboard:
        """Retrieve a publicly shared dashboard layout by its unique share token."""
        dashboard = await self.repository.get_by_share_token(share_token)
        if not dashboard:
            raise NotFoundException(
                message="Requested public dashboard was not found or is no longer shared."
            )
        return dashboard

    # --------------------------------------------------------------------------
    # Dashboard Templates Provisioning
    # --------------------------------------------------------------------------

    async def create_dashboard_template(
        self, organization_id: uuid.UUID, template_name: str
    ) -> Dashboard:
        """Provision a template dashboard preconfigured with analytical widgets."""
        if template_name.lower() != "web_analytics":
            raise NotFoundException(message=f"Template type '{template_name}' is not supported.")

        # Create basic Web Analytics dashboard
        dashboard_data = {
            "organization_id": organization_id,
            "name": "Web Analytics Console",
            "description": "Preconfigured telemetry console tracking Pageviews, Bounces, DAUs, and Browser splits.",
            "is_public": False,
            "share_token": None
        }
        dashboard = await self.repository.create(dashboard_data)

        # Standard widget set
        widgets_to_create = [
            {
                "dashboard_id": dashboard.id,
                "name": "Page Views",
                "type": "kpi",
                "layout": {"x": 0, "y": 0, "w": 3, "h": 2},
                "query_config": {"metric_type": "page_views", "time_range": "24h"}
            },
            {
                "dashboard_id": dashboard.id,
                "name": "Unique Visitors",
                "type": "kpi",
                "layout": {"x": 3, "y": 0, "w": 3, "h": 2},
                "query_config": {"metric_type": "unique_visitors", "time_range": "24h"}
            },
            {
                "dashboard_id": dashboard.id,
                "name": "Bounce Rate",
                "type": "kpi",
                "layout": {"x": 6, "y": 0, "w": 3, "h": 2},
                "query_config": {"metric_type": "bounce_rate", "time_range": "24h"}
            },
            {
                "dashboard_id": dashboard.id,
                "name": "Average Session Duration",
                "type": "kpi",
                "layout": {"x": 9, "y": 0, "w": 3, "h": 2},
                "query_config": {"metric_type": "avg_session_duration", "time_range": "24h"}
            },
            {
                "dashboard_id": dashboard.id,
                "name": "Hourly Page Views Trend",
                "type": "line",
                "layout": {"x": 0, "y": 2, "w": 8, "h": 4},
                "query_config": {"metric_type": "page_views", "interval": "hour", "time_range": "24h"}
            },
            {
                "dashboard_id": dashboard.id,
                "name": "Browser Segmentation Breakdown",
                "type": "pie",
                "layout": {"x": 8, "y": 2, "w": 4, "h": 4},
                "query_config": {"property_key": "browser", "limit": 5}
            }
        ]

        # Insert widgets sequentially into database
        for w_data in widgets_to_create:
            await self.widget_repository.create(w_data)

        # Refresh dashboard with loaded widgets
        return await self.get_dashboard_for_org(organization_id, dashboard.id)

    # --------------------------------------------------------------------------
    # Widgets CRUD Operations
    # --------------------------------------------------------------------------

    async def add_widget_to_dashboard(
        self, organization_id: uuid.UUID, dashboard_id: uuid.UUID, schema: WidgetCreate
    ) -> Widget:
        """Add a new widget to an existing organization dashboard parent."""
        # Enforce that parent dashboard exists under this organization
        await self.get_dashboard_for_org(organization_id, dashboard_id)

        obj_data = schema.model_dump()
        obj_data["dashboard_id"] = dashboard_id
        return await self.widget_repository.create(obj_data)

    async def update_dashboard_widget(
        self, organization_id: uuid.UUID, dashboard_id: uuid.UUID, widget_id: uuid.UUID, schema: WidgetUpdate
    ) -> Widget:
        """Update a widget parameters and coordinates within tenant organization bounds."""
        # Enforce that dashboard exists under organization
        await self.get_dashboard_for_org(organization_id, dashboard_id)

        widget = await self.widget_repository.get_by_dashboard(dashboard_id, widget_id)
        if not widget:
            raise NotFoundException(
                message=f"Widget with ID '{widget_id}' was not found in this dashboard."
            )

        return await self.widget_repository.update(widget, schema)

    async def delete_dashboard_widget(
        self, organization_id: uuid.UUID, dashboard_id: uuid.UUID, widget_id: uuid.UUID
    ) -> Widget:
        """Soft delete a widget from a tenant organization dashboard."""
        # Enforce dashboard ownership
        await self.get_dashboard_for_org(organization_id, dashboard_id)

        widget = await self.widget_repository.get_by_dashboard(dashboard_id, widget_id)
        if not widget:
            raise NotFoundException(
                message=f"Widget with ID '{widget_id}' was not found in this dashboard."
            )

        return await self.widget_repository.soft_delete(widget)
