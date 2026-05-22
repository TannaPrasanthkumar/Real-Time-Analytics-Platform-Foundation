from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.user import User, UserOrganization, UserRole
from app.models.organization import Organization
from app.schemas.auth import UserSignUp, UserLogin, TokenResponse
from app.schemas.user import UserCreate
from app.schemas.organization import OrganizationCreate
from app.services.user import UserService
from app.services.organization import OrganizationService
from app.core.security import verify_password, create_access_token, create_refresh_token
from app.core.exceptions import BadRequestException, UnauthorizedException

logger = structlog.get_logger(__name__)


class AuthService:
    """Service orchestrating credentials authentication and tenant registrations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(session)
        self.org_service = OrganizationService(session)

    async def register_new_tenant(self, schema: UserSignUp) -> TokenResponse:
        """Register a new active user account alongside an Owner workspace."""
        logger.info("Registering new tenant and workspace", email=schema.email)
        
        # 1. Verify user does not already exist
        try:
            await self.user_service.get_by_email(schema.email)
            raise BadRequestException(
                message=f"Account with email {schema.email} is already registered."
            )
        except BadRequestException:
            raise
        except Exception:
            # NotFoundException expected, proceed to registration
            pass

        # 2. Provision User
        user_create = UserCreate(
            email=schema.email,
            password=schema.password,
            full_name=schema.full_name,
            is_active=True,
        )
        user = await self.user_service.create_user(user_create)

        # 3. Provision Organization
        org_create = OrganizationCreate(name=schema.organization_name)
        org = await self.org_service.create_organization(org_create)

        # 4. Bind user to organization as OWNER
        membership = UserOrganization(
            user_id=user.id,
            organization_id=org.id,
            role=UserRole.OWNER,
        )
        self.session.add(membership)
        await self.session.commit()
        await self.session.refresh(user)

        # 5. Generate Auth Tokens
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        # Build token response payload
        token_response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user,
            default_organization_id=org.id,
        )
        
        # Attach the raw refresh token value in temporary field for cookie transport in router
        token_response.__dict__["_refresh_token"] = refresh_token
        return token_response

    async def authenticate_user(self, schema: UserLogin) -> TokenResponse:
        """Validate credentials, retrieve workspaces, and generate JWT tokens."""
        logger.info("Authenticating user credentials", email=schema.email)
        
        # 1. Fetch user by email
        try:
            user = await self.user_service.get_by_email(schema.email)
        except Exception:
            # Fail with general credentials error to avoid user enumeration
            raise UnauthorizedException(
                message="Invalid credentials. Please verify your email and password."
            )

        # 2. Verify hashed password
        if not user.hashed_password or not verify_password(
            schema.password, user.hashed_password
        ):
            raise UnauthorizedException(
                message="Invalid credentials. Please verify your email and password."
            )

        # 3. Retrieve user memberships to fetch default organization
        stmt = select(UserOrganization).where(
            UserOrganization.user_id == user.id,
            UserOrganization.is_deleted == False,
        )
        res = await self.session.execute(stmt)
        memberships = res.scalars().all()
        
        if not memberships:
            raise BadRequestException(
                message="This user is not associated with any active organizations. Please contact your administrator."
            )

        # Resolve first organization as default workspace
        default_org_id = memberships[0].organization_id

        # 4. Generate Auth Tokens
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        token_response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user,
            default_organization_id=default_org_id,
        )
        
        # Carry refresh token securely for cookie mounting in router
        token_response.__dict__["_refresh_token"] = refresh_token
        return token_response
