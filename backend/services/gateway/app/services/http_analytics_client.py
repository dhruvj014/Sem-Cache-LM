from __future__ import annotations

from typing import Any

import httpx
import structlog

from services.gateway.app.config import Settings
from shared.models.enums import AgentAction, ResponseSource
from shared.contracts.internal import InternalQueryEvent
from shared.models.schemas import AnalyticsSummary, HistoryResponse
from services.gateway.app.services.base.analytics_client_base import AnalyticsClient


class HttpAnalyticsClient(AnalyticsClient):
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http = http_client
        self._base_url = (settings.analytics_service_base_url or "").rstrip("/")

    async def record_query(
        self,
        query: str,
        source: ResponseSource,
        agent_action: AgentAction,
        similarity_score: float,
        latency_ms: float,
        cache_id: str | None,
        response_text: str,
    ) -> None:
        cid = structlog.contextvars.get_contextvars().get("correlation_id") or "unknown"
        req = InternalQueryEvent(
            correlation_id=str(cid),
            query=query,
            source=source.value,
            agent_action=agent_action.value,
            similarity_score=similarity_score,
            latency_ms=latency_ms,
            cache_id=cache_id,
            response_text=response_text,
        )
        await self._request("POST", "/internal/v1/events/query", json=req.model_dump())

    async def summary(self) -> AnalyticsSummary:
        data = await self._request("GET", "/internal/v1/summary")
        return AnalyticsSummary.model_validate(data)

    async def history(self, limit: int = 20) -> HistoryResponse:
        data = await self._request("GET", "/internal/v1/history", params={"limit": limit})
        return HistoryResponse.model_validate(data)

    async def reset(self) -> None:
        await self._request("POST", "/internal/v1/reset")

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {}
        cid = structlog.contextvars.get_contextvars().get("correlation_id")
        if cid:
            headers["x-correlation-id"] = str(cid)
        resp = await self._http.request(
            method,
            f"{self._base_url}{path}",
            headers=headers,
            json=json,
            params=params,
            timeout=self._settings.analytics_service_request_timeout_seconds,
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success"):
            raise RuntimeError("analytics internal request failed")
        return body.get("data") or {}

