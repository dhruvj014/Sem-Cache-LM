from datetime import datetime, timezone
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AgentAction, FeedbackRating, ResponseSource

T = TypeVar("T")


class ErrorPayload(BaseModel):
    code: str
    message: str


class ResponseEnvelope(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorPayload] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def ok(cls, data: T) -> "ResponseEnvelope[T]":
        return cls(success=True, data=data, error=None)

    @classmethod
    def fail(cls, code: str, message: str) -> "ResponseEnvelope[T]":
        return cls(success=False, data=None, error=ErrorPayload(code=code, message=message))


# ---- Query domain ----

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., min_length=1, max_length=128)
    similarity_hit_threshold: Optional[float] = Field(
        default=None,
        ge=0.5,
        le=1.0,
        description="Upper bound (cache hit). Overrides default for this request.",
    )
    similarity_gray_zone_low: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=0.99,
        description="Lower bound of gray zone (validate). Overrides default for this request.",
    )


class DecisionThresholdsData(BaseModel):
    similarity_hit_threshold: float
    similarity_gray_zone_low: float


class DecisionThresholdsUpdate(BaseModel):
    similarity_hit_threshold: float = Field(..., ge=0.5, le=1.0)
    similarity_gray_zone_low: float = Field(..., ge=0.0, le=0.99)

    @model_validator(mode="after")
    def gray_below_hit(self) -> "DecisionThresholdsUpdate":
        if self.similarity_gray_zone_low >= self.similarity_hit_threshold:
            raise ValueError(
                "similarity_gray_zone_low must be strictly less than similarity_hit_threshold"
            )
        return self


class CacheHit(BaseModel):
    id: str
    query: str
    response: str
    score: float
    hit_count: int = 0
    quality_score: float = 1.0


class QueryResponse(BaseModel):
    response: str
    source: ResponseSource
    cache_id: Optional[str] = None
    similarity_score: float = 0.0
    decision_reason: str
    latency_ms: float
    agent_action: AgentAction
    matched_query: Optional[str] = None
    quality_score: Optional[float] = None
    hit_count: Optional[int] = None
    validation_confidence: Optional[float] = None


# ---- Decision domain ----

class DecisionResult(BaseModel):
    action: AgentAction
    cache_id: Optional[str] = None
    confidence: float = 0.0
    reason: str
    matched_hit: Optional[CacheHit] = None


class ValidationResult(BaseModel):
    is_valid: bool
    confidence: float
    reason: str


# ---- Feedback domain ----

class FeedbackRequest(BaseModel):
    rating: FeedbackRating


class FeedbackResult(BaseModel):
    cache_id: str
    rating: FeedbackRating
    new_quality_score: float
    promoted: bool = False
    demoted: bool = False


# ---- Cache management ----

class CacheEntry(BaseModel):
    id: str
    query: str
    response: str
    quality_score: float
    hit_count: int
    created_at: str
    last_used_at: str
    promoted: bool = False
    demoted: bool = False


class CacheListResponse(BaseModel):
    entries: list[CacheEntry]
    total: int
    page: int
    page_size: int


class EvictionResult(BaseModel):
    evicted_ids: list[str]
    evicted_count: int


class ClearCacheResult(BaseModel):
    deleted_entries: int
    analytics_reset: bool


# ---- Analytics ----

class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    services: dict[str, bool]
    llm_model: str = ""
    embedding_model: str = ""
    qdrant_collection: str = ""


class AnalyticsSummary(BaseModel):
    total_queries: int
    cache_hits: int
    llm_calls: int
    validate_decisions: int
    false_hits: int
    hit_rate: float
    avg_cache_latency_ms: float
    avg_llm_latency_ms: float
    cache_entries: int
    estimated_tokens_saved: int
    estimated_time_saved_ms: float
    last_decision: Optional[dict[str, Any]] = None


class HistoryEntry(BaseModel):
    query: str
    source: ResponseSource
    agent_action: AgentAction
    similarity_score: float
    latency_ms: float
    cache_id: Optional[str] = None
    timestamp: str


class HistoryResponse(BaseModel):
    entries: list[HistoryEntry]
