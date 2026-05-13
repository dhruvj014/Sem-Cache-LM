from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    cors_origins: str = Field(default="http://localhost:5173")

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "semcachelm_cache"
    qdrant_vector_size: int = 768
    qdrant_api_key: str = Field(
        default="",
        description="API key for Qdrant Cloud.",
    )
    qdrant_https: bool = Field(
        default=False,
        description="Use HTTPS for Qdrant Cloud connections.",
    )

    rag_qdrant_host: str = Field(
        default="",
        description="Empty uses qdrant_host (same cluster, separate collection in dev).",
    )
    rag_qdrant_port: int = Field(
        default=0,
        description="0 uses qdrant_port.",
    )
    rag_qdrant_api_key: str = Field(
        default="",
        description="Empty uses qdrant_api_key.",
    )
    rag_qdrant_https: bool | None = Field(
        default=None,
        description="None uses qdrant_https.",
    )
    rag_qdrant_collection: str = Field(
        default="semcachelm_rag_chunks",
        description=(
            "Prefix for per-repo Qdrant collections: `{rag_qdrant_collection}__{repo_key}`. "
            "RAG service only; separate from semantic-cache QDRANT_COLLECTION."
        ),
    )
    rag_qdrant_vector_size: int = Field(
        default=0,
        ge=0,
        description="Vector dimension for RAG chunk embeddings in Qdrant; 0 uses qdrant_vector_size.",
    )
    rag_redis_manifest_prefix: str = Field(
        default="semcache:rag:index:v1",
        description="Redis key prefix for RAG index fingerprints / rebuild bookkeeping.",
    )

    redis_mode: Literal["inherit", "local", "aws"] = Field(
        default="inherit",
        description=(
            "inherit: use redis_host / redis_port / redis_ssl / redis_password from env as-is. "
            "local: Docker-friendly defaults (redis_local_*), TLS off. "
            "aws: ElastiCache / managed Redis via redis_aws_* (TLS on by default)."
        ),
    )
    redis_aws_host: str = Field(
        default="",
        description="Hostname when redis_mode=aws (e.g. *.serverless.*.cache.amazonaws.com).",
    )
    redis_aws_port: int = Field(default=6379, ge=1, le=65535)
    redis_aws_password: str = Field(
        default="",
        description="AUTH password/token when redis_mode=aws.",
    )
    redis_aws_ssl: bool = Field(
        default=True,
        description="TLS for AWS/managed Redis (Serverless ElastiCache expects true).",
    )
    redis_local_host: str = Field(
        default="redis",
        description="Service hostname when redis_mode=local (Compose service name).",
    )
    redis_local_port: int = Field(default=6379, ge=1, le=65535)
    redis_local_password: str = Field(
        default="",
        description="Optional password when redis_mode=local (e.g. local redis with requirepass).",
    )

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = Field(
        default="",
        description="Redis password (used for AWS ElastiCache AUTH).",
    )
    redis_ssl: bool = Field(
        default=False,
        description="Use SSL for Redis connection (required for ElastiCache in-transit encryption).",
    )

    # ── Security ──────────────────────────────────────────────────────────────
    internal_service_token: str = Field(
        default="",
        description=(
            "Shared bearer token for service-to-service /internal/v1/* routes. "
            "Empty string disables auth (safe for local dev). "
            "On AWS inject from Secrets Manager via INTERNAL_SERVICE_TOKEN env var."
        ),
    )

    # ── Google Gemini (embed + generate for AI + RAG) ─────────────────────────
    gemini_api_key: str = Field(default="", description="Google Gemini API key.")
    gemini_llm_model: str = Field(
        default="gemini-2.5-flash-lite",
        description="Gemini model for generation and judging.",
    )
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001",
        description=(
            "Gemini embedding model id; use outputDimensionality / Matryoshka to match "
            "qdrant_vector_size (768)."
        ),
    )
    gemini_timeout_seconds: float = Field(
        default=120.0,
        ge=5.0,
        le=600.0,
        description="HTTP timeout for Gemini REST calls (embed + generate).",
    )
    llm_no_rag_system_prompt: str = Field(
        default=(
            "You are answering the user's question without any retrieved repository or "
            "document passages (RAG was not used or returned nothing relevant). "
            "Answer from general knowledge: be accurate, concise, and direct. "
            "Do not invent citations, file paths, or quotes from a codebase you have not seen. "
            "If the question requires access to their private project or files, say you do not have "
            "that context and give best-effort general guidance or ask what they can share."
        ),
        description=(
            "System instruction for orchestrator plain-LLM fallbacks when there is no usable RAG context."
        ),
    )

    similarity_hit_threshold: float = 0.92
    similarity_gray_zone_low: float = 0.7

    quality_ema_alpha: float = 0.2
    quality_eviction_threshold: float = 0.3

    cache_search_top_k: int = Field(
        default=2,
        description="Neighbors to fetch from Qdrant before lexical rerank.",
    )
    cache_index_response_max_chars: int = Field(
        default=1200,
        description="Response chars included in vector text at store time.",
    )
    cache_session_snippet_max_chars: int = Field(
        default=450,
        description="Excerpt of last answer in session-aware search embedding.",
    )
    cache_rerank_lexical_weight: float = Field(
        default=0.22,
        ge=0.0,
        le=1.0,
        description="Blend: (1-w)*dense + w*lexical overlap.",
    )
    cache_rerank_quality_weight: float = Field(
        default=0.08,
        ge=0.0,
        le=0.3,
        description=(
            "Weight given to validated quality score during reranking. "
            "Entries with quality < 0.5 are penalised; high-quality entries get a boost. "
            "Combined quality+popularity weights must leave ≥0.5 for the base dense+lexical score."
        ),
    )
    cache_rerank_popularity_weight: float = Field(
        default=0.04,
        ge=0.0,
        le=0.2,
        description=(
            "Weight given to log-scaled hit count during reranking. "
            "Entries that have been successfully served many times get a small boost, "
            "capped at POPULARITY_CAP hits to avoid winner-takes-all effects."
        ),
    )
    cache_rerank_popularity_cap: float = Field(
        default=50.0,
        gt=0.0,
        description="Hit count at which the popularity boost saturates (log scale).",
    )

    validator_cache_ttl_seconds: int = Field(
        default=3600,
        description="Validator verdict Redis TTL seconds (0 disables).",
    )

    session_context_ttl_seconds: int = Field(
        default=86_400,
        description="Session follow-up context TTL in Redis.",
    )

    rag_repo_path: str = Field(
        default="https://github.com/273-Team11-Proj",
        description="Repository source for RAG indexing (local path or git URL).",
    )
    rag_repo_cache_dir: str = Field(
        default="rag_repo_cache",
        description="Local directory used when cloning a remote git repository for RAG.",
    )
    rag_github_token: str = Field(
        default="",
        description="Optional GitHub token for org repository discovery (helps with rate limits/private repos).",
    )
    rag_org_repo_limit: int = Field(
        default=25,
        ge=1,
        le=500,
        description="Maximum number of repositories to ingest when RAG_REPO_PATH points to a GitHub org/user.",
    )
    rag_org_include_forks: bool = Field(
        default=True,
        description=(
            "Include forked repositories when RAG_REPO_PATH is a GitHub org/user URL. "
            "Course and team orgs often only contain forks; set false to index non-forks only."
        ),
    )
    rag_top_k: int = Field(
        default=4,
        ge=1,
        le=20,
        description=(
            "Per-corpus retrieve depth; chunks are merged across corpora and the top-k "
            "by score are sent to one LLM synthesis pass."
        ),
    )
    rag_retrieval_score_floor: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum best chunk retrieval score (cosine-style, higher is better) to run "
            "RAG synthesis. If all retrieved chunks score below this, RAG returns empty so "
            "the orchestrator can answer with plain LLM for off-repo or general questions. "
            "Set to 0 to disable (always synthesize when any chunk is returned)."
        ),
    )
    rag_synthesis_text_qa_template: str = Field(
        default=(
            "Context information from the indexed repository is below. It may be incomplete, "
            "off-topic, or irrelevant to the question.\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n"
            "Answer the query. When the context clearly supports the answer, ground your "
            "response in it and stay faithful to it. When the context is unhelpful, unrelated, "
            "or obviously insufficient, do not force an answer from it—use your general knowledge "
            "to answer the question as well as you can. Do not invent file paths, line numbers, "
            "or quotations that are not present in the context.\n"
            "Query: {query_str}\n"
            "Answer: "
        ),
        description=(
            "LlamaIndex SIMPLE_SUMMARIZE QA prompt. Must contain {context_str} and {query_str} "
            "(see LlamaIndex SimpleSummarize)."
        ),
    )
    rag_chunk_size: int = Field(
        default=900,
        ge=200,
        le=4000,
        description="Chunk size for code/document splitting in LlamaIndex.",
    )
    rag_chunk_overlap: int = Field(
        default=120,
        ge=0,
        le=600,
        description="Chunk overlap for LlamaIndex sentence splitter.",
    )
    rag_citation_max_chars: int = Field(
        default=260,
        ge=80,
        le=1200,
        description="Max chars per citation snippet returned from RAG.",
    )
    rag_required_exts: str = Field(
        default=".py,.md,.js,.jsx,.ts,.tsx,.json,.yml,.yaml,.toml",
        description="Comma-separated file extensions to index.",
    )
    rag_exclude_dirs: str = Field(
        default=".git,__pycache__,.pytest_cache,node_modules,.venv,venv,dist,build,.next",
        description="Comma-separated directory patterns excluded from indexing.",
    )
    rag_catalog_dir: str = Field(
        default="rag_catalog",
        description="Directory where generated repo/API catalog artifacts are stored.",
    )
    rag_catalog_startup_generate: bool = Field(
        default=True,
        description="Generate repo/API catalog artifacts during app startup.",
    )
    rag_catalog_redis_prefix: str = Field(
        default="semcache:catalog",
        description="Redis key prefix for generated catalog artifacts.",
    )
    rag_catalog_repo_max_files: int = Field(
        default=50,
        ge=5,
        le=500,
        description="Maximum files sampled per repository for heuristic language detection.",
    )
    rag_catalog_enable_routes: bool = Field(
        default=True,
        description="Expose catalog read/refresh routes under /api/v1/catalog.",
    )
    rag_service_base_url: str = Field(
        default="http://localhost:8001",
        description="Base URL for the standalone RAG/Catalog service.",
    )
    rag_service_request_timeout_seconds: float = Field(
        default=240.0,
        ge=0.5,
        le=300.0,
        description="Timeout for internal calls to the RAG service.",
    )
    cache_service_base_url: str = Field(
        default="http://localhost:8002",
        description="Base URL for the standalone Cache service.",
    )
    cache_service_request_timeout_seconds: float = Field(
        default=60.0,
        ge=0.5,
        le=300.0,
        description="Timeout for internal calls to the Cache service.",
    )
    analytics_service_base_url: str = Field(
        default="http://localhost:8003",
        description="Base URL for the standalone Analytics service.",
    )
    analytics_service_request_timeout_seconds: float = Field(
        default=60.0,
        ge=0.5,
        le=300.0,
        description="Timeout for internal calls to the Analytics service.",
    )
    ai_inference_retry_attempts: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Retry attempts for AI inference transient failures.",
    )
    ai_inference_rate_limit_per_minute: int = Field(
        default=120,
        ge=10,
        le=10_000,
        description="Per-minute request budget for internal AI inference APIs.",
    )
    ai_inference_cost_per_1k_input_tokens_usd: float = Field(
        default=0.0001,
        ge=0.0,
        description=(
            "Estimated input-token cost for usage/cost logging (defaults tuned for Gemini Flash Lite)."
        ),
    )
    ai_inference_cost_per_1k_output_tokens_usd: float = Field(
        default=0.0004,
        ge=0.0,
        description=(
            "Estimated output-token cost for usage/cost logging (defaults tuned for Gemini Flash Lite)."
        ),
    )

    ai_service_base_url: str = Field(
        default="http://localhost:8004",
        description="Standalone AI inference service for gateway HTTP calls.",
    )
    ai_service_request_timeout_seconds: float = Field(
        default=240.0,
        ge=0.5,
        le=600.0,
        description="Timeout for gateway → AI service HTTP calls.",
    )
    orchestrator_service_base_url: str = Field(
        default="http://localhost:8005",
        description="Base URL for the standalone Orchestrator service.",
    )
    orchestrator_service_request_timeout_seconds: float = Field(
        default=360.0,
        ge=0.5,
        le=600.0,
        description="Timeout for gateway → Orchestrator service HTTP calls.",
    )

    # Async pipeline / Redis Streams
    query_job_ttl_seconds: int = Field(default=3600, ge=60)
    orchestrator_step_timeout_seconds: float = Field(
        default=360.0,
        ge=5.0,
        description="Watchdog for orchestrator waiting on downstream HTTP/stream steps.",
    )
    orchestrator_consumer_group: str = "cg-orchestrator"
    orchestrator_consumer_name_suffix: str = ""

    analytics_via_stream: bool = Field(
        default=True,
        description="When async pipeline completes, publish analytics to Redis stream.",
    )
    analytics_stream_consumer_enabled: bool = Field(
        default=True,
        description="Analytics service consumes analytics_events stream.",
    )

    stream_workers_enabled: bool = Field(
        default=True,
        description="Cache/RAG/AI microservices run XREADGROUP loops for command streams.",
    )

    stream_max_delivery_attempts: int = Field(
        default=4,
        ge=1,
        le=20,
        description="After this many failures, message goes to DLQ stream.",
    )

    stream_reclaim_min_idle_ms: int = Field(
        default=60_000,
        ge=0,
        le=3_600_000,
        description="XAUTOCLAIM min idle (ms) for stale pending stream entries; 0 disables reclaim.",
    )

    cmd_result_ttl_seconds: int = Field(
        default=7200,
        ge=300,
        description="TTL for semcache:cmd_result:{command_id} idempotency keys.",
    )

    @computed_field
    @property
    def active_embedding_model_id(self) -> str:
        return (self.gemini_embedding_model or "").strip() or "gemini-embedding-001"

    @computed_field
    @property
    def active_llm_model_id(self) -> str:
        return (self.gemini_llm_model or "").strip() or "gemini-2.5-flash-lite"

    @computed_field
    @property
    def rag_qdrant_host_resolved(self) -> str:
        return (self.rag_qdrant_host or "").strip() or self.qdrant_host

    @computed_field
    @property
    def rag_qdrant_port_resolved(self) -> int:
        return self.rag_qdrant_port or self.qdrant_port

    @computed_field
    @property
    def rag_qdrant_vector_size_resolved(self) -> int:
        return self.rag_qdrant_vector_size or self.qdrant_vector_size

    @computed_field
    @property
    def rag_qdrant_api_key_resolved(self) -> str:
        return (self.rag_qdrant_api_key or "").strip() or self.qdrant_api_key

    @computed_field
    @property
    def rag_qdrant_https_resolved(self) -> bool:
        return self.rag_qdrant_https if self.rag_qdrant_https is not None else self.qdrant_https

    @field_validator("redis_mode", mode="before")
    @classmethod
    def _normalize_redis_mode(cls, v):
        if v is None:
            return "inherit"
        s = str(v).strip().lower()
        if s not in ("inherit", "local", "aws"):
            raise ValueError("REDIS_MODE must be one of: inherit, local, aws")
        return s

    @model_validator(mode="after")
    def _apply_redis_mode(self):
        if self.redis_mode == "inherit":
            return self
        if self.redis_mode == "local":
            host = (self.redis_local_host or "redis").strip() or "redis"
            self.redis_host = host
            self.redis_port = self.redis_local_port
            self.redis_password = self.redis_local_password or ""
            self.redis_ssl = False
            return self
        aws_host = (self.redis_aws_host or "").strip()
        if not aws_host:
            msg = "REDIS_MODE=aws requires REDIS_AWS_HOST"
            raise ValueError(msg)
        self.redis_host = aws_host
        self.redis_port = self.redis_aws_port
        self.redis_password = self.redis_aws_password or ""
        self.redis_ssl = self.redis_aws_ssl
        return self

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _coerce_cors_origins(cls, v):
        if v is None:
            return "http://localhost:5173"
        if isinstance(v, list):
            return ",".join(str(x).strip() for x in v if str(x).strip())
        return str(v).strip() or "http://localhost:5173"

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        s = self.cors_origins.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [
                        str(x).strip() for x in parsed if str(x).strip()
                    ]
            except json.JSONDecodeError:
                pass
        return [o.strip() for o in s.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
