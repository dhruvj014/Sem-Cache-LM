"""Internal API: aggregate cache entry counts by Redis-backed quality score."""

from __future__ import annotations

from fastapi import APIRouter, Request

from shared.contracts.health_score import CacheHealthScoreBreakdown
from shared.config.settings import get_settings
from shared.models.schemas import ResponseEnvelope

router = APIRouter()

QUALITY_KEY = "semcache:quality:{cache_id}"


@router.get(
    "/v1/cache/health-buckets",
    response_model=ResponseEnvelope[CacheHealthScoreBreakdown],
)
async def internal_cache_health_buckets(app_request: Request):
    settings = get_settings()
    collection = settings.qdrant_collection
    client = app_request.app.state.qdrant.client
    rcli = app_request.app.state.redis.client

    healthy = degrading = critical = 0
    offset = None
    while True:
        records, next_off = await client.scroll(
            collection_name=collection,
            limit=256,
            offset=offset,
            with_payload=True,
        )
        for rec in records:
            cid = str(rec.id)
            qraw = await rcli.get(QUALITY_KEY.format(cache_id=cid))
            try:
                q = float(qraw) if qraw is not None else 1.0
            except (TypeError, ValueError):
                q = 1.0
            if q > 0.8:
                healthy += 1
            elif q >= 0.3:
                degrading += 1
            else:
                critical += 1
        if next_off is None:
            break
        offset = next_off

    total = healthy + degrading + critical
    overall = (100.0 * healthy / total) if total > 0 else 100.0
    return ResponseEnvelope.ok(
        CacheHealthScoreBreakdown(
            healthy=healthy,
            degrading=degrading,
            critical=critical,
            total=total,
            overall_health_percent=round(overall, 2),
        )
    )
