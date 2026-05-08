from __future__ import annotations

from typing import Any

import httpx
import structlog

from services.gateway.app.config import Settings
from shared.models.schemas import QueryResponse


class HttpOrchestratorClient:
    """Gateway-side client for the standalone orchestrator service."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http = http_client
        self._base_url = (settings.orchestrator_service_base_url or "").rstrip("/")

    async def handle_query(
        self,
        query: str,
        session_id: str,
        *,
        similarity_hit_threshold: float | None = None,
        similarity_gray_zone_low: float | None = None,
    ) -> QueryResponse:
        body = await self._post(
            "/internal/v1/query",
            {
                "query": query,
                "session_id": session_id,
                "similarity_hit_threshold": similarity_hit_threshold,
                "similarity_gray_zone_low": similarity_gray_zone_low,
            },
        )
        return QueryResponse.model_validate(body)

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
            timeout=self._settings.orchestrator_service_request_timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError("orchestrator internal request failed")
        return data.get("data") or {}

    async def health(self) -> bool:
        try:
            resp = await self._http.get(
                f"{self._base_url}/api/v1/docs",
                timeout=min(5.0, self._settings.orchestrator_service_request_timeout_seconds),
            )
            return resp.status_code < 500
        except Exception:
            return False
