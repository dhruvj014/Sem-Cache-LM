from __future__ import annotations

import httpx
import pytest

from services.ai.app.services.gemini_embedding import GeminiEmbeddingService
from services.ai.app.services.gemini_llm import GeminiLLMClient
from shared.config.settings import Settings


@pytest.fixture
def gemini_settings() -> Settings:
    return Settings(
        app_env="test",
        log_level="WARNING",
        gemini_api_key="test-api-key",
        gemini_embedding_model="gemini-embedding-001",
        gemini_llm_model="gemini-2.5-flash-lite",
        qdrant_vector_size=4,
        gemini_timeout_seconds=30.0,
    )


def _gemini_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path.endswith(":embedContent"):
            return httpx.Response(
                200,
                json={"embedding": {"values": [0.1, 0.2, 0.3, 0.4]}},
            )
        if request.method == "POST" and path.endswith(":generateContent"):
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"parts": [{"text": "  answer text  "}]}}
                    ]
                },
            )
        if request.method == "GET" and path.endswith("/models"):
            return httpx.Response(200, json={})
        return httpx.Response(404, text=f"unhandled {request.method} {path}")

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_gemini_embedding_returns_values(gemini_settings: Settings) -> None:
    async with httpx.AsyncClient(transport=_gemini_transport()) as http_client:
        svc = GeminiEmbeddingService(gemini_settings, http_client)
        out = await svc.embed("hello")
    assert out == [0.1, 0.2, 0.3, 0.4]


@pytest.mark.asyncio
async def test_gemini_llm_generate_parses_candidate_text(
    gemini_settings: Settings,
) -> None:
    async with httpx.AsyncClient(transport=_gemini_transport()) as http_client:
        svc = GeminiLLMClient(gemini_settings, http_client)
        out = await svc.generate("prompt", system="sys")
    assert out == "answer text"


@pytest.mark.asyncio
async def test_gemini_llm_health_ok(gemini_settings: Settings) -> None:
    async with httpx.AsyncClient(transport=_gemini_transport()) as http_client:
        svc = GeminiLLMClient(gemini_settings, http_client)
        ok = await svc.health()
    assert ok is True
