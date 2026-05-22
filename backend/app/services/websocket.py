import asyncio
import json
from typing import Dict, List
import uuid
import redis.asyncio as aioredis
import structlog
from fastapi import WebSocket

from app.core.config import settings

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages active live WebSocket subscription channels per organization with Redis Pub/Sub."""

    def __init__(self):
        # Maps organization UUID to a list of active WebSocket connection objects
        self.active_connections: Dict[uuid.UUID, List[WebSocket]] = {}
        # Maps organization UUID to its active Redis listener asyncio Task
        self.listener_tasks: Dict[uuid.UUID, asyncio.Task] = {}
        self.logger = logger.bind(service="ConnectionManager")

    async def connect(self, websocket: WebSocket, organization_id: uuid.UUID) -> None:
        """Accept WebSocket connection handshake and register to the organization group."""
        await websocket.accept()
        if organization_id not in self.active_connections:
            self.active_connections[organization_id] = []
        self.active_connections[organization_id].append(websocket)
        
        self.logger.info(
            "WebSocket client connected successfully",
            organization_id=str(organization_id),
            active_count=len(self.active_connections[organization_id])
        )

        # Spin up Redis Pub/Sub channel listener task if not already listening
        if organization_id not in self.listener_tasks:
            self.listener_tasks[organization_id] = asyncio.create_task(
                self.redis_listener(organization_id)
            )

    async def disconnect(self, websocket: WebSocket, organization_id: uuid.UUID) -> None:
        """Deregister a disconnected WebSocket connection from organization groups."""
        if organization_id in self.active_connections:
            if websocket in self.active_connections[organization_id]:
                self.active_connections[organization_id].remove(websocket)
            
            # Prune organization slot if no active sockets exist
            if not self.active_connections[organization_id]:
                self.active_connections.pop(organization_id, None)
                
                # Cancel the active Redis listener task for this organization
                task = self.listener_tasks.pop(organization_id, None)
                if task:
                    task.cancel()
                    self.logger.info(
                        "Cancelled Redis pubsub listener task for organization",
                        organization_id=str(organization_id)
                    )
                
            self.logger.info(
                "WebSocket client disconnected",
                organization_id=str(organization_id),
                active_count=len(self.active_connections.get(organization_id, []))
            )

    async def broadcast_to_org(self, organization_id: uuid.UUID, message: dict) -> None:
        """Broadcast live event analytics payload to all connected clients under a tenant."""
        if organization_id not in self.active_connections:
            return

        connections = list(self.active_connections[organization_id])
        self.logger.debug(
            "Broadcasting WebSocket message to organization",
            organization_id=str(organization_id),
            client_count=len(connections)
        )

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                self.logger.warning(
                    "Failed to send message to WebSocket client, pruning connection",
                    organization_id=str(organization_id),
                    error=str(e)
                )
                await self.disconnect(websocket, organization_id)

    async def redis_listener(self, organization_id: uuid.UUID) -> None:
        """Background coroutine listening on Redis Pub/Sub channel for live events."""
        channel_name = f"channel:org:{str(organization_id)}"
        self.logger.info(
            "Starting Redis Pub/Sub listener for organization",
            organization_id=str(organization_id),
            channel=channel_name
        )
        
        redis_client = aioredis.from_url(settings.REDIS_URL, socket_timeout=5.0)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel_name)

        try:
            while True:
                try:
                    # Non-blocking get_message loop checking for updates every 0.1s
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                    if message and message["type"] == "message":
                        payload = json.loads(message["data"])
                        await self.broadcast_to_org(organization_id, payload)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger.error(
                        "Error inside Redis pubsub subscription loop",
                        organization_id=str(organization_id),
                        error=str(e)
                    )
                    await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            self.logger.info(
                "Redis Pub/Sub listener cancelled",
                organization_id=str(organization_id)
            )
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
            await redis_client.close()


async def publish_live_message(organization_id: uuid.UUID, message: dict) -> None:
    """Utility function to publish messages onto the corresponding Redis Pub/Sub channel."""
    redis_client = aioredis.from_url(settings.REDIS_URL, socket_timeout=5.0)
    try:
        channel_name = f"channel:org:{str(organization_id)}"
        serialized = json.dumps(message, default=str)
        await redis_client.publish(channel_name, serialized)
    except Exception as e:
        logger.warning(
            "Failed to publish live event to Redis Pub/Sub",
            organization_id=str(organization_id),
            error=str(e)
        )
    finally:
        await redis_client.close()


# Global singleton manager instance
socket_manager = ConnectionManager()
