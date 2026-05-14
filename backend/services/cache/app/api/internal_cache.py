from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from shared.contracts.internal import (
    InternalCacheEvictRequest,
    InternalCacheEvictResponse,
    InternalCacheFeedbackRequest,
    InternalCacheIncrementHitRequest,
    InternalCacheSearchRequest,
    InternalCacheSearchResponse,
    InternalCacheStoreRequest,
    InternalCacheStoreResponse,
)
from shared.models.schemas import ResponseEnvelope

router = APIRouter()


@router.post("/v1/cache/search")
async def internal_cache_search(request: InternalCacheSearchRequest, app_request: Request):
    cache = app_request.app.state.cache_boundary
    hits = await cache.search(
        request.embedding,
        top_k=request.top_k,
        sparse_indices=request.sparse_indices or None,
        sparse_values=request.sparse_values or None,
    )
    return ResponseEnvelope.ok(
        InternalCacheSearchResponse(hits=[h.model_dump() for h in hits])
    )


@router.post("/v1/cache/store")
async def internal_cache_store(request: InternalCacheStoreRequest, app_request: Request):
    cache = app_request.app.state.cache_boundary
    cache_id = await cache.store(
        query=request.query,
        embedding=request.embedding,
        response=request.response,
        metadata=request.metadata,
        sparse_indices=request.sparse_indices or None,
        sparse_values=request.sparse_values or None,
    )
    return ResponseEnvelope.ok(InternalCacheStoreResponse(cache_id=cache_id))


@router.post("/v1/cache/increment_hit")
async def internal_cache_increment_hit(
    request: InternalCacheIncrementHitRequest, app_request: Request
):
    cache = app_request.app.state.cache_boundary
    await cache.increment_hit(request.cache_id)
    return ResponseEnvelope.ok({"updated": request.cache_id})


@router.post("/v1/cache/feedback")
async def internal_cache_feedback(request: InternalCacheFeedbackRequest, app_request: Request):
    cache = app_request.app.state.cache_boundary
    if request.action == "promote":
        await cache.promote(request.cache_id, request.new_quality)
    elif request.action == "demote":
        await cache.demote(request.cache_id, request.new_quality)
    else:  # pragma: no cover - guarded by pydantic literal
        raise HTTPException(status_code=400, detail="Invalid action")
    return ResponseEnvelope.ok({"cache_id": request.cache_id, "action": request.action})


@router.post("/v1/cache/evict")
async def internal_cache_evict(request: InternalCacheEvictRequest, app_request: Request):
    cache = app_request.app.state.cache_boundary
    result = await cache.evict_low_quality(request.threshold)
    return ResponseEnvelope.ok(
        InternalCacheEvictResponse(
            evicted_ids=result.evicted_ids,
            evicted_count=result.evicted_count,
        )
    )


@router.get("/v1/cache/entries")
async def internal_cache_entries(page: int, page_size: int, app_request: Request):
    cache = app_request.app.state.cache_boundary
    entries, total = await cache.list_entries(page, page_size)
    return ResponseEnvelope.ok(
        {
            "entries": [e.model_dump() for e in entries],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/v1/cache/{cache_id}")
async def internal_cache_get(cache_id: str, app_request: Request):
    cache = app_request.app.state.cache_boundary
    entry = await cache.get(cache_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    return ResponseEnvelope.ok(entry.model_dump())


@router.delete("/v1/cache/{cache_id}")
async def internal_cache_delete(cache_id: str, app_request: Request):
    cache = app_request.app.state.cache_boundary
    await cache.delete(cache_id)
    return ResponseEnvelope.ok({"deleted": cache_id})


@router.post("/v1/cache/clear")
async def internal_cache_clear(app_request: Request):
    cache = app_request.app.state.cache_boundary
    deleted = await cache.clear_all()
    return ResponseEnvelope.ok({"deleted_entries": deleted})

