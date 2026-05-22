from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.report import ReportSchedule, ReportHistory


class ReportScheduleRepository(BaseRepository[ReportSchedule]):
    """Repository handling database operations for Report Schedules."""

    def __init__(self, session: AsyncSession):
        super().__init__(ReportSchedule, session)

    async def get_by_org(
        self, organization_id: uuid.UUID, schedule_id: uuid.UUID, include_deleted: bool = False
    ) -> Optional[ReportSchedule]:
        """Fetch a single report schedule by ID under organization boundaries."""
        stmt = select(ReportSchedule).where(
            ReportSchedule.id == schedule_id,
            ReportSchedule.organization_id == organization_id
        )
        if not include_deleted:
            stmt = stmt.where(ReportSchedule.is_deleted == False)

        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_multi_by_org(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> List[ReportSchedule]:
        """Fetch multiple report schedules belonging to a specific organization."""
        stmt = select(ReportSchedule).where(
            ReportSchedule.organization_id == organization_id
        ).offset(skip).limit(limit)

        if not include_deleted:
            stmt = stmt.where(ReportSchedule.is_deleted == False)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_all_active(self) -> List[ReportSchedule]:
        """Fetch all active, non-deleted report schedules globally (used by periodic task)."""
        stmt = select(ReportSchedule).where(
            ReportSchedule.is_active == True,
            ReportSchedule.is_deleted == False
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class ReportHistoryRepository(BaseRepository[ReportHistory]):
    """Repository handling database operations for Report History."""

    def __init__(self, session: AsyncSession):
        super().__init__(ReportHistory, session)

    async def get_by_org(
        self, organization_id: uuid.UUID, history_id: uuid.UUID, include_deleted: bool = False
    ) -> Optional[ReportHistory]:
        """Fetch a single report history record under organization boundaries."""
        stmt = select(ReportHistory).where(
            ReportHistory.id == history_id,
            ReportHistory.organization_id == organization_id
        )
        if not include_deleted:
            stmt = stmt.where(ReportHistory.is_deleted == False)

        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_multi_by_org(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> List[ReportHistory]:
        """Fetch multiple report history logs belonging to a specific organization."""
        stmt = select(ReportHistory).where(
            ReportHistory.organization_id == organization_id
        ).order_by(ReportHistory.triggered_at.desc()).offset(skip).limit(limit)

        if not include_deleted:
            stmt = stmt.where(ReportHistory.is_deleted == False)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())
