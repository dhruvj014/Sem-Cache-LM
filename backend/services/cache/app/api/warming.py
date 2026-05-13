"""Internal API: warm semantic cache by embedding + optional LLM store."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request

from shared.config.settings import get_settings
from shared.contracts.internal import InternalEmbedRequest, InternalGenerateRequest
from shared.contracts.warming import CacheWarmRequest, CacheWarmResponse
from shared.models.schemas import ResponseEnvelope
from shared.observability.logger import get_logger
from shared.observability.metrics import CACHE_WARM_TOTAL

logger = get_logger(__name__)
router = APIRouter()


def _headers(settings) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    t = (settings.internal_service_token or "").strip()
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h


async def _ai_embed(http: httpx.AsyncClient, settings, text: str) -> list[float]:
    base = (settings.ai_service_base_url or "").rstrip("/")
    r = await http.post(
        f"{base}/internal/v1/embed",
        json=InternalEmbedRequest(text=text).model_dump(),
        headers=_headers(settings),
        timeout=settings.ai_service_request_timeout_seconds,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error", {}).get("message") or "embed failed")
    data = body.get("data") or {}
    return list(data.get("embedding") or [])


async def _ai_generate(http: httpx.AsyncClient, settings, prompt: str) -> str:
    base = (settings.ai_service_base_url or "").rstrip("/")
    r = await http.post(
        f"{base}/internal/v1/generate",
        json=InternalGenerateRequest(prompt=prompt, system=None).model_dump(),
        headers=_headers(settings),
        timeout=settings.ai_service_request_timeout_seconds,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error", {}).get("message") or "generate failed")
    data = body.get("data") or {}
    return str(data.get("text") or "")


@router.post("/v1/cache/warm", response_model=ResponseEnvelope[CacheWarmResponse])
async def internal_cache_warm(body: CacheWarmRequest, app_request: Request):
    settings = get_settings()
    cache = app_request.app.state.cache_service
    http: httpx.AsyncClient = app_request.app.state.http_client

    warmed = skipped = failed = 0
    for q in body.questions:
        qt = (q or "").strip()
        if not qt:
            continue
        try:
            emb = await _ai_embed(http, settings, qt)
            hits = await cache.search(emb, top_k=3)
            top = hits[0].score if hits else 0.0
            if top >= float(settings.similarity_hit_threshold):
                skipped += 1
                continue
            answer = await _ai_generate(
                http,
                settings,
                f"Answer briefly and accurately (no preamble):\n\n{qt}",
            )
            if not (answer or "").strip():
                failed += 1
                continue
            await cache.store(
                qt,
                emb,
                answer.strip(),
                {"source": "cache_warm"},
            )
            warmed += 1
            CACHE_WARM_TOTAL.inc()
        except Exception as e:  # noqa: BLE001
            logger.warning("cache.warm.item_failed", question_preview=qt[:80], error=str(e))
            failed += 1

    logger.info("cache.warm.done", warmed=warmed, skipped=skipped, failed=failed)
    return ResponseEnvelope.ok(
        CacheWarmResponse(
            warmed_count=warmed,
            skipped_count=skipped,
            failed_count=failed,
        )
    )
# verified
