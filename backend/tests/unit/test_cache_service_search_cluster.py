"""CacheService.search uses per-key GET so Redis Cluster avoids CROSSSLOT."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.cache.app.services.cache_service import (
    HIT_COUNT_KEY,
    QUALITY_KEY,
    CacheService,
)


@pytest.mark.asyncio
async def test_search_uses_per_key_get_not_mget(settings):
    """Multi-key MGET fails on Redis Cluster when UUIDs map to different slots."""
    hits = [
        SimpleNamespace(
            id="bf4010a1-bb01-4ea2-9f34-ac5b91a8735c",
            score=0.91,
            payload={"query": "q1", "response": "a1"},
        ),
        SimpleNamespace(
            id="55de7104-3ff7-49b7-8ba0-dc69e56b7efd",
            score=0.82,
            payload={"query": "q2", "response": "a2"},
        ),
    ]

    qdrant_client = MagicMock()
    qdrant_client.search = AsyncMock(return_value=hits)

    redis_client = MagicMock()
    redis_client.get = AsyncMock(
        side_effect=[
            "0.95",
            "0.88",
            "3",
            "7",
        ]
    )
    redis_client.pipeline = MagicMock(
        side_effect=AssertionError("pipeline must not be used for search (cluster CROSSSLOT)")
    )

    qdrant_infra = MagicMock()
    qdrant_infra.client = qdrant_client
    redis_infra = MagicMock()
    redis_infra.client = redis_client

    svc = CacheService(settings, qdrant_infra, redis_infra)
    out = await svc.search([0.1, 0.2, 0.3, 0.4], top_k=5)

    assert len(out) == 2
    assert out[0].quality_score == pytest.approx(0.95)
    assert out[0].hit_count == 3
    assert out[1].quality_score == pytest.approx(0.88)
    assert out[1].hit_count == 7

    assert redis_client.get.await_count == 4
    keys_requested = [c.args[0] for c in redis_client.get.await_args_list]
    assert keys_requested == [
        QUALITY_KEY.format(cache_id="bf4010a1-bb01-4ea2-9f34-ac5b91a8735c"),
        QUALITY_KEY.format(cache_id="55de7104-3ff7-49b7-8ba0-dc69e56b7efd"),
        HIT_COUNT_KEY.format(cache_id="bf4010a1-bb01-4ea2-9f34-ac5b91a8735c"),
        HIT_COUNT_KEY.format(cache_id="55de7104-3ff7-49b7-8ba0-dc69e56b7efd"),
    ]
    redis_client.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_delete_uses_single_key_deletes(settings):
    qdrant_client = MagicMock()
    qdrant_client.delete = AsyncMock()

    redis_client = MagicMock()
    redis_client.delete = AsyncMock(return_value=1)
    redis_client.srem = AsyncMock(return_value=1)

    qdrant_infra = MagicMock()
    qdrant_infra.client = qdrant_client
    redis_infra = MagicMock()
    redis_infra.client = redis_client

    svc = CacheService(settings, qdrant_infra, redis_infra)
    await svc.delete("abc-123")

    assert redis_client.delete.await_count == 2
    del_args = [c.args for c in redis_client.delete.await_args_list]
    assert del_args == [
        (QUALITY_KEY.format(cache_id="abc-123"),),
        (HIT_COUNT_KEY.format(cache_id="abc-123"),),
    ]
