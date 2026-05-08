"""Unit tests for CacheService quality-tracking and feedback wiring,
using in-memory fakes for Qdrant + Redis (so the suite runs offline)."""

from typing import Any

import pytest

from shared.models.enums import FeedbackRating
from services.gateway.app.services.feedback_service import FeedbackService


class FakeRedis:
    def __init__(self):
        self.kv: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}

    async def get(self, key: str):
        return self.kv.get(key)

    async def set(self, key: str, value: Any):
        self.kv[key] = str(value)

    async def incr(self, key: str):
        self.kv[key] = str(int(self.kv.get(key, "0")) + 1)

    async def delete(self, *keys):
        for k in keys:
            self.kv.pop(k, None)

    async def sadd(self, key: str, value: str):
        self.sets.setdefault(key, set()).add(value)

    async def srem(self, key: str, value: str):
        self.sets.get(key, set()).discard(value)

    async def sismember(self, key: str, value: str):
        return value in self.sets.get(key, set())


class FakeRedisInfra:
    def __init__(self):
        self.client = FakeRedis()


class FakeWriter:
    def __init__(self):
        self.promotions: list[tuple[str, float]] = []
        self.demotions: list[tuple[str, float]] = []

    async def store(self, **kw):
        return "x"

    async def promote(self, cache_id: str, new_quality: float):
        self.promotions.append((cache_id, new_quality))

    async def demote(self, cache_id: str, new_quality: float):
        self.demotions.append((cache_id, new_quality))

    async def delete(self, cache_id: str):
        pass

    async def increment_hit(self, cache_id: str):
        pass

    async def evict_low_quality(self, threshold: float):
        return None


@pytest.mark.asyncio
async def test_upvote_raises_quality_score(settings):
    redis_infra = FakeRedisInfra()
    redis_infra.client.kv["semcache:quality:abc"] = "0.5"
    writer = FakeWriter()
    service = FeedbackService(settings, redis_infra, writer)

    result = await service.submit_feedback("abc", FeedbackRating.UP)
    # EMA: new = 0.8*0.5 + 0.2*1.0 = 0.6
    assert result.new_quality_score == pytest.approx(0.6)
    assert result.promoted is True
    assert writer.promotions == [("abc", pytest.approx(0.6))]


@pytest.mark.asyncio
async def test_downvote_lowers_quality_score(settings):
    redis_infra = FakeRedisInfra()
    redis_infra.client.kv["semcache:quality:abc"] = "1.0"
    writer = FakeWriter()
    service = FeedbackService(settings, redis_infra, writer)

    result = await service.submit_feedback("abc", FeedbackRating.DOWN)
    # EMA: new = 0.8*1.0 + 0.2*0.0 = 0.8
    assert result.new_quality_score == pytest.approx(0.8)
    assert result.demoted is True


@pytest.mark.asyncio
async def test_repeated_downvotes_drive_score_below_threshold(settings):
    redis_infra = FakeRedisInfra()
    redis_infra.client.kv["semcache:quality:abc"] = "1.0"
    writer = FakeWriter()
    service = FeedbackService(settings, redis_infra, writer)
    score = 1.0
    for _ in range(20):
        result = await service.submit_feedback("abc", FeedbackRating.DOWN)
        # simulate cache_writer.demote also persisting to redis
        redis_infra.client.kv["semcache:quality:abc"] = str(result.new_quality_score)
        score = result.new_quality_score
    assert score < settings.quality_eviction_threshold
