import json
import logging
from typing import Any, Dict, Optional
import redis.asyncio as aioredis
from redis.exceptions import ConnectionError, RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Async Redis caching service with explicit TTL policies and JSON serialization."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._pool: Optional[aioredis.ConnectionPool] = None

    def _get_client(self) -> aioredis.Redis:
        if self._pool is None:
            self._pool = aioredis.ConnectionPool.from_url(
                self.redis_url,
                decode_responses=True,
                max_connections=20,
            )
        return aioredis.Redis(connection_pool=self._pool)

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve and deserialize JSON payload from Redis."""
        client = self._get_client()
        try:
            raw = await client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except (RedisError, json.JSONDecodeError) as exc:
            logger.error("Redis get_json failed for key %s: %s", key, exc)
            return None

    async def set_json(
        self, key: str, value: Dict[str, Any], ttl_seconds: int
    ) -> bool:
        """Serialize dictionary to JSON and store in Redis with an explicit TTL."""
        client = self._get_client()
        try:
            payload = json.dumps(value, default=str)
            return bool(await client.set(key, payload, ex=ttl_seconds))
        except (RedisError, TypeError) as exc:
            logger.error("Redis set_json failed for key %s: %s", key, exc)
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        client = self._get_client()
        try:
            deleted_count = await client.delete(key)
            return deleted_count > 0
        except RedisError as exc:
            logger.error("Redis delete failed for key %s: %s", key, exc)
            return False

    async def ping(self) -> bool:
        """Health check for Redis connectivity."""
        client = self._get_client()
        try:
            return bool(await client.ping())
        except (RedisError, ConnectionError) as exc:
            logger.warning("Redis ping healthcheck failed: %s", exc)
            return False

    async def close(self):
        """Close connection pool."""
        if self._pool is not None:
            await self._pool.disconnect()
            self._pool = None
