from __future__ import annotations

from typing import Any, Optional

import httpx
import time
import structlog

from services.gateway.app.config import Settings
from shared.contracts.internal import InternalRagRetrieveRequest
from shared.contracts.internal import InternalRagRetrieveResponse
from services.rag.app.services.rag_service import RagCitation, RagResult
from services.gateway.app.services.base.rag_client_base import RagClient
from shared.observability.logger import get_logger


logger = get_logger(__name__)


class HttpRagClient(RagClient):
    """Gateway-side client for the standalone RAG/Catalog service."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http = http_client
        self._base_url = (settings.rag_service_base_url or "").rstrip("/")

    async def answer(self, query: str) -> RagResult:
        correlation_id = self._get_correlation_id()
        headers = {}
        if correlation_id:
            headers["x-correlation-id"] = correlation_id

        start = time.perf_counter()
        url = f"{self._base_url}/internal/v1/retrieve"
        req = InternalRagRetrieveRequest(query=query)

        resp = await self._http.post(
            url,
            json=req.model_dump(),
            headers=headers,
            timeout=self._settings.rag_service_request_timeout_seconds,
        )
        resp.raise_for_status()
        latency_ms = (time.perf_counter() - start) * 1000
        body: dict[str, Any] = resp.json()
        if not body.get("success"):
            raise RuntimeError(body.get("error", {}).get("message") or "RAG retrieve failed")

        data = body.get("data")
        parsed = InternalRagRetrieveResponse.model_validate(data)
        citations = [
            RagCitation(
                file_path=c.file_path,
                score=c.score,
                snippet=c.snippet,
            )
            for c in (parsed.citations or [])
        ]
        logger.info(
            "rag.http_retrieve",
            latency_ms=round(latency_ms, 2),
            query_preview=(query or "")[:80],
            citations_count=len(citations),
        )
        return RagResult(response=parsed.answer, citations=citations)

    def _get_correlation_id(self) -> Optional[str]:
        ctx = structlog.contextvars.get_contextvars()
        value = ctx.get("correlation_id")
        return str(value) if value else None

