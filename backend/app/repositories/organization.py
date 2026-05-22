from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.organization import Organization


class OrganizationRepository(BaseRepository[Organization]):
    """Repository handling database interactions for Multi-Tenant Organizations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Organization, session)

    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        """Fetch active organization by unique workspace routing URL slug."""
        stmt = select(Organization).where(
            Organization.slug == slug, Organization.is_deleted == False
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
