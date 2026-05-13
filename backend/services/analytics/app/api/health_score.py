"""Internal API: cache health score (delegates to cache + updates gauges)."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request

from shared.config.settings import get_settings
from shared.contracts.health_score import CacheHealthScoreBreakdown, InternalHealthScoreRequest
from shared.models.schemas import ResponseEnvelope
from shared.observability.metrics import (
    CACHE_CRITICAL_ENTRIES,
    CACHE_DEGRADING_ENTRIES,
    CACHE_HEALTHY_ENTRIES,
)

router = APIRouter()


def _headers(settings) -> dict[str, str]:
    h: dict[str, str] = {}
    t = (settings.internal_service_token or "").strip()
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h


@router.post(
    "/v1/analytics/health-score",
    response_model=ResponseEnvelope[CacheHealthScoreBreakdown],
)
async def internal_health_score(
    app_request: Request,
    body: InternalHealthScoreRequest | None = None,
):
    _ = body
    settings = get_settings()
    http: httpx.AsyncClient = app_request.app.state.http_client
    base = (settings.cache_service_base_url or "").rstrip("/")
    resp = await http.get(
        f"{base}/internal/v1/cache/health-buckets",
        headers=_headers(settings),
        timeout=settings.cache_service_request_timeout_seconds,
    )
    resp.raise_for_status()
    envelope = resp.json()
    if not envelope.get("success"):
        raise RuntimeError("cache health-buckets failed")
    data = CacheHealthScoreBreakdown.model_validate(envelope.get("data") or {})

    CACHE_HEALTHY_ENTRIES.set(data.healthy)
    CACHE_DEGRADING_ENTRIES.set(data.degrading)
    CACHE_CRITICAL_ENTRIES.set(data.critical)

    return ResponseEnvelope.ok(data)
