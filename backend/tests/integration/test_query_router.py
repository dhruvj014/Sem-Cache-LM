"""Integration test for QueryRouterService using fake collaborators.
Verifies the full decision pipeline: cache hit, gray-zone validate (true positive),
gray-zone validate (false hit -> RAG fallback), and cold-cache RAG fallback."""

from typing import List

import pytest

from shared.models.enums import AgentAction, ResponseSource
from shared.models.schemas import (
    CacheHit,
    EvictionResult,
    QueryResponse,
    ValidationResult,
)
from services.gateway.app.services.agent_decision import AgentDecisionLayer
from services.gateway.app.services.decision_thresholds import DecisionThresholds
from shared.domain.cache_ports import CacheReader, CacheWriter
from shared.domain.model_providers import EmbeddingService, LLMClient
from services.gateway.app.services.query_router import QueryRouterService
from services.rag.app.services.rag_service import RagCitation, RagResult
from services.gateway.app.services.session_context import NullSessionContextService


class FakeEmbedder(EmbeddingService):
    def __init__(self):
        self.calls = 0

    async def embed(self, text: str):
        self.calls += 1
        return [0.1, 0.2, 0.3, 0.4]

    async def embed_batch(self, texts):
        return [await self.embed(t) for t in texts]

    @property
    def vector_size(self) -> int:
        return 4


class FakeCache(CacheReader, CacheWriter):
    def __init__(self, hits: List[CacheHit]):
        self._hits = hits
        self.stored: list[dict] = []
        self.incremented: list[str] = []

    async def search(self, embedding, top_k=5):
        return self._hits

    async def get(self, cache_id):
        return None

    async def list_entries(self, page, page_size):
        return [], 0

    async def store(self, query, embedding, response, metadata):
        cache_id = f"new-{len(self.stored)}"
        self.stored.append({"query": query, "response": response, "id": cache_id})
        return cache_id

    async def promote(self, cache_id, new_quality): pass
    async def demote(self, cache_id, new_quality): pass
    async def delete(self, cache_id): pass

    async def increment_hit(self, cache_id):
        self.incremented.append(cache_id)

    async def evict_low_quality(self, threshold):
        return EvictionResult(evicted_ids=[], evicted_count=0)


class FakeLLM(LLMClient):
    def __init__(self, response: str = "LLM-response"):
        self.calls = 0
        self._response = response

    async def generate(self, prompt: str, system: str | None = None) -> str:
        self.calls += 1
        return self._response

    async def health(self):
        return True


class FakeValidator:
    def __init__(self, is_valid: bool):
        self._is_valid = is_valid
        self.calls = 0

    async def validate(
        self,
        incoming_query,
        candidate_response,
        similarity_score,
        cache_id=None,
        **kwargs,
    ):
        self.calls += 1
        return ValidationResult(
            is_valid=self._is_valid,
            confidence=0.9,
            reason="ok" if self._is_valid else "different topic",
        )


class FakeRag:
    def __init__(self, response: str = "RAG-response"):
        self.calls = 0
        self._response = response

    async def answer(self, query: str) -> RagResult:
        self.calls += 1
        return RagResult(
            response=self._response,
            citations=[
                RagCitation(
                    file_path="backend/app/services/query_router.py",
                    score=0.88,
                    snippet="class QueryRouterService: ...",
                )
            ],
        )


class RecordingAnalyticsPublisher:
    def __init__(self):
        self.events: list[tuple[str, QueryResponse]] = []

    async def publish(self, *, query: str, response: QueryResponse):
        self.events.append((query, response))


def _hit(score, cache_id="cid-1", quality=1.0):
    return CacheHit(
        id=cache_id,
        query="cached q",
        response="cached r",
        score=score,
        hit_count=2,
        quality_score=quality,
    )


def _build(settings, hits, validator_valid=True, llm=None, rag=None):
    embedder = FakeEmbedder()
    cache = FakeCache(hits)
    agent = AgentDecisionLayer(DecisionThresholds(settings))
    validator = FakeValidator(is_valid=validator_valid)
    llm = llm or FakeLLM()
    rag = rag or FakeRag()
    publisher = RecordingAnalyticsPublisher()
    router = QueryRouterService(
        settings=settings,
        embedder=embedder,
        cache_reader=cache,
        cache_writer=cache,
        agent=agent,
        false_hit_detector=validator,
        llm=llm,
        rag=rag,
        analytics_publisher=publisher,
        session_context=NullSessionContextService(),
    )
    return router, embedder, cache, validator, llm, rag, publisher


@pytest.mark.asyncio
async def test_cold_cache_falls_back_to_llm(settings):
    router, embedder, cache, _, llm, rag, publisher = _build(settings, hits=[])
    resp = await router.handle_query("first query", "s1")
    assert resp.source == ResponseSource.LLM
    assert resp.agent_action == AgentAction.LLM_FALLBACK
    assert rag.calls == 1
    assert llm.calls == 0
    assert len(cache.stored) == 1
    assert resp.cache_id == cache.stored[0]["id"]
    assert cache.stored[0]["response"] == "RAG-response"
    assert len(resp.citations) == 1
    assert resp.citations[0].file_path == "backend/app/services/query_router.py"
    assert len(publisher.events) == 1


@pytest.mark.asyncio
async def test_high_similarity_returns_cache_hit(settings):
    router, _, cache, _, llm, rag, _ = _build(settings, hits=[_hit(0.96)])
    resp = await router.handle_query("repeat query", "s1")
    assert resp.source == ResponseSource.CACHE
    assert resp.agent_action == AgentAction.CACHE_HIT
    assert llm.calls == 0
    assert rag.calls == 0
    assert cache.incremented == ["cid-1"]
    assert resp.citations == []


@pytest.mark.asyncio
async def test_gray_zone_validates_and_serves_cache(settings):
    router, _, cache, validator, llm, rag, _ = _build(
        settings, hits=[_hit(0.81)], validator_valid=True
    )
    resp = await router.handle_query("paraphrase", "s1")
    assert resp.source == ResponseSource.VALIDATED_CACHE
    assert resp.agent_action == AgentAction.VALIDATE
    assert validator.calls == 1
    assert llm.calls == 0
    assert rag.calls == 0
    assert cache.incremented == ["cid-1"]
    assert len(cache.stored) == 1
    assert cache.stored[0]["query"] == "paraphrase"
    assert cache.stored[0]["response"] == "cached r"
    assert resp.citations == []


@pytest.mark.asyncio
async def test_gray_zone_false_hit_falls_back_to_rag(settings):
    router, _, cache, validator, llm, rag, _ = _build(
        settings, hits=[_hit(0.81)], validator_valid=False
    )
    resp = await router.handle_query("different topic, similar wording", "s1")
    assert resp.source == ResponseSource.FALSE_HIT_FALLBACK
    assert resp.agent_action == AgentAction.LLM_FALLBACK
    assert validator.calls == 1
    assert rag.calls == 1
    assert llm.calls == 0
    assert len(cache.stored) == 1
    assert len(resp.citations) == 1
    assert resp.citations[0].file_path == "backend/app/services/query_router.py"
