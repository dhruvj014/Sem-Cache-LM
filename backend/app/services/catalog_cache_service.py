from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.infrastructure.redis_client import RedisInfrastructure
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CatalogCacheService:
    def __init__(self, settings: Settings, redis_infra: RedisInfrastructure):
        self._settings = settings
        self._redis = redis_infra.client
        self._prefix = settings.rag_catalog_redis_prefix.rstrip(":")

    async def sync_files(self, paths: list[Path]) -> dict:
        synced = 0
        skipped = 0
        for p in paths:
            if not p.exists() or not p.is_file():
                skipped += 1
                continue
            content = p.read_text(encoding="utf-8", errors="ignore")
            key = f"{self._prefix}:{p.name}"
            meta_key = f"{key}:meta"
            checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
            await self._redis.set(key, content)
            await self._redis.set(
                meta_key,
                json.dumps(
                    {
                        "path": str(p),
                        "sha256": checksum,
                        "synced_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
            )
            synced += 1
        logger.info("catalog.redis.synced", synced=synced, skipped=skipped)
        return {"synced": synced, "skipped": skipped}

    async def get_cached_catalog(self, name: str) -> dict:
        key = f"{self._prefix}:{name}"
        meta_key = f"{key}:meta"
        return {
            "content": await self._redis.get(key),
            "meta": await self._redis.get(meta_key),
        }
