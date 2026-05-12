"""Public API: download analytics export (JSON or CSV)."""

from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from services.gateway.app.config import get_settings

router = APIRouter()


def _headers(settings: Any) -> dict[str, str]:
    h: dict[str, str] = {}
    t = (settings.internal_service_token or "").strip()
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h


@router.get("/analytics/export")
async def export_analytics(
    request: Request,
    fmt: str = Query("json", alias="format", pattern="^(json|csv)$"),
):
    settings = get_settings()
    http: httpx.AsyncClient = request.app.state.http_client
    base = (settings.analytics_service_base_url or "").rstrip("/")
    try:
        resp = await http.get(
            f"{base}/internal/v1/analytics/export",
            params={"format": fmt},
            headers=_headers(settings),
            timeout=settings.analytics_service_request_timeout_seconds,
        )
        resp.raise_for_status()
        body = resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Analytics export failed") from e
    if not body.get("success"):
        raise HTTPException(status_code=502, detail="Analytics export error")
    inner = body.get("data") or {}
    if fmt == "json":
        payload = inner.get("json_payload") or {}
        raw = json.dumps(payload, indent=2).encode("utf-8")
        return StreamingResponse(
            iter([raw]),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="semcachelm-analytics.json"'
            },
        )
    csv_text = inner.get("csv_text") or ""
    return StreamingResponse(
        iter([csv_text.encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="semcachelm-analytics.csv"'},
    )
