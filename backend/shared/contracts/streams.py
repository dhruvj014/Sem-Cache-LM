"""Canonical Redis Stream payloads (v1). Producers/consumers share these models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA_VERSION_V1 = 1


class StreamMeta(BaseModel):
    schema_version: int = Field(default=SCHEMA_VERSION_V1, ge=1)
    correlation_id: str = Field(..., min_length=1)
    job_id: str = Field(..., min_length=1)
    command_id: str = Field(..., min_length=1)
    trace_id: str = ""
    producer: str = ""
    attempt: int = Field(default=1, ge=1)
    emitted_at: str = Field(default_factory=_utc_iso)


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    degraded = "degraded"


class QuerySubmittedV1(StreamMeta):
    """Gateway -> orchestrator."""

    query: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., min_length=1, max_length=128)
    similarity_hit_threshold: Optional[float] = Field(default=None, ge=0.5, le=1.0)
    similarity_gray_zone_low: Optional[float] = Field(default=None, ge=0.0, le=0.99)


class QueryCompletedV1(StreamMeta):
    """Orchestrator -> optional query_results fan-out."""

    response_json: str = Field(..., min_length=1)


class QueryFailedV1(StreamMeta):
    error: str = Field(..., min_length=1)
    degraded: bool = False


class AiCommandKind(str, Enum):
    embed = "embed"
    generate = "generate"


class AiCommandV1(StreamMeta):
    kind: AiCommandKind
    text: str = Field(..., min_length=1)
    system: Optional[str] = None
    include_sparse: bool = False


class AiResultV1(StreamMeta):
    ok: bool = True
    error: Optional[str] = None
    embedding: Optional[list[float]] = None
    vector_size: int = 0
    generated_text: Optional[str] = None
    latency_ms: float = 0.0
    sparse_indices: list[int] = Field(default_factory=list)
    sparse_values: list[float] = Field(default_factory=list)


class CacheCommandKind(str, Enum):
    search = "search"
    store = "store"
    increment_hit = "increment_hit"


class CacheCommandV1(StreamMeta):
    kind: CacheCommandKind
    embedding: Optional[list[float]] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=100)
    query: Optional[str] = None
    response: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    cache_id: Optional[str] = None
    sparse_indices: list[int] = Field(default_factory=list)
    sparse_values: list[float] = Field(default_factory=list)


class CacheResultV1(StreamMeta):
    ok: bool = True
    error: Optional[str] = None
    hits: list[dict[str, Any]] = Field(default_factory=list)
    cache_id: Optional[str] = None


class RagCommandV1(StreamMeta):
    query: str = Field(..., min_length=1)


class RagResultV1(StreamMeta):
    ok: bool = True
    error: Optional[str] = None
    answer: str = ""
    citations: list[dict[str, Any]] = Field(default_factory=list)


class AnalyticsEventV1(StreamMeta):
    query: str
    source: str
    agent_action: str
    similarity_score: float
    latency_ms: float
    cache_id: Optional[str] = None
    response_text: str = ""


class ObservabilityEventV1(StreamMeta):
    event_type: Literal[
        "step_started",
        "step_completed",
        "orchestrator_watchdog",
        "pipeline_stalled",
        "worker_error",
    ]
    step: str = ""
    last_known_good_step: str = ""
    awaiting_step: str = ""
    pending_command_ids: str = ""
    deadline_ms: Optional[float] = None
    detail: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class DeadLetterV1(StreamMeta):
    """DLQ envelope — original stream + payload JSON + reason."""

    original_stream: str
    original_payload_json: str
    reason: str


def redis_payload(model: BaseModel) -> dict[str, str]:
    return {"payload": model.model_dump_json()}


def parse_payload_json(data: dict[str, str], model_cls: type[BaseModel]) -> BaseModel:
    raw = data.get("payload") or data.get("data") or "{}"
    return model_cls.model_validate_json(raw)
