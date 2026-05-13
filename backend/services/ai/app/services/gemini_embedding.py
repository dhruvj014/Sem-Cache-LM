from __future__ import annotations

from typing import List

import httpx

from shared.config.settings import Settings
from shared.domain.model_providers import EmbeddingService
from shared.observability.logger import get_logger
from shared.observability.metrics import LLM_LATENCY

logger = get_logger(__name__)

GEMINI_REST_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiEmbeddingService(EmbeddingService):
    """Gemini embeddings via Google AI REST (`embedContent`) with fixed output dimension."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http = http_client
        self._model = settings.gemini_embedding_model

    @property
    def vector_size(self) -> int:
        return int(self._settings.qdrant_vector_size)

    async def embed(self, text: str) -> List[float]:
        api_key = (self._settings.gemini_api_key or "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        dim = int(self._settings.qdrant_vector_size)
        url = f"{GEMINI_REST_BASE}/models/{self._model}:embedContent"
        payload = {
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": dim,
        }
        timeout = float(self._settings.gemini_timeout_seconds)
        with LLM_LATENCY.labels(call_type="embed").time():
            try:
                resp = await self._http.post(
                    url,
                    headers={"x-goog-api-key": api_key},
                    json=payload,
                    timeout=timeout,
                )
            except httpx.RequestError as e:
                raise RuntimeError(
                    "Cannot reach Google Gemini API (HTTPS to generativelanguage.googleapis.com). "
                    "From Docker, verify outbound internet and DNS inside the container "
                    "(e.g. curl -vI https://generativelanguage.googleapis.com), VPN/firewall rules, "
                    "and HTTP_PROXY/HTTPS_PROXY if you use a corporate proxy. "
                    f"Underlying error: {e}"
                ) from e
        resp.raise_for_status()
        data = resp.json()
        emb = data.get("embedding") or {}
        values = emb.get("values")
        if not values or not isinstance(values, list):
            raise RuntimeError("Gemini embedContent returned no embedding values")
        if len(values) != dim:
            logger.warning(
                "gemini.embedding_dim_mismatch",
                expected=dim,
                actual=len(values),
            )
            raise RuntimeError(
                f"Embedding dimension {len(values)} does not match qdrant_vector_size={dim}"
            )
        return [float(x) for x in values]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        results: List[List[float]] = []
        for t in texts:
            results.append(await self.embed(t))
        return results
