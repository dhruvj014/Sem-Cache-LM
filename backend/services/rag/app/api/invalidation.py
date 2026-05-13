"""Internal API: remove stale RAG chunk vectors from Qdrant."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Request
from qdrant_client.http import models as qmodels

from shared.config.settings import get_settings
from shared.contracts.invalidation import (
    InternalRagInvalidateRequest,
    InternalRagInvalidateResponse,
)
from shared.models.schemas import ResponseEnvelope
from shared.observability.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _rag_collection_prefix(settings: Any) -> str:
    base_raw = (settings.rag_qdrant_collection or "rag").strip()
    base = re.sub(r"[^a-zA-Z0-9_-]", "_", base_raw)[:80]
    return f"{base}__"


def _payload_matches_source(payload: dict[str, Any], source: str) -> bool:
    sid = (source or "").strip()
    if not sid:
        return False
    fp = str(payload.get("file_path") or payload.get("filename") or payload.get("id") or "")
    if fp and (fp == sid or sid in fp or fp.endswith(sid)):
        return True
    try:
        blob = json.dumps(payload, default=str)
    except Exception:
        blob = ""
    return bool(blob and sid in blob)


async def _list_rag_collections(client: Any, prefix: str) -> list[str]:
    cols = await client.get_collections()
    return sorted(c.name for c in cols.collections if c.name.startswith(prefix))


@router.post("/v1/rag/invalidate", response_model=ResponseEnvelope[InternalRagInvalidateResponse])
async def internal_rag_invalidate(
    body: InternalRagInvalidateRequest,
    app_request: Request,
):
    settings = get_settings()
    client = app_request.app.state.rag_qdrant_client
    prefix = _rag_collection_prefix(settings)
    collections = await _list_rag_collections(client, prefix)
    sid = body.source_identifier.strip()

    by_collection: dict[str, list[str]] = defaultdict(list)
    touched: list[str] = []

    for cname in collections:
        touched.append(cname)
        offset = None
        while True:
            records, next_off = await client.scroll(
                collection_name=cname,
                limit=256,
                offset=offset,
                with_payload=True,
            )
            for rec in records:
                rid = str(rec.id)
                pl = rec.payload or {}
                if rid == sid or _payload_matches_source(pl, sid):
                    by_collection[cname].append(rid)
            if next_off is None:
                break
            offset = next_off

    deleted = 0
    for cname, ids in by_collection.items():
        if not ids:
            continue
        # Deduplicate while preserving order
        uniq: list[str] = []
        seen: set[str] = set()
        for i in ids:
            if i not in seen:
                seen.add(i)
                uniq.append(i)
        await client.delete(
            collection_name=cname,
            points_selector=qmodels.PointIdsList(points=uniq),
        )
        deleted += len(uniq)

    logger.info(
        "rag.invalidation",
        source_identifier=sid,
        deleted_chunk_points=deleted,
        collections=len(touched),
    )

    return ResponseEnvelope.ok(
        InternalRagInvalidateResponse(
            deleted_chunk_points=deleted,
            collections_touched=touched,
        )
    )
