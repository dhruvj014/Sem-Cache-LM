from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class InternalEmbedRequest(BaseModel):
    text: str = Field(..., min_length=1)


class InternalEmbedResponse(BaseModel):
    embedding: list[float]
    vector_size: int
    latency_ms: float
    provider: str


class InternalSparseEmbedRequest(BaseModel):
    text: str = Field(..., min_length=1)


class InternalSparseEmbedResponse(BaseModel):
    indices: list[int]
    values: list[float]
    latency_ms: float


class InternalGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: Optional[str] = None


class InternalGenerateResponse(BaseModel):
    text: str
    latency_ms: float
    provider: str
    model: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float


class InternalRagRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1)


class InternalRagCitation(BaseModel):
    file_path: str
    score: float
    snippet: str


class InternalRagRetrieveResponse(BaseModel):
    answer: str
    citations: list[InternalRagCitation]


class InternalCacheSearchRequest(BaseModel):
    embedding: list[float]
    top_k: int = Field(default=5, ge=1, le=100)
    sparse_indices: list[int] = Field(default_factory=list)
    sparse_values: list[float] = Field(default_factory=list)


class InternalCacheSearchResponse(BaseModel):
    hits: list[dict[str, Any]]


class InternalCacheStoreRequest(BaseModel):
    query: str = Field(..., min_length=1)
    embedding: list[float]
    response: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    sparse_indices: list[int] = Field(default_factory=list)
    sparse_values: list[float] = Field(default_factory=list)


class InternalCacheStoreResponse(BaseModel):
    cache_id: str


class InternalCacheIncrementHitRequest(BaseModel):
    cache_id: str


class InternalCacheFeedbackRequest(BaseModel):
    cache_id: str
    action: Literal["promote", "demote"]
    new_quality: float = Field(..., ge=0.0, le=1.0)


class InternalCacheEvictRequest(BaseModel):
    threshold: float = Field(..., ge=0.0, le=1.0)


class InternalCacheEvictResponse(BaseModel):
    evicted_ids: list[str]
    evicted_count: int


class InternalQueryEvent(BaseModel):
    correlation_id: str
    query: str
    source: str
    agent_action: str
    similarity_score: float
    latency_ms: float
    cache_id: Optional[str] = None
    response_text: str
    emitted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InternalServiceHealth(BaseModel):
    service: str
    status: Literal["ok", "degraded"]
    details: dict[str, Any] = Field(default_factory=dict)


# --- Redis Stream contracts (v1) — single import surface for services ---
from shared.contracts.streams import (  # noqa: E402
    SCHEMA_VERSION_V1,
    AiCommandKind,
    AiCommandV1,
    AiResultV1,
    AnalyticsEventV1,
    CacheCommandKind,
    CacheCommandV1,
    CacheResultV1,
    DeadLetterV1,
    JobStatus,
    ObservabilityEventV1,
    QueryCompletedV1,
    QueryFailedV1,
    QuerySubmittedV1,
    RagCommandV1,
    RagResultV1,
    StreamMeta,
    parse_payload_json,
    redis_payload,
)

