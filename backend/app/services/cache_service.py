import uuid
from datetime import datetime, timezone
from typing import List, Optional

from qdrant_client.http import models as qmodels

from app.config import Settings
from app.infrastructure.qdrant_client import QdrantInfrastructure
from app.infrastructure.redis_client import RedisInfrastructure
from app.models.schemas import CacheEntry, CacheHit, EvictionResult
from app.services.base.cache_base import CacheReader, CacheWriter
from app.utils.logger import get_logger

logger = get_logger(__name__)

QUALITY_KEY = "semcache:quality:{cache_id}"
HIT_COUNT_KEY = "semcache:hits:{cache_id}"
PROMOTE_FLAG_KEY = "semcache:flags:promoted"
DEMOTE_FLAG_KEY = "semcache:flags:demoted"


class CacheService(CacheReader, CacheWriter):
    """Concrete Qdrant + Redis-backed semantic cache. Implements both
    CacheReader and CacheWriter so a single instance can be passed in,
    while consumers depend on whichever interface they need."""

    def __init__(
        self,
        settings: Settings,
        qdrant: QdrantInfrastructure,
        redis_infra: RedisInfrastructure,
    ):
        self._settings = settings
        self._qdrant = qdrant
        self._redis = redis_infra
        self._collection = settings.qdrant_collection

    # ---------- CacheReader ----------

    async def search(self, embedding: List[float], top_k: int = 5) -> List[CacheHit]:
        results = await self._qdrant.client.search(
            collection_name=self._collection,
            query_vector=embedding,
            limit=top_k,
            with_payload=True,
        )
        hits: List[CacheHit] = []
        for r in results:
            payload = r.payload or {}
            cache_id = str(r.id)
            quality = await self._get_quality(cache_id)
            hit_count = await self._get_hit_count(cache_id)
            hits.append(
                CacheHit(
                    id=cache_id,
                    query=payload.get("query", ""),
                    response=payload.get("response", ""),
                    score=float(r.score),
                    hit_count=hit_count,
                    quality_score=quality,
                )
            )
        return hits

    async def get(self, cache_id: str) -> Optional[CacheEntry]:
        records = await self._qdrant.client.retrieve(
            collection_name=self._collection,
            ids=[cache_id],
            with_payload=True,
        )
        if not records:
            return None
        rec = records[0]
        payload = rec.payload or {}
        quality = await self._get_quality(cache_id)
        hits = await self._get_hit_count(cache_id)
        return CacheEntry(
            id=str(rec.id),
            query=payload.get("query", ""),
            response=payload.get("response", ""),
            quality_score=quality,
            hit_count=hits,
            created_at=payload.get("created_at", ""),
            last_used_at=payload.get("last_used_at", ""),
            promoted=await self._is_flagged(PROMOTE_FLAG_KEY, cache_id),
            demoted=await self._is_flagged(DEMOTE_FLAG_KEY, cache_id),
        )

    async def list_entries(self, page: int, page_size: int) -> tuple[List[CacheEntry], int]:
        offset = (page - 1) * page_size
        scrolled, _ = await self._qdrant.client.scroll(
            collection_name=self._collection,
            limit=page_size,
            offset=offset,
            with_payload=True,
        )
        entries: List[CacheEntry] = []
        for rec in scrolled:
            cache_id = str(rec.id)
            payload = rec.payload or {}
            quality = await self._get_quality(cache_id)
            hits = await self._get_hit_count(cache_id)
            entries.append(
                CacheEntry(
                    id=cache_id,
                    query=payload.get("query", ""),
                    response=payload.get("response", ""),
                    quality_score=quality,
                    hit_count=hits,
                    created_at=payload.get("created_at", ""),
                    last_used_at=payload.get("last_used_at", ""),
                    promoted=await self._is_flagged(PROMOTE_FLAG_KEY, cache_id),
                    demoted=await self._is_flagged(DEMOTE_FLAG_KEY, cache_id),
                )
            )
        total = (await self._qdrant.client.count(self._collection)).count
        return entries, total

    # ---------- CacheWriter ----------

    async def store(
        self,
        query: str,
        embedding: List[float],
        response: str,
        metadata: dict,
    ) -> str:
        cache_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "query": query,
            "response": response,
            "created_at": now,
            "last_used_at": now,
            **(metadata or {}),
        }
        await self._qdrant.client.upsert(
            collection_name=self._collection,
            points=[
                qmodels.PointStruct(
                    id=cache_id,
                    vector=embedding,
                    payload=payload,
                )
            ],
        )
        await self._redis.client.set(QUALITY_KEY.format(cache_id=cache_id), "1.0")
        await self._redis.client.set(HIT_COUNT_KEY.format(cache_id=cache_id), "0")
        logger.info("cache.stored", cache_id=cache_id, query_preview=query[:80])
        return cache_id

    async def promote(self, cache_id: str, new_quality: float) -> None:
        await self._redis.client.set(QUALITY_KEY.format(cache_id=cache_id), f"{new_quality:.6f}")
        await self._redis.client.sadd(PROMOTE_FLAG_KEY, cache_id)
        await self._redis.client.srem(DEMOTE_FLAG_KEY, cache_id)
        logger.info("cache.promoted", cache_id=cache_id, quality=new_quality)

    async def demote(self, cache_id: str, new_quality: float) -> None:
        await self._redis.client.set(QUALITY_KEY.format(cache_id=cache_id), f"{new_quality:.6f}")
        await self._redis.client.sadd(DEMOTE_FLAG_KEY, cache_id)
        logger.info("cache.demoted", cache_id=cache_id, quality=new_quality)

    async def delete(self, cache_id: str) -> None:
        await self._qdrant.client.delete(
            collection_name=self._collection,
            points_selector=qmodels.PointIdsList(points=[cache_id]),
        )
        await self._redis.client.delete(
            QUALITY_KEY.format(cache_id=cache_id),
            HIT_COUNT_KEY.format(cache_id=cache_id),
        )
        await self._redis.client.srem(PROMOTE_FLAG_KEY, cache_id)
        await self._redis.client.srem(DEMOTE_FLAG_KEY, cache_id)
        logger.info("cache.deleted", cache_id=cache_id)

    async def increment_hit(self, cache_id: str) -> None:
        await self._redis.client.incr(HIT_COUNT_KEY.format(cache_id=cache_id))
        now = datetime.now(timezone.utc).isoformat()
        await self._qdrant.client.set_payload(
            collection_name=self._collection,
            payload={"last_used_at": now},
            points=[cache_id],
        )

    async def clear_all(self) -> int:
        """Remove all cache points and related Redis keys for this collection."""
        deleted = 0
        while True:
            records, _ = await self._qdrant.client.scroll(
                collection_name=self._collection,
                limit=256,
                with_payload=False,
            )
            if not records:
                break
            for rec in records:
                await self.delete(str(rec.id))
                deleted += 1
        logger.info("cache.cleared_all", deleted=deleted)
        return deleted

    async def evict_low_quality(self, threshold: float) -> EvictionResult:
        evicted: List[str] = []
        page = 1
        page_size = 100
        while True:
            entries, total = await self.list_entries(page, page_size)
            if not entries:
                break
            for e in entries:
                if e.quality_score < threshold:
                    await self.delete(e.id)
                    evicted.append(e.id)
            if page * page_size >= total:
                break
            page += 1
        logger.info("cache.evicted", count=len(evicted), threshold=threshold)
        return EvictionResult(evicted_ids=evicted, evicted_count=len(evicted))

    # ---------- helpers ----------

    async def _get_quality(self, cache_id: str) -> float:
        raw = await self._redis.client.get(QUALITY_KEY.format(cache_id=cache_id))
        if raw is None:
            return 1.0
        try:
            return float(raw)
        except ValueError:
            return 1.0

    async def _get_hit_count(self, cache_id: str) -> int:
        raw = await self._redis.client.get(HIT_COUNT_KEY.format(cache_id=cache_id))
        if raw is None:
            return 0
        try:
            return int(raw)
        except ValueError:
            return 0

    async def _is_flagged(self, key: str, cache_id: str) -> bool:
        return bool(await self._redis.client.sismember(key, cache_id))
