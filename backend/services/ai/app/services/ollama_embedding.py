import asyncio
from typing import ClassVar, List, Optional

import httpx

from shared.config.settings import Settings
from shared.domain.model_providers import EmbeddingService
from shared.observability.logger import get_logger
from shared.observability.metrics import LLM_LATENCY

logger = get_logger(__name__)


class OllamaEmbeddingService(EmbeddingService):
    _bm25_encoder: ClassVar[Optional[object]] = None

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http = http_client
        self._model = settings.ollama_embedding_model

    @property
    def vector_size(self) -> int:
        return self._settings.qdrant_vector_size

    async def embed(self, text: str) -> List[float]:
        url = f"{self._settings.ollama_base_url}/api/embeddings"
        with LLM_LATENCY.labels(call_type="embed").time():
            resp = await self._http.post(
                url,
                json={"model": self._model, "prompt": text},
                timeout=self._settings.ollama_timeout_seconds,
            )
        resp.raise_for_status()
        data = resp.json()
        embedding = data.get("embedding")
        if not embedding:
            raise RuntimeError("Ollama returned empty embedding")
        return embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        results: List[List[float]] = []
        for t in texts:
            results.append(await self.embed(t))
        return results

    async def sparse_encode(self, text: str) -> tuple[list[int], list[float]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._encode_bm25_sync, text)

    def _encode_bm25_sync(self, text: str) -> tuple[list[int], list[float]]:
        if OllamaEmbeddingService._bm25_encoder is None:
            from fastembed.sparse.bm25 import SparseTextEmbedding
            OllamaEmbeddingService._bm25_encoder = SparseTextEmbedding(
                model_name=self._settings.bm25_model
            )
        result = next(OllamaEmbeddingService._bm25_encoder.embed([text]))
        return result.indices.tolist(), result.values.tolist()
