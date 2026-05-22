from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.alert import AlertRule, AlertHistory


class AlertRuleRepository(BaseRepository[AlertRule]):
    """Repository handling database operations for metric Alert Rules."""

    def __init__(self, session: AsyncSession):
        super().__init__(AlertRule, session)

    async def get_by_org(
        self, organization_id: uuid.UUID, rule_id: uuid.UUID, include_deleted: bool = False
    ) -> Optional[AlertRule]:
        """Fetch a single alert rule by ID under organization boundaries."""
        stmt = select(AlertRule).where(
            AlertRule.id == rule_id,
            AlertRule.organization_id == organization_id
        )
        if not include_deleted:
            stmt = stmt.where(AlertRule.is_deleted == False)

        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_multi_by_org(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> List[AlertRule]:
        """Fetch multiple alert rules belonging to a specific organization."""
        stmt = select(AlertRule).where(
            AlertRule.organization_id == organization_id
        ).offset(skip).limit(limit)

        if not include_deleted:
            stmt = stmt.where(AlertRule.is_deleted == False)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_all_enabled(self) -> List[AlertRule]:
        """Fetch all enabled alert rules globally (used by background scanner task)."""
        stmt = select(AlertRule).where(
            AlertRule.is_enabled == True,
            AlertRule.is_deleted == False
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class AlertHistoryRepository(BaseRepository[AlertHistory]):
    """Repository handling database operations for Alert History logging."""

    def __init__(self, session: AsyncSession):
        super().__init__(AlertHistory, session)

    async def get_by_org(
        self, organization_id: uuid.UUID, history_id: uuid.UUID, include_deleted: bool = False
    ) -> Optional[AlertHistory]:
        """Fetch a single alert history record under organization boundaries."""
        stmt = select(AlertHistory).where(
            AlertHistory.id == history_id,
            AlertHistory.organization_id == organization_id
        )
        if not include_deleted:
            stmt = stmt.where(AlertHistory.is_deleted == False)

        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_multi_by_org(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> List[AlertHistory]:
        """Fetch multiple alert history logs belonging to a specific organization."""
        stmt = select(AlertHistory).where(
            AlertHistory.organization_id == organization_id
        ).order_by(AlertHistory.created_at.desc()).offset(skip).limit(limit)

        if not include_deleted:
            stmt = stmt.where(AlertHistory.is_deleted == False)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())
