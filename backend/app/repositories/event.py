from typing import List, Dict, Any
import uuid
from sqlalchemy import insert, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.event import Event


class EventRepository(BaseRepository[Event]):
    """Repository handling analytical operations on partitioned Event logs."""

    def __init__(self, session: AsyncSession):
        super().__init__(Event, session)

    async def bulk_insert_events(self, events: List[Dict[str, Any]]) -> None:
        """Execute a highly-optimized bulk insert of events into partitioned tables."""
        if not events:
            return
        
        # Executes batch parameterized INSERT statement
        await self.session.execute(insert(Event), events)
        await self.session.commit()

    async def get_by_org(
        self, organization_id: uuid.UUID, limit: int = 100, skip: int = 0
    ) -> List[Event]:
        """Fetch chronologically ordered events for a tenant."""
        stmt = (
            select(Event)
            .where(Event.organization_id == organization_id)
            .order_by(desc(Event.timestamp))
            .offset(skip)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
