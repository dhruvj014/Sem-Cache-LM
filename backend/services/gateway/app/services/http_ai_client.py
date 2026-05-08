from __future__ import annotations

from typing import Any, List

import httpx
import structlog

from services.gateway.app.config import Settings
from shared.contracts.internal import InternalEmbedRequest, InternalGenerateRequest
from shared.domain.model_providers import EmbeddingService
from shared.domain.model_providers import LLMClient


class HttpAIClient(EmbeddingService, LLMClient):
    """Calls the standalone AI inference service over HTTP (gateway stays Ollama-free)."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http = http_client
        self._base_url = (settings.ai_service_base_url or "").rstrip("/")
        self._vector_size = 0

    @property
    def vector_size(self) -> int:
        return self._vector_size

    async def embed(self, text: str) -> List[float]:
        body = await self._post(
            "/internal/v1/embed",
            InternalEmbedRequest(text=text).model_dump(),
        )
        self._vector_size = int(body.get("vector_size", 0))
        return list(body["embedding"])

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for t in texts:
            out.append(await self.embed(t))
        return out

    async def generate(self, prompt: str, system: str | None = None) -> str:
        body = await self._post(
            "/internal/v1/generate",
            InternalGenerateRequest(prompt=prompt, system=system).model_dump(),
        )
        return str(body["text"])

    async def health(self) -> bool:
        try:
            resp = await self._http.get(
                f"{self._base_url}/api/v1/docs",
                timeout=min(5.0, self._settings.ai_service_request_timeout_seconds),
            )
            return resp.status_code < 500
        except Exception:
            return False

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers: dict[str, str] = {}
        cid = structlog.contextvars.get_contextvars().get("correlation_id")
        if cid:
            headers["x-correlation-id"] = str(cid)
        resp = await self._http.request(
            "POST",
            f"{self._base_url}{path}",
            json=payload,
            headers=headers,
            timeout=self._settings.ai_service_request_timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError("AI internal request failed")
        return data.get("data") or {}
