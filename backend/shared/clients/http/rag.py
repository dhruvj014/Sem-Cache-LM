from __future__ import annotations

import time
from typing import Any, Optional

import httpx
import structlog

from services.rag.app.services.rag_service import RagCitation, RagResult
from shared.config.settings import Settings
from shared.contracts.internal import InternalRagRetrieveRequest
from shared.contracts.internal import InternalRagRetrieveResponse
from shared.domain.rag_ports import RagClient
from shared.observability.logger import get_logger

logger = get_logger(__name__)


class HttpRagClient(RagClient):
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http = http_client
        self._base_url = (settings.rag_service_base_url or "").rstrip("/")

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        cid = self._get_correlation_id()
        if cid:
            headers["x-correlation-id"] = cid
        token = self._settings.internal_service_token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def answer(self, query: str) -> RagResult:
        headers = self._build_headers()

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

    async def health(self) -> bool:
        try:
            resp = await self._http.get(
                f"{self._base_url}/api/v1/docs",
                timeout=min(5.0, self._settings.rag_service_request_timeout_seconds),
            )
            return resp.status_code < 500
        except Exception:
            return False
