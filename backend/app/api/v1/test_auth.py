import uuid
from fastapi import APIRouter, Depends

from app.api.deps import RequireRole
from app.models.user import UserRole, UserOrganization

router = APIRouter(prefix="/test-guard", tags=["RBAC Testing"])


@router.get("/viewer/{org_id}")
async def test_viewer_guard(
    membership: UserOrganization = Depends(RequireRole(UserRole.VIEWER))
) -> dict:
    """Endpoint accessible by Viewer, Analyst, Admin, and Owner."""
    return {
        "success": True,
        "role": membership.role,
        "message": f"Successfully passed Viewer guard with role {membership.role}.",
    }


@router.get("/analyst/{org_id}")
async def test_analyst_guard(
    membership: UserOrganization = Depends(RequireRole(UserRole.ANALYST))
) -> dict:
    """Endpoint accessible by Analyst, Admin, and Owner."""
    return {
        "success": True,
        "role": membership.role,
        "message": f"Successfully passed Analyst guard with role {membership.role}.",
    }


@router.get("/admin/{org_id}")
async def test_admin_guard(
    membership: UserOrganization = Depends(RequireRole(UserRole.ADMIN))
) -> dict:
    """Endpoint accessible by Admin and Owner."""
    return {
        "success": True,
        "role": membership.role,
        "message": f"Successfully passed Admin guard with role {membership.role}.",
    }


@router.get("/owner/{org_id}")
async def test_owner_guard(
    membership: UserOrganization = Depends(RequireRole(UserRole.OWNER))
) -> dict:
    """Endpoint accessible exclusively by Owner."""
    return {
        "success": True,
        "role": membership.role,
        "message": f"Successfully passed Owner guard with role {membership.role}.",
    }
