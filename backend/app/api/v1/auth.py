from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Response, Cookie
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.schemas.organization import OrganizationResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.deps import get_db, get_current_user
from app.core.config import settings
from app.core.security import decode_token, create_access_token, create_refresh_token
from app.core.exceptions import UnauthorizedException, BadRequestException
from app.models.user import User, UserOrganization
from app.repositories.user import UserRepository
from app.schemas.auth import UserSignUp, UserLogin, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth import AuthService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Helper setting refresh token inside secure HTTP-only cookies."""
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Helper clearing refresh token cookies at logout events."""
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        path="/",
    )


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(
    schema: UserSignUp,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Register account credentials, auto-provision default workspace, and issue tokens."""
    auth_service = AuthService(db)
    token_response = await auth_service.register_new_tenant(schema)
    
    # Mount refresh token to HTTP cookie
    refresh_token = token_response.__dict__.pop("_refresh_token", None)
    if refresh_token:
        _set_refresh_cookie(response, refresh_token)
        
    return token_response


@router.post("/login", response_model=TokenResponse)
async def login(
    schema: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Authenticate account credentials, verify memberships, and issue active tokens."""
    auth_service = AuthService(db)
    token_response = await auth_service.authenticate_user(schema)
    
    refresh_token = token_response.__dict__.pop("_refresh_token", None)
    if refresh_token:
        _set_refresh_cookie(response, refresh_token)
        
    return token_response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Silent token refresh extracting credentials from HttpOnly refresh cookie."""
    if not refresh_token:
        logger.warning("Refresh token cookie missing during validation check.")
        raise UnauthorizedException(
            message="Credentials verification failed. Refresh token missing."
        )

    try:
        payload = decode_token(refresh_token)
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        if not user_id_str or token_type != "refresh":
            raise UnauthorizedException(message="Invalid token claims.")
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise UnauthorizedException(message="Invalid refresh token signature.")

    user_repo = UserRepository(db)
    user = await user_repo.get(user_id)
    if not user or not user.is_active:
        raise UnauthorizedException(message="User account inactive or not found.")

    # Retrieve memberships
    stmt = select(UserOrganization).where(
        UserOrganization.user_id == user.id,
        UserOrganization.is_deleted == False,
    )
    res = await db.execute(stmt)
    memberships = res.scalars().all()
    if not memberships:
        raise BadRequestException(
            message="Account is not associated with any active organizations."
        )

    default_org_id = memberships[0].organization_id

    # Generate fresh tokens
    new_access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)

    _set_refresh_cookie(response, new_refresh_token)

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        user=user,
        default_organization_id=default_org_id,
    )


@router.post("/logout")
async def logout(response: Response) -> dict:
    """Clear authorization refresh cookie states from user browser."""
    _clear_refresh_cookie(response)
    return {"success": True, "message": "Logout successful."}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Retrieve logged-in user profile details."""
    return current_user


class UserOrganizationResponse(BaseModel):
    organization: OrganizationResponse
    role: str

    class Config:
        from_attributes = True


@router.get("/organizations", response_model=list[UserOrganizationResponse])
async def get_my_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> list[UserOrganizationResponse]:
    """Retrieve all organizations and memberships associated with the logged-in user."""
    stmt = select(UserOrganization).where(
        UserOrganization.user_id == current_user.id,
        UserOrganization.is_deleted == False
    ).options(selectinload(UserOrganization.organization))
    res = await db.execute(stmt)
    memberships = res.scalars().all()
    
    return [
        UserOrganizationResponse(
            organization=m.organization,
            role=m.role
        )
        for m in memberships if m.organization and not m.organization.is_deleted
    ]
