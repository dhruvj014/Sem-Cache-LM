from app.config import Settings
from app.models.enums import AgentAction, ResponseSource
from app.models.schemas import QueryResponse
from app.services.agent_decision import AgentDecisionLayer
from app.services.analytics_service import AnalyticsService
from app.services.base.cache_base import CacheReader, CacheWriter
from app.services.base.embedding_base import EmbeddingService
from app.services.base.llm_base import LLMClient
from app.services.false_hit_detector import FalseHitDetector
from app.services.retrieval_rerank import rerank_hits_with_lexical_blend
from app.services.retrieval_text import (
    build_index_text_for_vector,
    build_search_text_for_vector,
)
from app.services.session_context import NullSessionContextService, SessionContextService
from app.utils.logger import get_logger
from app.utils.timer import timer

logger = get_logger(__name__)


class QueryRouterService:
    """Top-level orchestrator. Receives all dependencies via constructor
    injection (Dependency Inversion). Knows about CacheReader and
    CacheWriter as separate roles."""

    def __init__(
        self,
        settings: Settings,
        embedder: EmbeddingService,
        cache_reader: CacheReader,
        cache_writer: CacheWriter,
        agent: AgentDecisionLayer,
        false_hit_detector: FalseHitDetector,
        llm: LLMClient,
        analytics: AnalyticsService,
        session_context: SessionContextService | NullSessionContextService | None = None,
    ):
        self._settings = settings
        self._embedder = embedder
        self._reader = cache_reader
        self._writer = cache_writer
        self._agent = agent
        self._validator = false_hit_detector
        self._llm = llm
        self._analytics = analytics
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
            last_q, last_snip = await self._session.get(session_id)
            search_text = build_search_text_for_vector(
                last_q,
                last_snip,
                query,
                self._settings.cache_session_snippet_max_chars,
            )
            embedding = await self._embedder.embed(search_text)
            hits = await self._reader.search(
                embedding, top_k=self._settings.cache_search_top_k
            )
            hits = rerank_hits_with_lexical_blend(
                query,
                hits,
                self._settings.cache_rerank_lexical_weight,
            )

            decision = self._agent.decide(
                hits,
                hit_threshold=similarity_hit_threshold,
                gray_zone_low=similarity_gray_zone_low,
            )

            response_payload: QueryResponse

            if decision.action == AgentAction.CACHE_HIT and decision.matched_hit:
                hit = decision.matched_hit
                await self._writer.increment_hit(hit.id)
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
                    await self._writer.increment_hit(hit.id)
                    idx_text = build_index_text_for_vector(
                        query,
                        hit.response,
                        self._settings.cache_index_response_max_chars,
                    )
                    idx_emb = await self._embedder.embed(idx_text)
                    await self._writer.store(
                        query=query,
                        embedding=idx_emb,
                        response=hit.response,
                        metadata={
                            "session_id": session_id,
                            "validated_from_cache_id": hit.id,
                        },
                    )
                    response_payload = QueryResponse(
                        response=hit.response,
                        source=ResponseSource.VALIDATED_CACHE,
                        cache_id=hit.id,
                        similarity_score=hit.score,
                        decision_reason=(
                            f"{decision.reason} Validator: {validation.reason}"
                        ),
                        latency_ms=0.0,
                        agent_action=AgentAction.VALIDATE,
                        matched_query=hit.query,
                        quality_score=hit.quality_score,
                        hit_count=hit.hit_count + 1,
                        validation_confidence=validation.confidence,
                    )
                else:
                    llm_response = await self._llm.generate(query)
                    idx_text = build_index_text_for_vector(
                        query,
                        llm_response,
                        self._settings.cache_index_response_max_chars,
                    )
                    idx_emb = await self._embedder.embed(idx_text)
                    new_id = await self._writer.store(
                        query=query,
                        embedding=idx_emb,
                        response=llm_response,
                        metadata={"session_id": session_id},
                    )
                    response_payload = QueryResponse(
                        response=llm_response,
                        source=ResponseSource.FALSE_HIT_FALLBACK,
                        cache_id=new_id,
                        similarity_score=hit.score,
                        decision_reason=(
                            f"False hit detected. {validation.reason} Falling back to LLM."
                        ),
                        latency_ms=0.0,
                        agent_action=AgentAction.LLM_FALLBACK,
                        matched_query=hit.query,
                        validation_confidence=validation.confidence,
                    )

            else:
                llm_response = await self._llm.generate(query)
                top_score = hits[0].score if hits else 0.0
                idx_text = build_index_text_for_vector(
                    query,
                    llm_response,
                    self._settings.cache_index_response_max_chars,
                )
                idx_emb = await self._embedder.embed(idx_text)
                new_id = await self._writer.store(
                    query=query,
                    embedding=idx_emb,
                    response=llm_response,
                    metadata={"session_id": session_id},
                )
                response_payload = QueryResponse(
                    response=llm_response,
                    source=ResponseSource.LLM,
                    cache_id=new_id,
                    similarity_score=top_score,
                    decision_reason=decision.reason,
                    latency_ms=0.0,
                    agent_action=AgentAction.LLM_FALLBACK,
                )

        response_payload.latency_ms = round(total.elapsed_ms, 2)

        await self._session.set(
            session_id,
            query,
            response_payload.response,
            self._settings.cache_session_snippet_max_chars,
        )

        await self._analytics.record_query(
            query=query,
            source=response_payload.source,
            agent_action=response_payload.agent_action,
            similarity_score=response_payload.similarity_score,
            latency_ms=response_payload.latency_ms,
            cache_id=response_payload.cache_id,
            response_text=response_payload.response,
        )

        return response_payload
