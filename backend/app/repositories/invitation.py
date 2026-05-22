from typing import Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.invitation import Invitation


class InvitationRepository(BaseRepository[Invitation]):
    """Repository handling database operations for team workspace onboarding invitations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Invitation, session)

    async def get_by_token(self, token: str) -> Optional[Invitation]:
        """Retrieve active invitation by unique secure token."""
        stmt = select(Invitation).where(
            Invitation.token == token, Invitation.is_deleted == False
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_by_email_and_org(
        self, email: str, organization_id: uuid.UUID
    ) -> Optional[Invitation]:
        """Fetch active pending invitation for a specific email and workspace."""
        stmt = select(Invitation).where(
            Invitation.email == email.lower(),
            Invitation.organization_id == organization_id,
            Invitation.is_accepted == False,
            Invitation.is_deleted == False,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
