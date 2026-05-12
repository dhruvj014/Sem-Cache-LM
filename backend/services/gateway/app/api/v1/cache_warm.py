"""Public API: warm semantic cache with pre-generated Q/A rows."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request

from services.gateway.app.config import get_settings
from shared.contracts.warming import CacheWarmRequest, CacheWarmResponse
from shared.models.schemas import ResponseEnvelope

router = APIRouter()


def _headers(settings) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    t = (settings.internal_service_token or "").strip()
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h


@router.post("/cache/warm", response_model=ResponseEnvelope[CacheWarmResponse])
async def public_cache_warm(body: CacheWarmRequest, request: Request):
    settings = get_settings()
    http: httpx.AsyncClient = request.app.state.http_client
    base = (settings.cache_service_base_url or "").rstrip("/")
    try:
        resp = await http.post(
            f"{base}/internal/v1/cache/warm",
            json=body.model_dump(),
            headers=_headers(settings),
            timeout=settings.cache_service_request_timeout_seconds * 10,
        )
        resp.raise_for_status()
        out = resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Cache warm request failed") from e
    if not out.get("success"):
        raise HTTPException(status_code=502, detail="Cache warm error")
    data = CacheWarmResponse.model_validate(out.get("data") or {})
    return ResponseEnvelope.ok(data)
