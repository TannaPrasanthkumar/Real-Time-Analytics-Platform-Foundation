from typing import Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.user import User, UserOrganization


class UserRepository(BaseRepository[User]):
    """Repository handling all database inquiries relating to User records."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Fetch active user by email utilizing lower case normalization."""
        stmt = select(User).where(
            User.email == email.lower(), User.is_deleted == False
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_membership(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Optional[UserOrganization]:
        """Fetch active membership entry linking a user to a specific organization."""
        stmt = select(UserOrganization).where(
            UserOrganization.user_id == user_id,
            UserOrganization.organization_id == organization_id,
            UserOrganization.is_deleted == False,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
