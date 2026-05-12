"""Public API: search / filter semantic cache."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from services.gateway.app.config import get_settings
from shared.contracts.search import CacheSearchResponse
from shared.models.schemas import ResponseEnvelope

router = APIRouter()


def _headers(settings) -> dict[str, str]:
    h: dict[str, str] = {}
    t = (settings.internal_service_token or "").strip()
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h


@router.get("/cache/search", response_model=ResponseEnvelope[CacheSearchResponse])
async def public_cache_search(
    request: Request,
    query: str = Query("", max_length=2000),
    min_quality: float = Query(0.0, ge=0.0, le=1.0),
    max_quality: float = Query(1.0, ge=0.0, le=1.0),
    sort_by: str = Query("quality", pattern="^(quality|date|similarity)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    settings = get_settings()
    http: httpx.AsyncClient = request.app.state.http_client
    base = (settings.cache_service_base_url or "").rstrip("/")
    try:
        resp = await http.get(
            f"{base}/internal/v1/cache/search",
            params={
                "query": query,
                "min_quality": min_quality,
                "max_quality": max_quality,
                "sort_by": sort_by,
                "page": page,
                "page_size": page_size,
            },
            headers=_headers(settings),
            timeout=settings.cache_service_request_timeout_seconds,
        )
        resp.raise_for_status()
        body = resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Cache search failed") from e
    if not body.get("success"):
        raise HTTPException(status_code=502, detail="Cache search error")
    data = CacheSearchResponse.model_validate(body.get("data") or {})
    return ResponseEnvelope.ok(data)
