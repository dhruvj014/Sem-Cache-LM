import os
import sys
from pathlib import Path

import pytest

# Make the backend root importable as a package root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from services.gateway.app.config import Settings  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        log_level="WARNING",
        cors_origins=["http://localhost"],
        qdrant_host="localhost",
        qdrant_port=6333,
        qdrant_collection="test_collection",
        qdrant_vector_size=4,
        redis_host="localhost",
        redis_port=6379,
        redis_db=0,
        ollama_base_url="http://localhost:11434",
        ollama_llm_model="llama3.1:8b",
        ollama_embedding_model="nomic-embed-text",
        similarity_hit_threshold=0.92,
        similarity_gray_zone_low=0.7,
        quality_ema_alpha=0.2,
        quality_eviction_threshold=0.3,
        cache_search_top_k=5,
        cache_rerank_lexical_weight=0.0,
        validator_cache_ttl_seconds=0,
    )
