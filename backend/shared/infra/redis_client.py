from __future__ import annotations

from typing import Any

import redis.asyncio as redis

from shared.observability.logger import get_logger

logger = get_logger(__name__)


class RedisInfrastructure:
    """Owns the Redis connection. SRP: connection lifecycle only."""

    def __init__(self, settings: Any):
        self._settings = settings
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return self._client

    async def connect(self) -> None:
        self._client = redis.Redis(
            host=self._settings.redis_host,
            port=self._settings.redis_port,
            db=self._settings.redis_db,
            decode_responses=True,
        )
        await self._client.ping()
        logger.info("redis.connected", host=self._settings.redis_host)

    async def health(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception as e:
            logger.warning("redis.health_failed", error=str(e))
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

