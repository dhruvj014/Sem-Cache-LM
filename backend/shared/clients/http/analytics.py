from __future__ import annotations

from typing import Any

import httpx
import structlog

from shared.config.settings import Settings
from shared.contracts.internal import InternalQueryEvent
from shared.domain.analytics_ports import AnalyticsClient
from shared.models.enums import AgentAction, ResponseSource
from shared.models.schemas import AnalyticsSummary, HistoryResponse


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
        *,
        job_id: str | None = None,
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
            job_id=job_id,
        )
        await self._request("POST", "/internal/v1/events/query", json=req.model_dump(mode="json"))

    async def summary(self) -> AnalyticsSummary:
        data = await self._request("GET", "/internal/v1/summary")
        return AnalyticsSummary.model_validate(data)

    async def history(self, limit: int = 20) -> HistoryResponse:
        data = await self._request("GET", "/internal/v1/history", params={"limit": limit})
        return HistoryResponse.model_validate(data)

    async def reset(self) -> None:
        await self._request("POST", "/internal/v1/reset")

    async def health(self) -> bool:
        try:
            resp = await self._http.get(
                f"{self._base_url}/api/v1/docs",
                timeout=min(5.0, self._settings.analytics_service_request_timeout_seconds),
            )
            return resp.status_code < 500
        except Exception:
            return False

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        cid = structlog.contextvars.get_contextvars().get("correlation_id")
        if cid:
            headers["x-correlation-id"] = str(cid)
        token = self._settings.internal_service_token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = self._build_headers()
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
