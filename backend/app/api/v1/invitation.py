import uuid
from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_db, get_current_user, RequireRole
from app.core.config import settings
from app.models.user import User, UserRole
from app.schemas.invitation import InvitationCreate, InvitationResponse, InvitationAccept
from app.schemas.auth import TokenResponse
from app.services.invitation import InvitationService

router = APIRouter(tags=["Invitations"])


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


@router.post(
    "/organizations/{org_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireRole(UserRole.ADMIN))]
)
async def create_organization_invitation(
    org_id: uuid.UUID,
    schema: InvitationCreate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> InvitationResponse:
    """Issue a pending team workspace onboarding invitation. Requires Admin or Owner role clearance."""
    service = InvitationService(db)
    return await service.create_invitation(
        organization_id=org_id, inviter_id=current_user.id, schema=schema
    )


@router.get(
    "/invitations/{token}",
    response_model=InvitationResponse,
    status_code=status.HTTP_200_OK
)
async def verify_and_retrieve_invitation(
    token: str,
    db=Depends(get_db)
) -> InvitationResponse:
    """Public retrieval endpoint validating a token and fetching invitation details."""
    service = InvitationService(db)
    return await service.get_valid_invitation(token)


@router.post(
    "/invitations/accept",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK
)
async def accept_organization_invitation(
    schema: InvitationAccept,
    response: Response,
    db=Depends(get_db)
) -> TokenResponse:
    """Accept an organization invitation, provision credentials if needed, and log in."""
    service = InvitationService(db)
    token_response = await service.accept_invitation(schema)
    
    # Mount refresh token to HTTP cookie
    refresh_token = token_response.__dict__.pop("_refresh_token", None)
    if refresh_token:
        _set_refresh_cookie(response, refresh_token)
        
    return token_response
