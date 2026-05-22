from typing import Optional, List
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.api_key import APIKey


class APIKeyRepository(BaseRepository[APIKey]):
    """Repository handling database queries for APIKey records."""

    def __init__(self, session: AsyncSession):
        super().__init__(APIKey, session)

    async def get_by_prefix(self, prefix: str) -> Optional[APIKey]:
        """Fetch active API key by its prefix."""
        stmt = select(APIKey).where(
            APIKey.prefix == prefix,
            APIKey.is_active == True,
            APIKey.is_deleted == False,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_org(self, organization_id: uuid.UUID) -> List[APIKey]:
        """Fetch all active API keys for an organization."""
        stmt = select(APIKey).where(
            APIKey.organization_id == organization_id,
            APIKey.is_deleted == False,
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
