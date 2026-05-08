from __future__ import annotations

import structlog
from httpx import AsyncClient, MockTransport
import httpx
import pytest

from services.gateway.app.config import Settings
from shared.contracts.internal import InternalRagRetrieveResponse
from shared.clients.http.rag import HttpRagClient


def _settings() -> Settings:
    # Reuse Settings defaults; tests use only the RAG service URL + timeout.
    return Settings(app_env="test", log_level="WARNING", cors_origins=["http://localhost"])


@pytest.mark.asyncio
async def test_http_rag_client_converts_response_to_rag_result():
    settings = _settings()
    transport_calls = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/internal/v1/retrieve")
        transport_calls["headers"] = dict(request.headers)

        data = InternalRagRetrieveResponse(
            answer="rag answer",
            citations=[
                {
                    "file_path": "repo:file.py",
                    "score": 0.9,
                    "snippet": "snippet",
                }
            ],
        )
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": data.model_dump(),
                "error": None,
                "timestamp": "t",
            },
        )

    http_client = AsyncClient(transport=MockTransport(handler), base_url="http://test")
    client = HttpRagClient(settings=settings, http_client=http_client)

    structlog.contextvars.bind_contextvars(correlation_id="cid-123")
    try:
        rag_result = await client.answer("q?")
    finally:
        structlog.contextvars.clear_contextvars()
        await http_client.aclose()

    assert rag_result.response == "rag answer"
    assert len(rag_result.citations) == 1
    assert rag_result.citations[0].file_path == "repo:file.py"
    assert "x-correlation-id" in transport_calls["headers"]
    assert transport_calls["headers"]["x-correlation-id"] == "cid-123"

