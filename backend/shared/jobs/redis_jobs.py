"""Redis hash persistence for async query jobs (`semcache:job:{job_id}`)."""

from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as redis

from shared.contracts.streams import JobStatus
from shared.stream_topology import JOB_KEY_PREFIX


async def job_create_pending(
    r: redis.Redis,
    *,
    job_id: str,
    correlation_id: str,
    ttl_seconds: int,
    query: str = "",
) -> None:
    key = f"{JOB_KEY_PREFIX}{job_id}"
    q = (query or "").strip()
    if len(q) > 4000:
        q = q[:4000]
    pipe = r.pipeline()
    pipe.hset(
        key,
        mapping={
            "status": JobStatus.pending.value,
            "correlation_id": correlation_id,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "result_json": "",
            "error": "",
            "query": q,
        },
    )
    pipe.expire(key, ttl_seconds)
    await pipe.execute()


async def job_mark_processing(r: redis.Redis, job_id: str) -> None:
    key = f"{JOB_KEY_PREFIX}{job_id}"
    await r.hset(
        key,
        mapping={
            "status": JobStatus.processing.value,
            "updated_at": _now_iso(),
        },
    )


async def job_mark_completed(
    r: redis.Redis,
    job_id: str,
    *,
    result_json: str,
) -> None:
    key = f"{JOB_KEY_PREFIX}{job_id}"
    await r.hset(
        key,
        mapping={
            "status": JobStatus.completed.value,
            "result_json": result_json,
            "error": "",
            "updated_at": _now_iso(),
        },
    )


async def job_mark_failed(
    r: redis.Redis,
    job_id: str,
    *,
    error: str,
    degraded: bool = False,
) -> None:
    key = f"{JOB_KEY_PREFIX}{job_id}"
    status = JobStatus.degraded.value if degraded else JobStatus.failed.value
    await r.hset(
        key,
        mapping={
            "status": status,
            "error": error,
            "updated_at": _now_iso(),
        },
    )


async def job_get_all(r: redis.Redis, job_id: str) -> Optional[dict[str, str]]:
    key = f"{JOB_KEY_PREFIX}{job_id}"
    raw = await r.hgetall(key)
    return dict(raw) if raw else None


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def decode_job_view(raw: dict[str, str]) -> dict[str, Any]:
    """Normalize hash fields for API responses."""
    out: dict[str, Any] = dict(raw)
    if out.get("result_json"):
        try:
            out["result"] = json.loads(out["result_json"])
        except json.JSONDecodeError:
            out["result"] = None
    else:
        out["result"] = None
    return out
