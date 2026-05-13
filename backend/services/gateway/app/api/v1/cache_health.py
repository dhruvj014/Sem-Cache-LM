"""Public API: cache quality health score (via analytics service)."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request

from services.gateway.app.config import get_settings
from shared.contracts.health_score import CacheHealthScoreBreakdown
from shared.models.schemas import ResponseEnvelope

router = APIRouter()


def _headers(settings) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    t = (settings.internal_service_token or "").strip()
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h


@router.get("/cache/health-score", response_model=ResponseEnvelope[CacheHealthScoreBreakdown])
async def get_cache_health_score(request: Request):
    settings = get_settings()
    http: httpx.AsyncClient = request.app.state.http_client
    base = (settings.analytics_service_base_url or "").rstrip("/")
    try:
        resp = await http.post(
            f"{base}/internal/v1/analytics/health-score",
            json={},
            headers=_headers(settings),
            timeout=settings.analytics_service_request_timeout_seconds,
        )
        resp.raise_for_status()
        body = resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Analytics health-score request failed") from e
    if not body.get("success"):
        raise HTTPException(status_code=502, detail="Analytics health-score returned error")
    data = CacheHealthScoreBreakdown.model_validate(body.get("data") or {})
    return ResponseEnvelope.ok(data)
# verified
