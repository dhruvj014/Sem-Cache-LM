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

    validator_cache_ttl_seconds: int = Field(
        default=3600,
        description="Validator verdict Redis TTL seconds (0 disables).",
    )

    session_context_ttl_seconds: int = Field(
        default=86_400,
        description="Session follow-up context TTL in Redis.",
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
