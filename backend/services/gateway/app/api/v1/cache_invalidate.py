"""Public API: invalidate semantic cache + RAG vectors for a chunk or source."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from services.gateway.app.config import get_settings
from shared.contracts.invalidation import (
    InternalCacheInvalidateRequest,
    InternalCacheInvalidateResponse,
    InternalRagInvalidateRequest,
    InternalRagInvalidateResponse,
    PublicCacheInvalidateRequest,
    PublicCacheInvalidateResponse,
)
from shared.contracts.streams import SCHEMA_VERSION_V1, AnalyticsEventV1
from shared.infra.stream_runtime import xadd_model
from shared.models.enums import AgentAction, ResponseSource
from shared.models.schemas import ResponseEnvelope
from shared.observability.logger import get_logger
from shared.stream_topology import STREAM_ANALYTICS_EVENTS_V1

logger = get_logger(__name__)
router = APIRouter()


def _internal_headers(settings: Any) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = (settings.internal_service_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _post_internal_json(
    http: httpx.AsyncClient,
    *,
    base_url: str,
    path: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    resp = await http.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise HTTPException(
            status_code=502,
            detail=data.get("error", {}).get("message") or "Downstream invalidation failed",
        )
    return data.get("data") or {}


@router.post("/cache/invalidate", response_model=ResponseEnvelope[PublicCacheInvalidateResponse])
async def public_cache_invalidate(body: PublicCacheInvalidateRequest, request: Request):
    settings = get_settings()
    http: httpx.AsyncClient = request.app.state.http_client
    headers = _internal_headers(settings)
    timeout_cache = float(settings.cache_service_request_timeout_seconds)
    timeout_rag = float(settings.rag_service_request_timeout_seconds)

    internal_req = InternalCacheInvalidateRequest(
        chunk_id=body.chunk_id,
        source_identifier=body.source_identifier,
    )
    cache_base = (settings.cache_service_base_url or "").rstrip("/")
    rag_base = (settings.rag_service_base_url or "").rstrip("/")

    try:
        cache_data = await _post_internal_json(
            http,
            base_url=cache_base,
            path="/internal/v1/cache/invalidate",
            payload=internal_req.model_dump(exclude_none=True),
            headers=headers,
            timeout=timeout_cache,
        )
    except httpx.HTTPError as e:
        logger.warning("gateway.cache_invalidate_http_error", error=str(e))
        raise HTTPException(status_code=502, detail="Cache service invalidation request failed") from e

    cache_parsed = InternalCacheInvalidateResponse.model_validate(cache_data)

    rag_source = (body.chunk_id or body.source_identifier or "").strip()
    rag_data: dict[str, Any] = {}
    try:
        rag_req = InternalRagInvalidateRequest(source_identifier=rag_source)
        rag_data = await _post_internal_json(
            http,
            base_url=rag_base,
            path="/internal/v1/rag/invalidate",
            payload=rag_req.model_dump(),
            headers=headers,
            timeout=timeout_rag,
        )
    except httpx.HTTPError as e:
        logger.warning("gateway.rag_invalidate_http_error", error=str(e))
        raise HTTPException(status_code=502, detail="RAG service invalidation request failed") from e

    rag_parsed = InternalRagInvalidateResponse.model_validate(rag_data)

    command_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    summary = {
        "event": "cache_invalidation",
        "chunk_id": body.chunk_id,
        "source_identifier": body.source_identifier,
        "cache_invalidated_count": cache_parsed.invalidated_count,
        "rag_deleted_chunk_points": rag_parsed.deleted_chunk_points,
        "rag_collections_touched": rag_parsed.collections_touched,
    }
    preview = json.dumps(summary, default=str)[:3500]
    evt = AnalyticsEventV1(
        schema_version=SCHEMA_VERSION_V1,
        correlation_id=correlation_id,
        job_id=job_id,
        command_id=command_id,
        producer="gateway",
        query=f"[cache_invalidation] {preview}",
        source=ResponseSource.LLM.value,
        agent_action=AgentAction.REJECT.value,
        similarity_score=0.0,
        latency_ms=0.0,
        cache_id=None,
        response_text=json.dumps(summary, default=str)[:8000],
    )
    await xadd_model(request.app.state.redis.client, STREAM_ANALYTICS_EVENTS_V1, evt)

    out = PublicCacheInvalidateResponse(
        cache_invalidated_count=cache_parsed.invalidated_count,
        invalidated_cache_ids=cache_parsed.invalidated_cache_ids,
        rag_deleted_chunk_points=rag_parsed.deleted_chunk_points,
        rag_collections_touched=rag_parsed.collections_touched,
        rag_confirmation="rag_chunks_deleted" if rag_parsed.deleted_chunk_points else "no_matching_rag_points",
    )
    logger.info(
        "gateway.cache_invalidation_complete",
        cache_invalidated=cache_parsed.invalidated_count,
        rag_deleted=rag_parsed.deleted_chunk_points,
    )
    return ResponseEnvelope.ok(out)
