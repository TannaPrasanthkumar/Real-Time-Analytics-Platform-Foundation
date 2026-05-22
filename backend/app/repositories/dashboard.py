from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.dashboard import Dashboard, Widget


class DashboardRepository(BaseRepository[Dashboard]):
    """Repository handling database interactions for customizable Dashboards."""

    def __init__(self, session: AsyncSession):
        super().__init__(Dashboard, session)

    async def get_by_org(
        self, organization_id: uuid.UUID, dashboard_id: uuid.UUID, include_deleted: bool = False
    ) -> Optional[Dashboard]:
        """Fetch a single dashboard by ID within tenant boundaries, preloading widgets."""
        stmt = select(Dashboard).where(
            Dashboard.id == dashboard_id,
            Dashboard.organization_id == organization_id
        ).options(selectinload(Dashboard.widgets))

        if not include_deleted:
            stmt = stmt.where(Dashboard.is_deleted == False)

        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_multi_by_org(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> List[Dashboard]:
        """Fetch multiple dashboards under a specific organization tenant."""
        stmt = select(Dashboard).where(
            Dashboard.organization_id == organization_id
        ).offset(skip).limit(limit)

        if not include_deleted:
            stmt = stmt.where(Dashboard.is_deleted == False)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_by_share_token(self, share_token: str) -> Optional[Dashboard]:
        """Fetch a publicly shared dashboard by its unique cryptographic share token."""
        stmt = select(Dashboard).where(
            Dashboard.share_token == share_token,
            Dashboard.is_public == True,
            Dashboard.is_deleted == False
        ).options(selectinload(Dashboard.widgets))

        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


class WidgetRepository(BaseRepository[Widget]):
    """Repository handling database interactions for individual Widgets."""

    def __init__(self, session: AsyncSession):
        super().__init__(Widget, session)

    async def get_by_dashboard(
        self, dashboard_id: uuid.UUID, widget_id: uuid.UUID, include_deleted: bool = False
    ) -> Optional[Widget]:
        """Fetch a single widget under a specific dashboard parent."""
        stmt = select(Widget).where(
            Widget.id == widget_id,
            Widget.dashboard_id == dashboard_id
        )

        if not include_deleted:
            stmt = stmt.where(Widget.is_deleted == False)

        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_multi_by_dashboard(
        self, dashboard_id: uuid.UUID, include_deleted: bool = False
    ) -> List[Widget]:
        """Fetch all widgets belonging to a specific dashboard parent."""
        stmt = select(Widget).where(
            Widget.dashboard_id == dashboard_id
        )

        if not include_deleted:
            stmt = stmt.where(Widget.is_deleted == False)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())
