import uuid
from typing import Optional
from fastapi import APIRouter, WebSocket, status, Query
from jose import JWTError
import structlog

from app.core.security import decode_token
from app.db.session import async_session
from app.repositories.user import UserRepository
from app.models.user import User
from app.services.websocket import socket_manager

router = APIRouter(tags=["WebSockets"])
logger = structlog.get_logger(__name__)


async def get_websocket_user(token: str) -> Optional[User]:
    """Cryptographically validate JWT token passed during WebSocket query handshake."""
    try:
        # Handle both standard bearer prefix and bare token payloads
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
            
        payload = decode_token(token)
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if not user_id_str or token_type != "access":
            return None
            
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        return None

    # Fetch user within fresh transactional block to avoid pool sharing issues
    async with async_session() as db:
        user_repo = UserRepository(db)
        user = await user_repo.get(user_id)
        if user and user.is_active:
            return user
            
    return None


@router.websocket("/organizations/{org_id}/ws/events")
async def websocket_events(
    websocket: WebSocket,
    org_id: uuid.UUID,
    token: str = Query(..., description="JWT Bearer Token for handshake authentication.")
) -> None:
    """Live WebSocket gateway streaming incoming analytical events for a tenant.
    
    Validates JWT token query parameters on connection and maps connection to 
    the central ConnectionManager.
    """
    user = await get_websocket_user(token)
    if not user:
        logger.warning(
            "WebSocket handshake aborted. Invalid or expired token.",
            org_id=str(org_id)
        )
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Could not validate credentials."
        )
        return

    # Validate multi-tenant organization boundary
    async with async_session() as db:
        user_repo = UserRepository(db)
        
        if not user.is_superuser:
            membership = await user_repo.get_membership(user_id=user.id, organization_id=org_id)
            if not membership:
                logger.warning(
                    "WebSocket handshake aborted. Access denied for tenant workspace.",
                    org_id=str(org_id),
                    user_id=str(user.id)
                )
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Access denied for organization."
                )
                return

    # Accept connection and register in the connection manager group
    await socket_manager.connect(websocket, org_id)

    try:
        # Keep socket boundary open and handle client-issued heartbeats/pings
        while True:
            # We block waiting for client data (e.g. pings/pong or state switches)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except Exception as e:
        logger.debug(
            "WebSocket connection loop terminated",
            org_id=str(org_id),
            error=str(e)
        )
    finally:
        # Gracefully deregister from manager
        await socket_manager.disconnect(websocket, org_id)
