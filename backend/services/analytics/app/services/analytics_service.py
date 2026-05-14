"""Analytics read model (Redis). Microservice-owned."""

import json
from datetime import datetime, timezone
from typing import Optional

from shared.infra.redis_client import RedisInfrastructure
from shared.models.enums import AgentAction, ResponseSource
from shared.models.schemas import AnalyticsSummary, HistoryEntry, HistoryResponse
from shared.observability.logger import get_logger

logger = get_logger(__name__)

STATS_KEY = "semcache:stats"
HISTORY_KEY = "semcache:history"
LAST_DECISION_KEY = "semcache:last_decision"
HISTORY_LIMIT = 200
ANALYTICS_JOB_DEDUPE_PREFIX = "semcache:analytics:dedupe:"
ANALYTICS_JOB_DEDUPE_TTL_SECONDS = 172_800  # 48h; job hash TTL is shorter, ids are UUIDs

CHARS_PER_TOKEN = 4


class AnalyticsService:
    """Aggregate stats + recent history in Redis only (no direct Qdrant reads)."""

    def __init__(self, redis_infra: RedisInfrastructure):
        self._redis = redis_infra

    async def reset(self) -> None:
        r = self._redis.client
        await r.delete(STATS_KEY, HISTORY_KEY, LAST_DECISION_KEY)
        logger.info("analytics.reset")

    async def record_query(
        self,
        query: str,
        source: ResponseSource,
        agent_action: AgentAction,
        similarity_score: float,
        latency_ms: float,
        cache_id: Optional[str],
        response_text: str,
        *,
        job_id: Optional[str] = None,
    ) -> None:
        r = self._redis.client
        if job_id:
            dedupe_key = f"{ANALYTICS_JOB_DEDUPE_PREFIX}{job_id}"
            if not await r.set(
                dedupe_key,
                "1",
                nx=True,
                ex=ANALYTICS_JOB_DEDUPE_TTL_SECONDS,
            ):
                logger.debug("analytics.record_query_skipped_duplicate", job_id=job_id)
                return

        pipe = r.pipeline()
        pipe.hincrby(STATS_KEY, "total_queries", 1)

        if agent_action == AgentAction.CACHE_HIT or source in (
            ResponseSource.CACHE,
            ResponseSource.VALIDATED_CACHE,
        ):
            pipe.hincrby(STATS_KEY, "cache_hits", 1)
            pipe.hincrbyfloat(STATS_KEY, "sum_cache_latency_ms", latency_ms)
            pipe.hincrby(STATS_KEY, "n_cache", 1)
            estimated_tokens = max(1, len(response_text) // CHARS_PER_TOKEN)
            pipe.hincrby(STATS_KEY, "estimated_tokens_saved", estimated_tokens)

        if source == ResponseSource.LLM or source == ResponseSource.FALSE_HIT_FALLBACK:
            pipe.hincrby(STATS_KEY, "llm_calls", 1)
            pipe.hincrbyfloat(STATS_KEY, "sum_llm_latency_ms", latency_ms)
            pipe.hincrby(STATS_KEY, "n_llm", 1)

        if agent_action == AgentAction.VALIDATE:
            pipe.hincrby(STATS_KEY, "validate_decisions", 1)

        if source == ResponseSource.FALSE_HIT_FALLBACK:
            pipe.hincrby(STATS_KEY, "false_hits", 1)

        entry = HistoryEntry(
            query=query,
            source=source,
            agent_action=agent_action,
            similarity_score=similarity_score,
            latency_ms=latency_ms,
            cache_id=cache_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        pipe.lpush(HISTORY_KEY, entry.model_dump_json())
        pipe.ltrim(HISTORY_KEY, 0, HISTORY_LIMIT - 1)

        last = {
            "agent_action": agent_action.value,
            "source": source.value,
            "similarity_score": similarity_score,
            "latency_ms": latency_ms,
            "cache_id": cache_id,
            "query_preview": query[:120],
            "timestamp": entry.timestamp,
        }
        pipe.set(LAST_DECISION_KEY, json.dumps(last))

        avg_llm_latency = await self._get_avg_llm_latency()
        if avg_llm_latency > 0 and agent_action == AgentAction.CACHE_HIT:
            saved = max(0.0, avg_llm_latency - latency_ms)
            pipe.hincrbyfloat(STATS_KEY, "estimated_time_saved_ms", saved)

        await pipe.execute()

    async def _get_avg_llm_latency(self) -> float:
        r = self._redis.client
        n = await r.hget(STATS_KEY, "n_llm")
        s = await r.hget(STATS_KEY, "sum_llm_latency_ms")
        n_v = int(n) if n else 0
        s_v = float(s) if s else 0.0
        return s_v / n_v if n_v > 0 else 0.0

    async def summary(self) -> AnalyticsSummary:
        r = self._redis.client
        raw = await r.hgetall(STATS_KEY)

        def _i(k: str) -> int:
            return int(raw.get(k, 0) or 0)

        def _f(k: str) -> float:
            return float(raw.get(k, 0) or 0.0)

        total = _i("total_queries")
        cache_hits = _i("cache_hits")
        llm_calls = _i("llm_calls")
        n_cache = _i("n_cache")
        n_llm = _i("n_llm")
        sum_cache = _f("sum_cache_latency_ms")
        sum_llm = _f("sum_llm_latency_ms")

        hit_rate = cache_hits / total if total > 0 else 0.0
        avg_cache = sum_cache / n_cache if n_cache > 0 else 0.0
        avg_llm = sum_llm / n_llm if n_llm > 0 else 0.0

        cache_entries = _i("cache_entries")

        last_raw = await r.get(LAST_DECISION_KEY)
        last = json.loads(last_raw) if last_raw else None

        return AnalyticsSummary(
            total_queries=total,
            cache_hits=cache_hits,
            llm_calls=llm_calls,
            validate_decisions=_i("validate_decisions"),
            false_hits=_i("false_hits"),
            hit_rate=hit_rate,
            avg_cache_latency_ms=avg_cache,
            avg_llm_latency_ms=avg_llm,
            cache_entries=cache_entries,
            estimated_tokens_saved=_i("estimated_tokens_saved"),
            estimated_time_saved_ms=_f("estimated_time_saved_ms"),
            last_decision=last,
        )

    async def history(self, limit: int = 20) -> HistoryResponse:
        raw = await self._redis.client.lrange(HISTORY_KEY, 0, limit - 1)
        entries = [HistoryEntry.model_validate_json(item) for item in raw]
        return HistoryResponse(entries=entries)
