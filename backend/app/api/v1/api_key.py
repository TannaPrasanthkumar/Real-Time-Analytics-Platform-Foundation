import uuid
from typing import List
from fastapi import APIRouter, Depends, status

from app.api.deps import get_db, RequireRole
from app.models.user import UserRole
from app.schemas.api_key import APIKeyCreate, APIKeyResponse, APIKeyCreatedResponse
from app.services.api_key import APIKeyService

router = APIRouter(tags=["API Keys"])


@router.post(
    "/organizations/{org_id}/api-keys",
    response_model=APIKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireRole(UserRole.ADMIN))],
)
async def generate_api_key(
    org_id: uuid.UUID,
    schema: APIKeyCreate,
    db=Depends(get_db),
) -> APIKeyCreatedResponse:
    """Generate a new API Key for workspace ingestion. Requires Admin or Owner role."""
    service = APIKeyService(db)
    return await service.create_key(org_id, schema)


@router.get(
    "/organizations/{org_id}/api-keys",
    response_model=List[APIKeyResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ADMIN))],
)
async def list_api_keys(
    org_id: uuid.UUID,
    db=Depends(get_db),
) -> List[APIKeyResponse]:
    """List all active API Keys for a workspace organization. Requires Admin or Owner role."""
    service = APIKeyService(db)
    return await service.get_org_keys(org_id)


@router.delete(
    "/organizations/{org_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequireRole(UserRole.ADMIN))],
)
async def revoke_api_key(
    org_id: uuid.UUID,
    key_id: uuid.UUID,
    db=Depends(get_db),
) -> None:
    """Revoke (soft-delete) an API key. Requires Admin or Owner role."""
    service = APIKeyService(db)
    await service.revoke_key(org_id, key_id)


@router.post(
    "/organizations/{org_id}/api-keys/{key_id}/rotate",
    response_model=APIKeyCreatedResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireRole(UserRole.ADMIN))],
)
async def rotate_api_key(
    org_id: uuid.UUID,
    key_id: uuid.UUID,
    db=Depends(get_db),
) -> APIKeyCreatedResponse:
    """Rotate an existing API key, revoking it and returning a new key. Requires Admin or Owner role."""
    service = APIKeyService(db)
    return await service.rotate_key(org_id, key_id)
