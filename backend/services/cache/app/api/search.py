"""Internal API: search / filter semantic cache entries."""

from __future__ import annotations

import math
from typing import Any, List

import httpx
from fastapi import APIRouter, Query, Request

from shared.config.settings import get_settings
from shared.contracts.internal import InternalEmbedRequest
from shared.contracts.search import CacheSearchHit, CacheSearchResponse
from shared.models.schemas import ResponseEnvelope
router = APIRouter()

QUALITY_KEY = "semcache:quality:{cache_id}"
HIT_COUNT_KEY = "semcache:hits:{cache_id}"


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (na * nb)))


def _build_headers(settings: Any) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = (settings.internal_service_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _embed_via_ai(settings: Any, http: httpx.AsyncClient, text: str) -> list[float]:
    base = (settings.ai_service_base_url or "").rstrip("/")
    payload = InternalEmbedRequest(text=text).model_dump()
    resp = await http.post(
        f"{base}/internal/v1/embed",
        json=payload,
        headers=_build_headers(settings),
        timeout=settings.ai_service_request_timeout_seconds,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError("embed failed")
    data = body.get("data") or {}
    return list(data.get("embedding") or [])


@router.get("/v1/cache/search", response_model=ResponseEnvelope[CacheSearchResponse])
async def internal_cache_search(
    app_request: Request,
    query: str = Query("", max_length=2000),
    min_quality: float = Query(0.0, ge=0.0, le=1.0),
    max_quality: float = Query(1.0, ge=0.0, le=1.0),
    sort_by: str = Query("quality", pattern="^(quality|date|similarity)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    settings = get_settings()
    collection = settings.qdrant_collection
    qclient = app_request.app.state.qdrant.client
    rcli = app_request.app.state.redis.client
    http = app_request.app.state.http_client

    q_lower = (query or "").strip().lower()
    ref_vec: list[float] | None = None
    need_vectors = False
    if sort_by == "similarity" and q_lower:
        ref_vec = await _embed_via_ai(settings, http, query.strip())
        need_vectors = True

    rows: list[dict[str, Any]] = []
    offset = None
    while True:
        records, next_off = await qclient.scroll(
            collection_name=collection,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=need_vectors,
        )
        for rec in records:
            cid = str(rec.id)
            pl = rec.payload or {}
            qtext = str(pl.get("query", ""))
            rtext = str(pl.get("response", ""))
            if q_lower and q_lower not in qtext.lower() and q_lower not in rtext.lower():
                continue
            qraw = await rcli.get(QUALITY_KEY.format(cache_id=cid))
            try:
                quality = float(qraw) if qraw is not None else 1.0
            except (TypeError, ValueError):
                quality = 1.0
            if quality < min_quality or quality > max_quality:
                continue
            hraw = await rcli.get(HIT_COUNT_KEY.format(cache_id=cid))
            try:
                hits = int(hraw) if hraw is not None else 0
            except (TypeError, ValueError):
                hits = 0
            sim = 0.0
            if ref_vec:
                raw_vec = getattr(rec, "vector", None)
                if raw_vec is not None:
                    vec = list(raw_vec) if not isinstance(raw_vec, list) else raw_vec
                    sim = _cosine(ref_vec, vec)
            rows.append(
                {
                    "cache_id": cid,
                    "query_preview": qtext[:240],
                    "response_preview": rtext[:240],
                    "quality_score": quality,
                    "hit_count": hits,
                    "created_at": str(pl.get("created_at", "")),
                    "last_used_at": str(pl.get("last_used_at", "")),
                    "similarity_rank": sim,
                    "source": str(pl.get("source", "")),
                }
            )
        if next_off is None:
            break
        offset = next_off

    if sort_by == "quality":
        rows.sort(key=lambda x: x["quality_score"], reverse=True)
    elif sort_by == "date":
        rows.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    else:
        rows.sort(key=lambda x: x["similarity_rank"], reverse=True)

    total = len(rows)
    start = (page - 1) * page_size
    chunk = rows[start : start + page_size]
    entries = [CacheSearchHit.model_validate(r) for r in chunk]
    return ResponseEnvelope.ok(
        CacheSearchResponse(
            entries=entries,
            total=total,
            page=page,
            page_size=page_size,
        )
    )
# verified
