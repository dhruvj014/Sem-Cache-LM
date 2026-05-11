"""Consumes QuerySubmitted from Redis Streams and runs stream RPC orchestration."""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import List

from redis.exceptions import ResponseError

from shared.config.settings import Settings
from shared.contracts.streams import (
    SCHEMA_VERSION_V1,
    AiCommandKind,
    AiCommandV1,
    AiResultV1,
    AnalyticsEventV1,
    CacheCommandKind,
    CacheCommandV1,
    CacheResultV1,
    ObservabilityEventV1,
    QueryCompletedV1,
    QuerySubmittedV1,
    RagCommandV1,
    RagResultV1,
    parse_payload_json,
)
from shared.infra.redis_client import RedisInfrastructure
from shared.infra.stream_runtime import (
    ensure_consumer_group,
    reclaim_stale_pending_messages,
    wait_cmd_result_json,
    xadd_model,
)
from shared.jobs.redis_jobs import (
    job_mark_completed,
    job_mark_failed,
    job_mark_processing,
)
from shared.models.enums import AgentAction, ResponseSource
from shared.models.schemas import CacheHit, Citation, QueryResponse
from shared.observability.logger import get_logger
from shared.observability.metrics import record_query_response_metrics
from services.orchestrator.app.domain.agent_decision import AgentDecisionLayer
from services.orchestrator.app.domain.false_hit_detector import FalseHitDetector
from services.orchestrator.app.domain.retrieval_rerank import rerank_hits_with_lexical_blend
from services.orchestrator.app.domain.retrieval_text import (
    build_index_text_for_vector,
    build_search_text_for_vector,
)
from services.orchestrator.app.domain.session_context import SessionContextService
from shared.stream_topology import (
    STREAM_AI_COMMANDS_V1,
    STREAM_ANALYTICS_EVENTS_V1,
    STREAM_CACHE_COMMANDS_V1,
    STREAM_OBSERVABILITY_EVENTS_V1,
    STREAM_QUERY_COMMANDS_V1,
    STREAM_QUERY_RESULTS_V1,
    STREAM_RAG_COMMANDS_V1,
)
from shared.utils.timer import timer

logger = get_logger(__name__)


def _prepare_rag_query(query: str) -> str:
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


class QueryStreamOrchestrator:
    def __init__(
        self,
        settings: Settings,
        redis_infra: RedisInfrastructure,
        agent: AgentDecisionLayer,
        session_context: SessionContextService,
        false_hit_detector: FalseHitDetector,
    ):
        self._settings = settings
        self._redis_infra = redis_infra
        self._agent = agent
        self._session = session_context
        self._validator = false_hit_detector

    @property
    def _r(self):
        return self._redis_infra.client

    def _step_timeout(self) -> float:
        return float(self._settings.orchestrator_step_timeout_seconds)

    async def _emit_obs(
        self,
        *,
        correlation_id: str,
        job_id: str,
        command_id: str,
        event_type: str,
        step: str = "",
        last_known_good_step: str = "",
        awaiting_step: str = "",
        pending_command_ids: str = "",
        deadline_ms: float | None = None,
        detail: str = "",
    ) -> None:
        evt = ObservabilityEventV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=correlation_id,
            job_id=job_id,
            command_id=command_id,
            producer="orchestrator",
            event_type=event_type,  # type: ignore[arg-type]
            step=step,
            last_known_good_step=last_known_good_step,
            awaiting_step=awaiting_step,
            pending_command_ids=pending_command_ids,
            deadline_ms=deadline_ms,
            detail=detail,
        )
        await xadd_model(self._r, STREAM_OBSERVABILITY_EVENTS_V1, evt)

    async def _wait_ai(self, cmd: AiCommandV1) -> AiResultV1:
        await xadd_model(self._r, STREAM_AI_COMMANDS_V1, cmd)
        raw = await wait_cmd_result_json(
            self._r, cmd.command_id, timeout_s=self._step_timeout()
        )
        if not raw:
            raise TimeoutError(f"ai command timeout command_id={cmd.command_id}")
        res = AiResultV1.model_validate(raw)
        if not res.ok:
            raise RuntimeError(res.error or "ai failed")
        return res

    async def _wait_cache(self, cmd: CacheCommandV1) -> CacheResultV1:
        await xadd_model(self._r, STREAM_CACHE_COMMANDS_V1, cmd)
        raw = await wait_cmd_result_json(
            self._r, cmd.command_id, timeout_s=self._step_timeout()
        )
        if not raw:
            raise TimeoutError(f"cache command timeout command_id={cmd.command_id}")
        res = CacheResultV1.model_validate(raw)
        if not res.ok:
            raise RuntimeError(res.error or "cache failed")
        return res

    async def _wait_rag(self, cmd: RagCommandV1) -> RagResultV1:
        await xadd_model(self._r, STREAM_RAG_COMMANDS_V1, cmd)
        raw = await wait_cmd_result_json(
            self._r, cmd.command_id, timeout_s=self._step_timeout()
        )
        if not raw:
            raise TimeoutError(f"rag command timeout command_id={cmd.command_id}")
        res = RagResultV1.model_validate(raw)
        if not res.ok:
            raise RuntimeError(res.error or "rag failed")
        return res

    async def _embed(self, correlation_id: str, job_id: str, text: str) -> List[float]:
        cmd_id = str(uuid.uuid4())
        cmd = AiCommandV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=correlation_id,
            job_id=job_id,
            command_id=cmd_id,
            producer="orchestrator",
            kind=AiCommandKind.embed,
            text=text,
        )
        res = await self._wait_ai(cmd)
        if not res.embedding:
            raise RuntimeError("empty embedding")
        return res.embedding

    async def _generate_plain(self, correlation_id: str, job_id: str, prompt: str) -> str:
        cmd_id = str(uuid.uuid4())
        cmd = AiCommandV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=correlation_id,
            job_id=job_id,
            command_id=cmd_id,
            producer="orchestrator",
            kind=AiCommandKind.generate,
            text=prompt,
        )
        res = await self._wait_ai(cmd)
        return res.generated_text or ""

    async def _cache_search(
        self, correlation_id: str, job_id: str, embedding: List[float], top_k: int
    ) -> List[CacheHit]:
        cmd_id = str(uuid.uuid4())
        cmd = CacheCommandV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=correlation_id,
            job_id=job_id,
            command_id=cmd_id,
            producer="orchestrator",
            kind=CacheCommandKind.search,
            embedding=embedding,
            top_k=top_k,
        )
        res = await self._wait_cache(cmd)
        return [CacheHit.model_validate(h) for h in res.hits]

    async def _cache_increment(self, correlation_id: str, job_id: str, cache_id: str) -> None:
        cmd_id = str(uuid.uuid4())
        cmd = CacheCommandV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=correlation_id,
            job_id=job_id,
            command_id=cmd_id,
            producer="orchestrator",
            kind=CacheCommandKind.increment_hit,
            cache_id=cache_id,
        )
        await self._wait_cache(cmd)

    async def _cache_store(
        self,
        correlation_id: str,
        job_id: str,
        *,
        query: str,
        embedding: List[float],
        response: str,
        metadata: dict,
    ) -> str | None:
        cmd_id = str(uuid.uuid4())
        cmd = CacheCommandV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=correlation_id,
            job_id=job_id,
            command_id=cmd_id,
            producer="orchestrator",
            kind=CacheCommandKind.store,
            query=query,
            embedding=embedding,
            response=response,
            metadata=metadata or {},
        )
        res = await self._wait_cache(cmd)
        return res.cache_id

    async def _rag_answer(self, correlation_id: str, job_id: str, q: str) -> RagResultV1:
        cmd_id = str(uuid.uuid4())
        cmd = RagCommandV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=correlation_id,
            job_id=job_id,
            command_id=cmd_id,
            producer="orchestrator",
            query=q,
        )
        return await self._wait_rag(cmd)

    def _citations(self, rr: RagResultV1) -> List[Citation]:
        out: List[Citation] = []
        for c in rr.citations:
            out.append(
                Citation(
                    file_path=str(c.get("file_path", "")),
                    score=float(c.get("score", 0.0)),
                    snippet=str(c.get("snippet", "")),
                )
            )
        return out

    async def _publish_analytics(self, submitted: QuerySubmittedV1, payload: QueryResponse) -> None:
        cmd_id = str(uuid.uuid4())
        evt = AnalyticsEventV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=submitted.correlation_id,
            job_id=submitted.job_id,
            command_id=cmd_id,
            producer="orchestrator",
            query=submitted.query,
            source=payload.source.value,
            agent_action=payload.agent_action.value,
            similarity_score=payload.similarity_score,
            latency_ms=payload.latency_ms,
            cache_id=payload.cache_id,
            response_text=payload.response,
        )
        await xadd_model(self._r, STREAM_ANALYTICS_EVENTS_V1, evt)

    async def _execute_job(self, submitted: QuerySubmittedV1) -> None:
        query = submitted.query
        session_id = submitted.session_id
        correlation_id = submitted.correlation_id
        job_id = submitted.job_id
        self._current_job_id = job_id
        self._current_correlation_id = correlation_id

        await self._emit_obs(
            correlation_id=correlation_id,
            job_id=job_id,
            command_id=submitted.command_id,
            event_type="step_started",
            step="job_start",
        )

        try:
            with timer() as total:
                rag_query = _prepare_rag_query(query)
                last_q, last_snip = await self._session.get(session_id)
                search_text = build_search_text_for_vector(
                    last_q,
                    last_snip,
                    query,
                    self._settings.cache_session_snippet_max_chars,
                )
                embedding = await self._embed(correlation_id, job_id, search_text)

                try:
                    hits = await self._cache_search(
                        correlation_id,
                        job_id,
                        embedding,
                        self._settings.cache_search_top_k,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "orchestrator.cache_search_degraded",
                        error_type=type(e).__name__,
                        error_repr=repr(e),
                    )
                    hits = []

                hits = rerank_hits_with_lexical_blend(
                    query,
                    hits,
                    self._settings.cache_rerank_lexical_weight,
                    quality_weight=self._settings.cache_rerank_quality_weight,
                    popularity_weight=self._settings.cache_rerank_popularity_weight,
                    popularity_cap=self._settings.cache_rerank_popularity_cap,
                )

                decision = self._agent.decide(
                    hits,
                    hit_threshold=submitted.similarity_hit_threshold,
                    gray_zone_low=submitted.similarity_gray_zone_low,
                )
                response_payload: QueryResponse
                if decision.action == AgentAction.CACHE_HIT and decision.matched_hit:
                    hit = decision.matched_hit
                    try:
                        await self._cache_increment(correlation_id, job_id, hit.id)
                    except Exception as e:  # noqa: BLE001
                        logger.warning("orchestrator.increment_hit_failed", cache_id=hit.id, error_repr=repr(e))
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
                            await self._cache_increment(correlation_id, job_id, hit.id)
                        except Exception as e:  # noqa: BLE001
                            logger.warning("orchestrator.increment_hit_failed", cache_id=hit.id, error_repr=repr(e))
                        idx_text = build_index_text_for_vector(
                            query,
                            hit.response,
                            self._settings.cache_index_response_max_chars,
                        )
                        idx_emb = await self._embed(correlation_id, job_id, idx_text)
                        try:
                            await self._cache_store(
                                correlation_id,
                                job_id,
                                query=query,
                                embedding=idx_emb,
                                response=hit.response,
                                metadata={"session_id": session_id, "validated_from_cache_id": hit.id},
                            )
                        except Exception as e:  # noqa: BLE001
                            logger.warning("orchestrator.store_failed", error_repr=repr(e))
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
                        rag_result = await self._rag_answer(correlation_id, job_id, rag_query)
                        llm_response = (
                            rag_result.answer
                            if rag_result.answer
                            else await self._generate_plain(correlation_id, job_id, query)
                        )
                        idx_text = build_index_text_for_vector(query, llm_response, self._settings.cache_index_response_max_chars)
                        idx_emb = await self._embed(correlation_id, job_id, idx_text)
                        new_id = None
                        try:
                            new_id = await self._cache_store(
                                correlation_id,
                                job_id,
                                query=query,
                                embedding=idx_emb,
                                response=llm_response,
                                metadata={
                                    "session_id": session_id,
                                    "rag_citations": [str(x.get("file_path", "")) for x in rag_result.citations],
                                },
                            )
                        except Exception as e:  # noqa: BLE001
                            logger.warning("orchestrator.store_failed", error_repr=repr(e))
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
                            citations=self._citations(rag_result),
                        )
                else:
                    rag_result = await self._rag_answer(correlation_id, job_id, rag_query)
                    llm_response = (
                        rag_result.answer
                        if rag_result.answer
                        else await self._generate_plain(correlation_id, job_id, query)
                    )
                    top_score = hits[0].score if hits else 0.0
                    idx_text = build_index_text_for_vector(query, llm_response, self._settings.cache_index_response_max_chars)
                    idx_emb = await self._embed(correlation_id, job_id, idx_text)
                    new_id = None
                    try:
                        new_id = await self._cache_store(
                            correlation_id,
                            job_id,
                            query=query,
                            embedding=idx_emb,
                            response=llm_response,
                            metadata={
                                "session_id": session_id,
                                "rag_citations": [str(x.get("file_path", "")) for x in rag_result.citations],
                            },
                        )
                    except Exception as e:  # noqa: BLE001
                        logger.warning("orchestrator.store_failed", error_repr=repr(e))
                    response_payload = QueryResponse(
                        response=llm_response,
                        source=ResponseSource.LLM,
                        cache_id=new_id,
                        similarity_score=top_score,
                        decision_reason=(
                            f"{decision.reason} Answer generated via RAG synthesis."
                            if rag_result.answer
                            else decision.reason
                        ),
                        latency_ms=0.0,
                        agent_action=AgentAction.LLM_FALLBACK,
                        citations=self._citations(rag_result),
                    )

            response_payload.latency_ms = round(total.elapsed_ms, 2)
            record_query_response_metrics(response_payload)
            await self._session.set(
                session_id,
                query,
                response_payload.response,
                self._settings.cache_session_snippet_max_chars,
            )
            await job_mark_completed(
                self._r,
                job_id,
                result_json=response_payload.model_dump_json(),
            )
            qc = str(uuid.uuid4())
            done = QueryCompletedV1(
                schema_version=SCHEMA_VERSION_V1,
                correlation_id=correlation_id,
                job_id=job_id,
                command_id=qc,
                producer="orchestrator",
                response_json=response_payload.model_dump_json(),
            )
            await xadd_model(self._r, STREAM_QUERY_RESULTS_V1, done)
            if self._settings.analytics_via_stream:
                await self._publish_analytics(submitted, response_payload)
            await self._emit_obs(
                correlation_id=correlation_id,
                job_id=job_id,
                command_id=submitted.command_id,
                event_type="step_completed",
                step="job_complete",
            )
        finally:
            self._current_job_id = None
            self._current_correlation_id = None

    async def _handle_query_message(self, stream: str, group: str, msg_id: str, fields: dict) -> None:
        r = self._r
        submitted = parse_payload_json(fields, QuerySubmittedV1)
        assert isinstance(submitted, QuerySubmittedV1)
        try:
            await job_mark_processing(r, submitted.job_id)
            await self._execute_job(submitted)
            await r.xack(stream, group, msg_id)
        except Exception as e:  # noqa: BLE001
            logger.exception("orchestrator.job_failed", job_id=submitted.job_id, error=str(e))
            await job_mark_failed(r, submitted.job_id, error=str(e))
            await self._emit_obs(
                correlation_id=submitted.correlation_id,
                job_id=submitted.job_id,
                command_id=submitted.command_id,
                event_type="orchestrator_watchdog",
                step="job_failed",
                last_known_good_step="unknown",
                awaiting_step="terminal",
                detail=str(e),
                deadline_ms=self._step_timeout() * 1000,
            )
            await r.xack(stream, group, msg_id)

    async def run_forever(self) -> None:
        r = self._r
        stream = STREAM_QUERY_COMMANDS_V1
        group = self._settings.orchestrator_consumer_group
        suffix = self._settings.orchestrator_consumer_name_suffix or uuid.uuid4().hex[:8]
        consumer = f"orch-{os.getpid()}-{suffix}"
        await ensure_consumer_group(r, stream, group)
        logger.info("orchestrator.loop_started", consumer=consumer, group=group)

        while True:
            try:
                for msg_id, fields in await reclaim_stale_pending_messages(
                    r,
                    stream=stream,
                    group=group,
                    consumer=consumer,
                    min_idle_ms=self._settings.stream_reclaim_min_idle_ms,
                ):
                    await self._handle_query_message(stream, group, msg_id, fields)

                resp = await r.xreadgroup(
                    groupname=group,
                    consumername=consumer,
                    streams={stream: ">"},
                    count=3,
                    block=3000,
                )
            except asyncio.CancelledError:
                raise
            except ResponseError as e:
                logger.warning("orchestrator.read_error", error=str(e))
                await asyncio.sleep(1.0)
                continue

            if not resp:
                continue

            for _, messages in resp:
                for msg_id, fields in messages:
                    await self._handle_query_message(stream, group, msg_id, fields)
