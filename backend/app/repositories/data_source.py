from typing import Optional, List
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.data_source import DataSource


class DataSourceRepository(BaseRepository[DataSource]):
    """Repository handling database queries for DataSource records."""

    def __init__(self, session: AsyncSession):
        super().__init__(DataSource, session)

    async def get_by_org(self, organization_id: uuid.UUID) -> List[DataSource]:
        """Fetch all active data sources for an organization."""
        stmt = select(DataSource).where(
            DataSource.organization_id == organization_id,
            DataSource.is_deleted == False,
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_by_org_and_id(
        self, organization_id: uuid.UUID, data_source_id: uuid.UUID
    ) -> Optional[DataSource]:
        """Fetch a specific active data source within an organization."""
        stmt = select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.organization_id == organization_id,
            DataSource.is_deleted == False,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
