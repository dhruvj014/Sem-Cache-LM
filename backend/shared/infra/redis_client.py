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
        host = self._settings.redis_host.strip()
        port = self._settings.redis_port

        if host.startswith(("redis://", "rediss://")):
            self._client = redis.Redis.from_url(
                host,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
        else:
            # If host contains a port (e.g. my-redis:6379), strip it to avoid double-ports
            if ":" in host:
                host_parts = host.split(":")
                host = host_parts[0]
                try:
                    port = int(host_parts[1])
                except (ValueError, IndexError):
                    pass

            self._client = redis.Redis(
                host=host,
                port=port,
                db=self._settings.redis_db,
                password=self._settings.redis_password or None,
                ssl=self._settings.redis_ssl,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
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

