"""Internal API: invalidate semantic cache entries linked to RAG chunks or sources."""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Request

from shared.config.settings import get_settings
from shared.contracts.invalidation import (
    InternalCacheInvalidateRequest,
    InternalCacheInvalidateResponse,
)
from shared.models.schemas import ResponseEnvelope
from shared.observability.logger import get_logger
from shared.observability.metrics import INVALIDATIONS_TOTAL

logger = get_logger(__name__)

router = APIRouter()


def _payload_matches_chunk(payload: dict[str, Any], chunk_id: str) -> bool:
    cid = (chunk_id or "").strip()
    if not cid:
        return False
    if str(payload.get("chunk_id") or "") == cid:
        return True
    raw = payload.get("rag_chunk_ids")
    if isinstance(raw, list) and cid in [str(x) for x in raw]:
        return True
    raw_one = payload.get("rag_chunk_id")
    if str(raw_one or "") == cid:
        return True
    return False


def _payload_matches_source(payload: dict[str, Any], source: str) -> bool:
    sid = (source or "").strip()
    if not sid:
        return False
    cits = payload.get("rag_citations")
    if isinstance(cits, list):
        for c in cits:
            if not isinstance(c, str):
                continue
            if c == sid or sid in c or c.endswith(sid) or sid in c.replace("\\", "/"):
                return True
    return False


async def _collect_matching_ids(
    *,
    collection: str,
    client: Any,
    chunk_id: Optional[str],
    source_identifier: Optional[str],
) -> List[str]:
    matches: list[str] = []
    seen: set[str] = set()
    offset = None
    chunk = (chunk_id or "").strip() or None
    source = (source_identifier or "").strip() or None

    while True:
        records, next_off = await client.scroll(
            collection_name=collection,
            limit=256,
            offset=offset,
            with_payload=True,
        )
        for rec in records:
            rid = str(rec.id)
            pl = rec.payload or {}
            ok = False
            if chunk is not None:
                if rid == chunk:
                    ok = True
                elif _payload_matches_chunk(pl, chunk):
                    ok = True
            elif source is not None:
                ok = _payload_matches_source(pl, source)
            if ok and rid not in seen:
                seen.add(rid)
                matches.append(rid)
        if next_off is None:
            break
        offset = next_off
    return matches


@router.post("/v1/cache/invalidate", response_model=ResponseEnvelope[InternalCacheInvalidateResponse])
async def internal_cache_invalidate(
    body: InternalCacheInvalidateRequest,
    app_request: Request,
):
    settings = get_settings()
    collection = settings.qdrant_collection
    qclient = app_request.app.state.qdrant.client
    cache = app_request.app.state.cache_service

    chunk = (body.chunk_id or "").strip() or None
    source = (body.source_identifier or "").strip() or None

    ids = await _collect_matching_ids(
        collection=collection,
        client=qclient,
        chunk_id=chunk,
        source_identifier=source,
    )

    for cid in ids:
        await cache.delete(cid)

    if ids:
        INVALIDATIONS_TOTAL.inc(len(ids))
        logger.info(
            "cache.invalidation",
            invalidated_count=len(ids),
            chunk_id=chunk,
            source_identifier=source,
        )

    return ResponseEnvelope.ok(
        InternalCacheInvalidateResponse(
            invalidated_count=len(ids),
            invalidated_cache_ids=ids,
        )
    )
