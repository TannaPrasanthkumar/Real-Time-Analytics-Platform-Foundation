import re
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.repositories.organization import OrganizationRepository
from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate
from app.core.exceptions import NotFoundException


class OrganizationService(BaseService[Organization, OrganizationRepository]):
    """Service orchestrating workspaces, slug resolution, and tenant provisionings."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(OrganizationRepository(session))

    async def get_by_slug(self, slug: str) -> Organization:
        """Fetch active organization by slug, raising NotFoundException on failure."""
        org = await self.repository.get_by_slug(slug)
        if not org:
            raise NotFoundException(
                message=f"Workspace with slug '{slug}' was not found."
            )
        return org

    async def _generate_unique_slug(self, name: str) -> str:
        """Normalize name into an alphanumeric slug and verify uniqueness."""
        # Normalize: lowercase, strip special characters, replace spaces with hyphen
        base_slug = name.lower()
        base_slug = re.sub(r"[^a-z0-9\s-]", "", base_slug)
        base_slug = re.sub(r"[\s-]+", "-", base_slug).strip("-")
        
        if not base_slug:
            base_slug = "org"
            
        slug = base_slug
        attempts = 0
        while attempts < 10:
            existing = await self.repository.get_by_slug(slug)
            if not existing:
                return slug
            # Append short random suffix on collisions
            slug = f"{base_slug}-{str(uuid.uuid4())[:4]}"
            attempts += 1
            
        return f"{base_slug}-{str(uuid.uuid4())[:8]}"

    async def create_organization(self, schema: OrganizationCreate) -> Organization:
        """Provision a new organization with a unique generated slug."""
        slug = await self._generate_unique_slug(schema.name)
        org_data = {
            "name": schema.name,
            "slug": slug,
            "is_active": True,
        }
        return await self.repository.create(org_data)
