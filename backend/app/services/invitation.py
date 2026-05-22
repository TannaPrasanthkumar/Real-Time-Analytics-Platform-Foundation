import secrets
from datetime import datetime, timezone, timedelta
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.repositories.invitation import InvitationRepository
from app.repositories.user import UserRepository
from app.models.invitation import Invitation
from app.models.user import UserOrganization, UserRole
from app.schemas.invitation import InvitationCreate, InvitationAccept
from app.schemas.auth import TokenResponse
from app.schemas.user import UserCreate
from app.services.user import UserService
from app.services.organization import OrganizationService
from app.core.security import create_access_token, create_refresh_token
from app.core.exceptions import NotFoundException, BadRequestException


class InvitationService(BaseService[Invitation, InvitationRepository]):
    """Service layer orchestrating the lifecycle and acceptance of workspace team invitations."""

    def __init__(self, session: AsyncSession):
        super().__init__(InvitationRepository(session))
        self.session = session
        self.user_repo = UserRepository(session)
        self.user_service = UserService(session)
        self.org_service = OrganizationService(session)

    async def create_invitation(
        self, organization_id: uuid.UUID, inviter_id: uuid.UUID, schema: InvitationCreate
    ) -> Invitation:
        """Issue a new pending onboarding workspace invitation for a target email."""
        email = schema.email.lower()
        
        # 1. Verify organization exists
        org = await self.org_service.get_by_id(organization_id)
        if not org:
            raise NotFoundException(message="Organization not found.")

        # 2. Check if user already exists and is already a member
        try:
            user = await self.user_service.get_by_email(email)
            membership = await self.user_repo.get_membership(user.id, organization_id)
            if membership:
                raise BadRequestException(
                    message=f"User with email {email} is already a member of this organization."
                )
        except NotFoundException:
            # User does not exist, safe to invite
            pass

        # 3. Check for existing active, unexpired pending invitation
        existing_invite = await self.repository.get_active_by_email_and_org(
            email, organization_id
        )
        if existing_invite and existing_invite.expires_at > datetime.now(timezone.utc):
            raise BadRequestException(
                message=f"There is already an active pending invitation for {email}."
            )

        # 4. Generate cryptographically secure token and 7-day expiration
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        inv_data = {
            "email": email,
            "organization_id": organization_id,
            "inviter_id": inviter_id,
            "role": schema.role,
            "token": token,
            "expires_at": expires_at,
            "is_accepted": False,
        }

        invite = await self.repository.create(inv_data)
        invite.organization_name = org.name
        return invite

    async def get_valid_invitation(self, token: str) -> Invitation:
        """Fetch, validate, and verify that an invitation is pending and unexpired."""
        invite = await self.repository.get_by_token(token)
        if not invite:
            raise NotFoundException(message="Invitation not found or has been revoked.")

        if invite.is_accepted:
            raise BadRequestException(message="This invitation has already been accepted.")

        if invite.expires_at < datetime.now(timezone.utc):
            raise BadRequestException(message="This invitation has expired.")

        # Bind organization name metadata
        org = await self.org_service.get_by_id(invite.organization_id)
        invite.organization_name = org.name
        return invite

    async def accept_invitation(self, schema: InvitationAccept) -> TokenResponse:
        """Process invitation acceptance, dynamic user creation if needed, and issue auth tokens."""
        # 1. Fetch and validate the invitation token state
        invite = await self.get_valid_invitation(schema.token)

        # 2. Check if the user already has an account
        try:
            user = await self.user_service.get_by_email(invite.email)
            
            # Check if they are already associated with organization
            membership = await self.user_repo.get_membership(user.id, invite.organization_id)
            if membership:
                raise BadRequestException(
                    message="You are already a member of this organization."
                )
        except NotFoundException:
            # User does not exist, dynamic account registration is required
            if not schema.password or not schema.full_name:
                raise BadRequestException(
                    message="Full name and password are required to create your account."
                )
            
            user_create = UserCreate(
                email=invite.email,
                password=schema.password,
                full_name=schema.full_name,
                is_active=True,
            )
            user = await self.user_service.create_user(user_create)

        # 3. Create the UserOrganization workspace membership association
        membership = UserOrganization(
            user_id=user.id,
            organization_id=invite.organization_id,
            role=invite.role,
        )
        self.session.add(membership)

        # 4. Finalize invitation acceptance state
        invite.is_accepted = True
        self.session.add(invite)
        
        await self.session.commit()
        await self.session.refresh(user)

        # 5. Issue access and refresh tokens
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        token_response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user,
            default_organization_id=invite.organization_id,
        )
        
        # Attach raw refresh token in temporary field for cookie transport in router
        token_response.__dict__["_refresh_token"] = refresh_token
        return token_response
