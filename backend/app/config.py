import json
from functools import lru_cache

from pydantic import Field, computed_field, field_validator
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

    # Comma-separated in .env, e.g. http://localhost:5173,http://localhost:3000
    # (pydantic-settings cannot parse that format for List[str] — it expects JSON.)
    cors_origins: str = Field(default="http://localhost:5173")

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "semcachelm_cache"
    qdrant_vector_size: int = 768

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout_seconds: float = 120.0

    similarity_hit_threshold: float = 0.92
    similarity_gray_zone_low: float = 0.7

    quality_ema_alpha: float = 0.2
    quality_eviction_threshold: float = 0.3

    cache_search_top_k: int = Field(
        default=12,
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
        default="https://github.com/dhruvj014/Sem-Cache-LM",
        description="Repository source for RAG indexing (local path or git URL).",
    )
    rag_repo_cache_dir: str = Field(
        default=".rag_repo_cache",
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
        default=False,
        description="Whether to include forked repositories in org/user ingestion mode.",
    )
    rag_index_dir: str = Field(
        default=".rag_index",
        description="Persisted LlamaIndex storage directory.",
    )
    rag_top_k: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Top-k chunks retrieved by LlamaIndex query engine.",
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
