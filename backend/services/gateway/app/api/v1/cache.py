from fastapi import APIRouter, Depends, HTTPException, Query

from services.gateway.app.config import Settings, get_settings
from services.gateway.app.dependencies import get_analytics_service, get_cache_boundary
from shared.domain.analytics_ports import AnalyticsClient
from shared.domain.cache_boundary import CacheBoundary
from shared.models.schemas import (
    CacheEntry,
    CacheListResponse,
    ClearCacheResult,
    EvictionResult,
    ResponseEnvelope,
)
from shared.observability.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/cache/entries", response_model=ResponseEnvelope[CacheListResponse])
async def list_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    service: CacheBoundary = Depends(get_cache_boundary),
):
    entries, total = await service.list_entries(page, page_size)
    return ResponseEnvelope.ok(
        CacheListResponse(
            entries=entries,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/cache/clear", response_model=ResponseEnvelope[ClearCacheResult])
async def clear_all_cache(
    service: CacheBoundary = Depends(get_cache_boundary),
    analytics: AnalyticsClient = Depends(get_analytics_service),
):
    deleted = await service.clear_all()
    await analytics.reset()
    return ResponseEnvelope.ok(
        ClearCacheResult(deleted_entries=deleted, analytics_reset=True)
    )


@router.get("/cache/{cache_id}", response_model=ResponseEnvelope[CacheEntry])
async def get_entry(
    cache_id: str,
    service: CacheBoundary = Depends(get_cache_boundary),
):
    entry = await service.get(cache_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    return ResponseEnvelope.ok(entry)


@router.delete("/cache/{cache_id}", response_model=ResponseEnvelope[dict])
async def delete_entry(
    cache_id: str,
    service: CacheBoundary = Depends(get_cache_boundary),
):
    await service.delete(cache_id)
    return ResponseEnvelope.ok({"deleted": cache_id})


@router.post("/cache/evict", response_model=ResponseEnvelope[EvictionResult])
async def trigger_eviction(
    service: CacheBoundary = Depends(get_cache_boundary),
    settings: Settings = Depends(get_settings),
):
    result = await service.evict_low_quality(settings.quality_eviction_threshold)
    return ResponseEnvelope.ok(result)
