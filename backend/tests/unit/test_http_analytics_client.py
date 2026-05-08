from __future__ import annotations

import httpx
import pytest
import structlog
from httpx import AsyncClient, MockTransport

from services.gateway.app.config import Settings
from shared.models.enums import AgentAction, ResponseSource
from services.gateway.app.services.http_analytics_client import HttpAnalyticsClient


def _settings() -> Settings:
    return Settings(app_env="test", log_level="WARNING", cors_origins=["http://localhost"])


@pytest.mark.asyncio
async def test_http_analytics_client_roundtrip():
    captured = {"paths": []}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["paths"].append(request.url.path)
        captured["headers"] = dict(request.headers)
        if request.url.path.endswith("/summary"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "total_queries": 1,
                        "cache_hits": 0,
                        "llm_calls": 1,
                        "validate_decisions": 0,
                        "false_hits": 0,
                        "hit_rate": 0.0,
                        "avg_cache_latency_ms": 0.0,
                        "avg_llm_latency_ms": 1.0,
                        "cache_entries": 0,
                        "estimated_tokens_saved": 0,
                        "estimated_time_saved_ms": 0.0,
                        "last_decision": None,
                    },
                    "error": None,
                    "timestamp": "t",
                },
            )
        if request.url.path.endswith("/history"):
            return httpx.Response(
                200,
                json={"success": True, "data": {"entries": []}, "error": None, "timestamp": "t"},
            )
        return httpx.Response(200, json={"success": True, "data": {}, "error": None, "timestamp": "t"})

    client = AsyncClient(transport=MockTransport(handler), base_url="http://test")
    svc = HttpAnalyticsClient(settings=_settings(), http_client=client)
    structlog.contextvars.bind_contextvars(correlation_id="analytics-cid-1")
    try:
        await svc.record_query(
            query="q",
            source=ResponseSource.LLM,
            agent_action=AgentAction.LLM_FALLBACK,
            similarity_score=0.1,
            latency_ms=4.0,
            cache_id=None,
            response_text="r",
        )
        summary = await svc.summary()
        history = await svc.history(10)
        await svc.reset()
    finally:
        structlog.contextvars.clear_contextvars()
        await client.aclose()

    assert summary.llm_calls == 1
    assert history.entries == []
    assert any(p.endswith("/events/query") for p in captured["paths"])
    assert captured["headers"].get("x-correlation-id") == "analytics-cid-1"

