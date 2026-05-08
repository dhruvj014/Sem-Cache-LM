from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.cache.app.api.internal_cache import router
from shared.models.schemas import CacheHit, EvictionResult


class _FakeCacheBoundary:
    def __init__(self):
        self.hit_incremented = None
        self.feedback = None

    async def search(self, embedding: list[float], top_k: int = 5) -> list[CacheHit]:
        return [
            CacheHit(
                id="cid-1",
                query="q",
                response="r",
                score=0.91,
                hit_count=3,
                quality_score=0.95,
            )
        ]

    async def store(self, query: str, embedding: list[float], response: str, metadata: dict) -> str:
        return "new-1"

    async def increment_hit(self, cache_id: str) -> None:
        self.hit_incremented = cache_id

    async def promote(self, cache_id: str, new_quality: float) -> None:
        self.feedback = ("promote", cache_id, new_quality)

    async def demote(self, cache_id: str, new_quality: float) -> None:
        self.feedback = ("demote", cache_id, new_quality)

    async def get(self, cache_id: str):
        return None

    async def delete(self, cache_id: str) -> None:
        return None

    async def clear_all(self) -> int:
        return 0

    async def evict_low_quality(self, threshold: float) -> EvictionResult:
        return EvictionResult(evicted_ids=["a", "b"], evicted_count=2)


def test_cache_internal_contract_routes():
    app = FastAPI()
    app.include_router(router, prefix="/internal")
    fake = _FakeCacheBoundary()
    app.state.cache_boundary = fake
    client = TestClient(app)

    search = client.post(
        "/internal/v1/cache/search",
        json={"embedding": [0.1, 0.2, 0.3], "top_k": 3},
    )
    assert search.status_code == 200
    assert len(search.json()["data"]["hits"]) == 1

    store = client.post(
        "/internal/v1/cache/store",
        json={
            "query": "What is cache?",
            "embedding": [0.1, 0.2, 0.3],
            "response": "Cache response",
            "metadata": {"session_id": "s1"},
        },
    )
    assert store.status_code == 200
    assert store.json()["data"]["cache_id"] == "new-1"

    inc = client.post("/internal/v1/cache/increment_hit", json={"cache_id": "cid-1"})
    assert inc.status_code == 200
    assert fake.hit_incremented == "cid-1"

    fb = client.post(
        "/internal/v1/cache/feedback",
        json={"cache_id": "cid-1", "action": "promote", "new_quality": 0.99},
    )
    assert fb.status_code == 200
    assert fake.feedback == ("promote", "cid-1", 0.99)

    ev = client.post("/internal/v1/cache/evict", json={"threshold": 0.2})
    assert ev.status_code == 200
    assert ev.json()["data"]["evicted_count"] == 2

