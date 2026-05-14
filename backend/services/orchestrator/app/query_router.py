import asyncio
from typing import Protocol

from shared.domain.cache_boundary import CacheBoundary
from shared.domain.rag_ports import RagClient
from shared.config.settings import Settings
from shared.domain.model_providers import EmbeddingService, LLMClient
from shared.models.enums import AgentAction, ResponseSource
from shared.models.schemas import Citation, QueryResponse
from shared.observability.logger import get_logger
from shared.observability.metrics import record_query_response_metrics
from services.orchestrator.app.domain.agent_decision import AgentDecisionLayer
from services.orchestrator.app.domain.false_hit_detector import FalseHitDetector
from services.orchestrator.app.domain.retrieval_rerank import rerank_hits_with_lexical_blend
from services.orchestrator.app.domain.retrieval_text import (
    build_index_text_for_vector,
    build_search_text_for_vector,
)
from services.orchestrator.app.domain.session_context import (
    NullSessionContextService,
    SessionContextService,
)
from shared.utils.timer import timer

logger = get_logger(__name__)


class AnalyticsPublishPort(Protocol):
    async def publish(self, *, query: str, response: QueryResponse) -> None: ...


class QueryRouterService:
    def __init__(
        self,
        settings: Settings,
        embedder: EmbeddingService,
        cache_reader: CacheBoundary,
        cache_writer: CacheBoundary,
        agent: AgentDecisionLayer,
        false_hit_detector: FalseHitDetector,
        llm: LLMClient,
        rag: RagClient | None,
        analytics_publisher: AnalyticsPublishPort | None = None,
        session_context: SessionContextService | NullSessionContextService | None = None,
    ):
        self._settings = settings
        self._embedder = embedder
        self._reader = cache_reader
        self._writer = cache_writer
        self._agent = agent
        self._validator = false_hit_detector
        self._llm = llm
        self._rag = rag
        self._analytics_publisher = analytics_publisher
        self._session = session_context or NullSessionContextService()

    async def handle_query(
        self,
        query: str,
        session_id: str,
        *,
        similarity_hit_threshold: float | None = None,
        similarity_gray_zone_low: float | None = None,
    ) -> QueryResponse:
        with timer() as total:
            rag_query = self._prepare_rag_query(query)
            last_q, last_snip = await self._session.get(session_id)
            search_text = build_search_text_for_vector(
                last_q,
                last_snip,
                query,
                self._settings.cache_session_snippet_max_chars,
            )
            embedding, (sparse_idx, sparse_val) = await asyncio.gather(
                self._embedder.embed(search_text),
                self._embedder.sparse_encode(search_text),
            )
            try:
                hits = await self._reader.search(
                    embedding,
                    top_k=self._settings.cache_search_top_k,
                    sparse_indices=sparse_idx,
                    sparse_values=sparse_val,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "cache.search_degraded",
                    error_type=type(e).__name__,
                    error_repr=repr(e),
                )
                hits = []
            hits = rerank_hits_with_lexical_blend(
                hits,
                quality_weight=self._settings.cache_rerank_quality_weight,
                popularity_weight=self._settings.cache_rerank_popularity_weight,
                popularity_cap=self._settings.cache_rerank_popularity_cap,
            )

            decision = self._agent.decide(
                hits,
                hit_threshold=similarity_hit_threshold,
                gray_zone_low=similarity_gray_zone_low,
            )

            response_payload: QueryResponse
            if decision.action == AgentAction.CACHE_HIT and decision.matched_hit:
                hit = decision.matched_hit
                try:
                    await self._writer.increment_hit(hit.id)
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "cache.increment_hit_failed",
                        cache_id=hit.id,
                        error_type=type(e).__name__,
                        error_repr=repr(e),
                    )
                response_payload = QueryResponse(
                    response=hit.response,
                    source=ResponseSource.CACHE,
                    cache_id=hit.id,
                    similarity_score=hit.score,
                    decision_reason=decision.reason,
                    latency_ms=0.0,
                    agent_action=AgentAction.CACHE_HIT,
                    matched_query=hit.query,
                    quality_score=hit.quality_score,
                    hit_count=hit.hit_count + 1,
                    citations=[],
                )
            elif decision.action == AgentAction.VALIDATE and decision.matched_hit:
                hit = decision.matched_hit
                validation = await self._validator.validate(
                    incoming_query=query,
                    candidate_response=hit.response,
                    similarity_score=hit.score,
                    cache_id=hit.id,
                )
                if validation.is_valid:
                    try:
                        await self._writer.increment_hit(hit.id)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "cache.increment_hit_failed",
                            cache_id=hit.id,
                            error_type=type(e).__name__,
                            error_repr=repr(e),
                        )
                    idx_text = build_index_text_for_vector(
                        query,
                        hit.response,
                        self._settings.cache_index_response_max_chars,
                    )
                    idx_emb, (idx_sparse_idx, idx_sparse_val) = await asyncio.gather(
                        self._embedder.embed(idx_text),
                        self._embedder.sparse_encode(idx_text),
                    )
                    try:
                        await self._writer.store(
                            query=query,
                            embedding=idx_emb,
                            response=hit.response,
                            metadata={
                                "session_id": session_id,
                                "validated_from_cache_id": hit.id,
                            },
                            sparse_indices=idx_sparse_idx,
                            sparse_values=idx_sparse_val,
                        )
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "cache.store_failed",
                            error_type=type(e).__name__,
                            error_repr=repr(e),
                        )
                    response_payload = QueryResponse(
                        response=hit.response,
                        source=ResponseSource.VALIDATED_CACHE,
                        cache_id=hit.id,
                        similarity_score=hit.score,
                        decision_reason=f"{decision.reason} Validator: {validation.reason}",
                        latency_ms=0.0,
                        agent_action=AgentAction.VALIDATE,
                        matched_query=hit.query,
                        quality_score=hit.quality_score,
                        hit_count=hit.hit_count + 1,
                        validation_confidence=validation.confidence,
                        citations=[],
                    )
                else:
                    rag_result = await self._rag.answer(rag_query) if self._rag else None
                    llm_response = (
                        rag_result.response
                        if rag_result and rag_result.response
                        else await self._llm.generate(query)
                    )
                    idx_text = build_index_text_for_vector(
                        query,
                        llm_response,
                        self._settings.cache_index_response_max_chars,
                    )
                    idx_emb, (idx_sparse_idx, idx_sparse_val) = await asyncio.gather(
                        self._embedder.embed(idx_text),
                        self._embedder.sparse_encode(idx_text),
                    )
                    try:
                        new_id = await self._writer.store(
                            query=query,
                            embedding=idx_emb,
                            response=llm_response,
                            metadata={
                                "session_id": session_id,
                                "rag_citations": (
                                    [c.file_path for c in rag_result.citations]
                                    if rag_result
                                    else []
                                ),
                            },
                            sparse_indices=idx_sparse_idx,
                            sparse_values=idx_sparse_val,
                        )
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "cache.store_failed",
                            error_type=type(e).__name__,
                            error_repr=repr(e),
                        )
                        new_id = None
                    response_payload = QueryResponse(
                        response=llm_response,
                        source=ResponseSource.FALSE_HIT_FALLBACK,
                        cache_id=new_id,
                        similarity_score=hit.score,
                        decision_reason=f"False hit detected. {validation.reason} Falling back to RAG synthesis.",
                        latency_ms=0.0,
                        agent_action=AgentAction.LLM_FALLBACK,
                        matched_query=hit.query,
                        validation_confidence=validation.confidence,
                        citations=(
                            [
                                Citation(
                                    file_path=c.file_path,
                                    score=c.score,
                                    snippet=c.snippet,
                                )
                                for c in rag_result.citations
                            ]
                            if rag_result
                            else []
                        ),
                    )
            else:
                rag_result = await self._rag.answer(rag_query) if self._rag else None
                llm_response = (
                    rag_result.response
                    if rag_result and rag_result.response
                    else await self._llm.generate(query)
                )
                top_score = hits[0].score if hits else 0.0
                idx_text = build_index_text_for_vector(
                    query,
                    llm_response,
                    self._settings.cache_index_response_max_chars,
                )
                idx_emb, (idx_sparse_idx, idx_sparse_val) = await asyncio.gather(
                    self._embedder.embed(idx_text),
                    self._embedder.sparse_encode(idx_text),
                )
                try:
                    new_id = await self._writer.store(
                        query=query,
                        embedding=idx_emb,
                        response=llm_response,
                        metadata={
                            "session_id": session_id,
                            "rag_citations": (
                                [c.file_path for c in rag_result.citations]
                                if rag_result
                                else []
                            ),
                        },
                        sparse_indices=idx_sparse_idx,
                        sparse_values=idx_sparse_val,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "cache.store_failed",
                        error_type=type(e).__name__,
                        error_repr=repr(e),
                    )
                    new_id = None
                response_payload = QueryResponse(
                    response=llm_response,
                    source=ResponseSource.LLM,
                    cache_id=new_id,
                    similarity_score=top_score,
                    decision_reason=(
                        f"{decision.reason} Answer generated via RAG synthesis."
                        if rag_result and rag_result.response
                        else decision.reason
                    ),
                    latency_ms=0.0,
                    agent_action=AgentAction.LLM_FALLBACK,
                    citations=(
                        [
                            Citation(
                                file_path=c.file_path,
                                score=c.score,
                                snippet=c.snippet,
                            )
                            for c in rag_result.citations
                        ]
                        if rag_result
                        else []
                    ),
                )

        response_payload.latency_ms = round(total.elapsed_ms, 2)
        record_query_response_metrics(response_payload)
        await self._session.set(
            session_id,
            query,
            response_payload.response,
            self._settings.cache_session_snippet_max_chars,
        )

        if self._analytics_publisher is not None:
            try:
                await self._analytics_publisher.publish(query=query, response=response_payload)
            except Exception as e:  # noqa: BLE001
                logger.warning("analytics.stream_publish_failed", error=str(e))

        return response_payload

    def _prepare_rag_query(self, query: str) -> str:
        lowered = (query or "").lower()
        broad_markers = (
            "what does this repo do",
            "what does this codebase do",
            "what api",
            "list api",
            "endpoint",
            "overview",
            "architecture",
            "summarize this repo",
        )
        if any(m in lowered for m in broad_markers):
            return (
                "Prefer catalog documents for high-level explanations of repositories "
                "and APIs when relevant.\n\n"
                f"User query: {query}"
            )
        return query
