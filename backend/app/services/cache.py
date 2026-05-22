import json
from typing import Any
import redis.asyncio as aioredis
import structlog
from app.core.config import settings

logger = structlog.get_logger(__name__)


class CacheService:
    """Service handling high-throughput, structured Redis analytics query caching."""

    def __init__(self):
        self.redis_url = settings.REDIS_URL

    async def get_cached(self, key: str) -> Any | None:
        """Fetch and deserialize a JSON cached query value."""
        redis_client = aioredis.from_url(self.redis_url, socket_timeout=2.0)
        try:
            cached_data = await redis_client.get(key)
            if cached_data:
                logger.debug("Redis query cache hit", key=key)
                return json.loads(cached_data)
        except Exception as e:
            logger.warning("Failed to fetch query from Redis cache", error=str(e), key=key)
        finally:
            await redis_client.close()
        return None

    async def set_cached(self, key: str, value: Any, ttl: int = 300) -> None:
        """Serialize and cache a JSON query value with time-to-live expiration."""
        redis_client = aioredis.from_url(self.redis_url, socket_timeout=2.0)
        try:
            serialized = json.dumps(value, default=str)
            await redis_client.set(key, serialized, ex=ttl)
            logger.debug("Redis query cache set", key=key, ttl=ttl)
        except Exception as e:
            logger.warning("Failed to store query in Redis cache", error=str(e), key=key)
        finally:
            await redis_client.close()

    async def delete_cached(self, key: str) -> None:
        """Explicitly invalidate a cached query by key."""
        redis_client = aioredis.from_url(self.redis_url, socket_timeout=2.0)
        try:
            await redis_client.delete(key)
            logger.info("Redis query cache invalidated", key=key)
        except Exception as e:
            logger.warning("Failed to delete query from Redis cache", error=str(e), key=key)
        finally:
            await redis_client.close()
