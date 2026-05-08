from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.analytics.app.api.internal_analytics import router
from shared.models.enums import AgentAction, ResponseSource
from shared.models.schemas import AnalyticsSummary, HistoryEntry, HistoryResponse


class _FakeAnalyticsBoundary:
    def __init__(self):
        self.events = 0
        self.resets = 0

    async def record_query(self, **kwargs):
        self.events += 1

    async def summary(self) -> AnalyticsSummary:
        return AnalyticsSummary(
            total_queries=1,
            cache_hits=0,
            llm_calls=1,
            validate_decisions=0,
            false_hits=0,
            hit_rate=0.0,
            avg_cache_latency_ms=0.0,
            avg_llm_latency_ms=12.3,
            cache_entries=10,
            estimated_tokens_saved=0,
            estimated_time_saved_ms=0.0,
            last_decision=None,
        )

    async def history(self, limit: int = 20) -> HistoryResponse:
        return HistoryResponse(
            entries=[
                HistoryEntry(
                    query="q",
                    source=ResponseSource.LLM,
                    agent_action=AgentAction.LLM_FALLBACK,
                    similarity_score=0.1,
                    latency_ms=5.0,
                    cache_id=None,
                    timestamp="2026-01-01T00:00:00Z",
                )
            ]
        )

    async def reset(self) -> None:
        self.resets += 1


def test_analytics_internal_contract_routes():
    app = FastAPI()
    app.include_router(router, prefix="/internal")
    fake = _FakeAnalyticsBoundary()
    app.state.analytics_boundary = fake
    client = TestClient(app)

    ev = client.post(
        "/internal/v1/events/query",
        json={
            "correlation_id": "cid-1",
            "query": "q",
            "source": "llm",
            "agent_action": "LLM_FALLBACK",
            "similarity_score": 0.2,
            "latency_ms": 10.0,
            "response_text": "answer",
        },
    )
    assert ev.status_code == 200
    assert fake.events == 1

    summary = client.get("/internal/v1/summary")
    assert summary.status_code == 200
    assert summary.json()["data"]["llm_calls"] == 1

    history = client.get("/internal/v1/history?limit=5")
    assert history.status_code == 200
    assert len(history.json()["data"]["entries"]) == 1

    reset = client.post("/internal/v1/reset")
    assert reset.status_code == 200
    assert fake.resets == 1

