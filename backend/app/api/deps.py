from typing import AsyncGenerator
import uuid
import hashlib
import secrets
from datetime import datetime, timezone
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
import structlog

from app.db.session import async_session
from app.core.security import decode_token
from app.core.config import settings
from app.core.exceptions import (
    UnauthorizedException,
    ForbiddenException,
    RateLimitException,
)
from app.models.user import User, UserOrganization, UserRole
from app.models.api_key import APIKey
from app.repositories.user import UserRepository
from app.repositories.api_key import APIKeyRepository

logger = structlog.get_logger(__name__)

# Security scheme to extract JWT Bearer token from authorization headers
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login"
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a thread-safe asynchronous database session.
    
    Guarantees session closure and connection return to connection pool
    at request lifecycle completion.
    """
    session: AsyncSession = async_session()
    try:
        yield session
    except Exception as e:
        logger.error(
            "Transaction pipeline exception encountered. Rolling back changes.",
            error=str(e),
        )
        await session.rollback()
        raise e
    finally:
        await session.close()


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2)
) -> User:
    """Dependency extracting JWT and resolving active database User credentials."""
    try:
        payload = decode_token(token)
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        if not user_id_str or token_type != "access":
            raise UnauthorizedException(message="Could not validate credentials.")
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise UnauthorizedException(message="Could not validate credentials.")

    user_repo = UserRepository(db)
    user = await user_repo.get(user_id)
    if not user:
        raise UnauthorizedException(message="User not found.")
    if not user.is_active:
        raise UnauthorizedException(message="Inactive user account.")
    return user


class RequireRole:
    """FastAPI dependency guard evaluating organization membership and role clearance."""
    
    ROLE_LEVELS = {
        UserRole.OWNER: 4,
        UserRole.ADMIN: 3,
        UserRole.ANALYST: 2,
        UserRole.VIEWER: 1,
    }

    def __init__(self, required_role: UserRole):
        self.required_role = required_role

    async def __call__(
        self,
        org_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> UserOrganization:
        # Platform superusers automatically bypass tenant role checks
        if current_user.is_superuser:
            logger.info(
                "Superuser role clearance bypass applied",
                user_id=current_user.id,
                org_id=org_id,
            )
            return UserOrganization(
                user_id=current_user.id,
                organization_id=org_id,
                role=UserRole.OWNER,
            )

        user_repo = UserRepository(db)
        membership = await user_repo.get_membership(
            user_id=current_user.id, organization_id=org_id
        )
        
        if not membership:
            logger.warning(
                "Tenant access denied. User not a member of organization.",
                user_id=current_user.id,
                org_id=org_id,
            )
            raise ForbiddenException(
                message="You do not have access permissions for the requested organization."
            )

        # Resolve hierarchical roles clearance
        user_role_level = self.ROLE_LEVELS.get(membership.role, 0)
        required_role_level = self.ROLE_LEVELS.get(self.required_role, 99)

        if user_role_level < required_role_level:
            logger.warning(
                "Tenant authorization failed. Insufficient role clearances.",
                user_id=current_user.id,
                org_id=org_id,
                user_role=membership.role,
                required_role=self.required_role,
            )
            raise ForbiddenException(
                message=f"Access denied. This action requires a minimum role of {self.required_role}."
            )

        return membership


async def get_api_key_from_request(request: Request) -> str:
    """Helper to extract API key from headers or Authorization Bearer tokens."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header.split(" ")[1]
            
    if not api_key:
        raise UnauthorizedException(message="API Key is missing.")
    return api_key


async def enforce_rate_limiting(prefix: str, organization_id: uuid.UUID) -> None:
    """Redis-backed sliding minute window rate limiter."""
    limit = settings.RATE_LIMIT_PER_MINUTE
    
    # Formulate unique key: rate_limit:{prefix}:{minute}
    minute_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    redis_key = f"rate_limit:{prefix}:{minute_str}"
    
    redis_client = aioredis.from_url(settings.REDIS_URL, socket_timeout=2.0)
    try:
        pipe = redis_client.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, 60)
        results = await pipe.execute()
        current_count = results[0]
        
        if current_count > limit:
            logger.warning(
                "Rate limit exceeded for API Key prefix",
                prefix=prefix,
                org_id=str(organization_id),
                current_count=current_count,
                limit=limit,
            )
            raise RateLimitException(
                message=f"Rate limit exceeded. Maximum allowed: {limit} requests per minute."
            )
    finally:
        await redis_client.close()


async def validate_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> APIKey:
    """Security dependency validating cryptographically secure ingestion API keys."""
    api_key = await get_api_key_from_request(request)
    
    # Format verification
    if len(api_key) < 16 or not api_key.startswith("pk_live_"):
        raise UnauthorizedException(message="Invalid API Key format.")
        
    prefix = api_key[:16]
    
    # Prefix lookup
    api_key_repo = APIKeyRepository(db)
    db_key = await api_key_repo.get_by_prefix(prefix)
    
    if not db_key:
        raise UnauthorizedException(message="Invalid API Key.")
        
    # Constant-time comparison
    incoming_hash = hashlib.sha256(api_key.encode()).hexdigest()
    if not secrets.compare_digest(db_key.hashed_key, incoming_hash):
        raise UnauthorizedException(message="Invalid API Key.")
        
    # Expiry verification
    if db_key.expires_at and db_key.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise UnauthorizedException(message="API Key has expired.")
        
    # Rate limit enforcement
    await enforce_rate_limiting(db_key.prefix, db_key.organization_id)
    
    return db_key
