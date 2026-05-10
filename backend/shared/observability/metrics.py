from prometheus_client import Counter, Histogram, Gauge

from shared.models.enums import AgentAction, ResponseSource
from shared.models.schemas import QueryResponse

# ── Decision counters ────────────────────────────────────────
CACHE_HIT_TOTAL = Counter(
    "semcachelm_cache_hits_total",
    "Queries served directly from semantic cache",
)
LLM_FALLBACK_TOTAL = Counter(
    "semcachelm_llm_fallback_total",
    "Queries that required full LLM inference",
)
VALIDATE_HIT_TOTAL = Counter(
    "semcachelm_validate_hits_total",
    "Gray-zone queries approved by LLM judge",
)
VALIDATE_MISS_TOTAL = Counter(
    "semcachelm_validate_misses_total",
    "Gray-zone queries rejected by LLM judge",
)

# ── Latency histograms ───────────────────────────────────────
LLM_LATENCY = Histogram(
    "semcachelm_llm_latency_seconds",
    "Latency of Ollama calls by type",
    labelnames=["call_type"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# ── Similarity score distribution ───────────────────────────
SIMILARITY_SCORE = Histogram(
    "semcachelm_similarity_score",
    "Cosine similarity score from Qdrant search",
    buckets=[
        0.0,
        0.5,
        0.6,
        0.65,
        0.70,
        0.75,
        0.80,
        0.85,
        0.90,
        0.92,
        0.95,
        0.98,
        1.0,
    ],
)

# ── Quality / feedback ───────────────────────────────────────
QUALITY_SCORE_OBSERVED = Histogram(
    "semcachelm_quality_score_observed",
    "EMA quality score recorded at feedback time",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# ── System state gauges ──────────────────────────────────────
CACHE_SIZE = Gauge(
    "semcachelm_cache_size_total",
    "Current number of entries in Qdrant collection",
)
EVICTIONS_TOTAL = Counter(
    "semcachelm_evictions_total",
    "Cache entries evicted due to low quality score",
)
STREAM_PENDING = Gauge(
    "semcachelm_redis_stream_pending",
    "Unacknowledged messages in Redis Streams queue",
)


def record_query_response_metrics(response_payload: QueryResponse) -> None:
    """Record decision and similarity metrics after a query outcome is resolved."""
    similarity_score = response_payload.similarity_score
    if similarity_score is not None and similarity_score > 0:
        SIMILARITY_SCORE.observe(float(similarity_score))
    aa = response_payload.agent_action
    src = response_payload.source
    if aa == AgentAction.CACHE_HIT:
        CACHE_HIT_TOTAL.inc()
    elif aa == AgentAction.VALIDATE:
        VALIDATE_HIT_TOTAL.inc()
    elif aa == AgentAction.LLM_FALLBACK and src == ResponseSource.FALSE_HIT_FALLBACK:
        VALIDATE_MISS_TOTAL.inc()
    elif aa == AgentAction.LLM_FALLBACK:
        LLM_FALLBACK_TOTAL.inc()
