from __future__ import annotations

import httpx
import pytest
import structlog
from httpx import AsyncClient, MockTransport

from services.gateway.app.config import Settings
from shared.clients.http.cache import HttpCacheClient


def _settings() -> Settings:
    return Settings(app_env="test", log_level="WARNING", cors_origins=["http://localhost"])


@pytest.mark.asyncio
async def test_http_cache_client_search_and_store_roundtrip():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["last_path"] = request.url.path
        captured["headers"] = dict(request.headers)
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "hits": [
                            {
                                "id": "cid",
                                "query": "q",
                                "response": "r",
                                "score": 0.9,
                                "hit_count": 1,
                                "quality_score": 1.0,
                            }
                        ]
                    },
                    "error": None,
                    "timestamp": "t",
                },
            )
        if request.url.path.endswith("/store"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {"cache_id": "new-1"},
                    "error": None,
                    "timestamp": "t",
                },
            )
        return httpx.Response(200, json={"success": True, "data": {}, "error": None, "timestamp": "t"})

    client = AsyncClient(transport=MockTransport(handler), base_url="http://test")
    svc = HttpCacheClient(settings=_settings(), http_client=client)
    structlog.contextvars.bind_contextvars(correlation_id="cache-cid-1")
    try:
        hits = await svc.search([0.1, 0.2, 0.3], top_k=3)
        cache_id = await svc.store("q", [0.1], "r", {})
    finally:
        structlog.contextvars.clear_contextvars()
        await client.aclose()

    assert len(hits) == 1
    assert hits[0].id == "cid"
    assert cache_id == "new-1"
    assert captured["headers"].get("x-correlation-id") == "cache-cid-1"

