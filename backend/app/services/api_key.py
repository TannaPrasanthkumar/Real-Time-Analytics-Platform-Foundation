from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.repositories.api_key import APIKeyRepository
from app.models.api_key import APIKey
from app.schemas.api_key import APIKeyCreate
from app.core.exceptions import NotFoundException, BadRequestException


class APIKeyService(BaseService[APIKey, APIKeyRepository]):
    """Service orchestrating cryptographic API Key generation, verification, and rotation."""

    def __init__(self, session: AsyncSession):
        super().__init__(APIKeyRepository(session))

    async def create_key(
        self, organization_id: uuid.UUID, schema: APIKeyCreate
    ) -> APIKey:
        """Create a cryptographically secure, SHA-256 hashed API Key."""
        # 1. Generate unhashed API Key secret
        # pk_live_ prefix (8 chars) + 32 chars cryptographically secure hex = 40 characters
        raw_key = f"pk_live_{secrets.token_hex(16)}"
        
        # 2. Extract public lookup prefix (first 16 characters)
        prefix = raw_key[:16]
        
        # 3. Hash the key with SHA-256 for secure database storage
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # 4. Calculate expiration timestamp
        expires_at: Optional[datetime] = None
        if schema.expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=schema.expires_in_days)
            
        key_data = {
            "organization_id": organization_id,
            "name": schema.name,
            "prefix": prefix,
            "hashed_key": hashed_key,
            "is_active": True,
            "expires_at": expires_at,
        }
        
        # Create database record
        db_key = await self.repository.create(key_data)
        
        # Inject raw_key dynamically for single-time visibility at creation
        db_key.raw_key = raw_key  # type: ignore
        return db_key

    async def get_org_keys(self, organization_id: uuid.UUID) -> List[APIKey]:
        """Retrieve all active keys for a tenant organization."""
        return await self.repository.get_by_org(organization_id)

    async def revoke_key(
        self, organization_id: uuid.UUID, key_id: uuid.UUID
    ) -> None:
        """Permanently revoke (soft-delete) an API Key."""
        key = await self.repository.get(key_id)
        if not key or key.organization_id != organization_id or key.is_deleted:
            raise NotFoundException(message="API Key was not found.")
            
        await self.repository.soft_delete(key)

    async def rotate_key(
        self, organization_id: uuid.UUID, key_id: uuid.UUID
    ) -> APIKey:
        """Rotate an existing API key: revoking the old key and issuing a new one."""
        old_key = await self.repository.get(key_id)
        if not old_key or old_key.organization_id != organization_id or old_key.is_deleted:
            raise NotFoundException(message="API Key to rotate was not found.")
            
        # Revoke the old key
        await self.repository.soft_delete(old_key)
        
        # Determine original expiry duration in days if custom expiry was set
        expires_in_days: Optional[int] = None
        if old_key.expires_at:
            delta = old_key.expires_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
            expires_in_days = max(1, delta.days)
            
        # Generate new key with identical metadata
        new_schema = APIKeyCreate(name=old_key.name, expires_in_days=expires_in_days)
        return await self.create_key(organization_id, new_schema)
