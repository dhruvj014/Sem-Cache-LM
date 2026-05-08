"""Redis Streams helpers: consumer groups, publish, idempotent result wait."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import redis.asyncio as redis
from pydantic import BaseModel
from redis.exceptions import ResponseError

from shared.contracts.streams import redis_payload
from shared.observability.logger import get_logger
from shared.stream_topology import CMD_RESULT_PREFIX

logger = get_logger(__name__)


async def ensure_consumer_group(r: redis.Redis, stream: str, group: str) -> None:
    try:
        await r.xgroup_create(stream, group, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" in str(e):
            return
        raise


async def xadd_model(r: redis.Redis, stream: str, model: BaseModel) -> str:
    rid = await r.xadd(stream, redis_payload(model))
    return str(rid)


async def wait_cmd_result_json(
    r: redis.Redis,
    command_id: str,
    *,
    timeout_s: float,
    poll_s: float = 0.05,
) -> Optional[dict[str, Any]]:
    key = f"{CMD_RESULT_PREFIX}{command_id}"
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        raw = await r.get(key)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("cmd_result.invalid_json", command_id=command_id)
                return None
        await asyncio.sleep(poll_s)
    return None


async def set_cmd_result(
    r: redis.Redis,
    command_id: str,
    payload: dict[str, Any],
    *,
    ttl_seconds: int,
) -> None:
    key = f"{CMD_RESULT_PREFIX}{command_id}"
    await r.set(key, json.dumps(payload), ex=ttl_seconds)


async def get_cmd_result_json(
    r: redis.Redis,
    command_id: str,
) -> Optional[dict[str, Any]]:
    key = f"{CMD_RESULT_PREFIX}{command_id}"
    raw = await r.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def reclaim_stale_pending_messages(
    r: redis.Redis,
    *,
    stream: str,
    group: str,
    consumer: str,
    min_idle_ms: int,
    count: int = 16,
) -> list[tuple[str, dict[str, str]]]:
    """XAUTOCLAIM idle pending entries for this consumer (at-least-once recovery)."""
    if min_idle_ms <= 0:
        return []
    try:
        result = await r.xautoclaim(
            stream,
            group,
            consumer,
            min_idle_ms,
            start_id="0-0",
            count=count,
        )
    except ResponseError as e:
        logger.warning(
            "stream.xautoclaim_failed", stream=stream, group=group, error=str(e)
        )
        return []
    if not result or len(result) < 2:
        return []
    messages = result[1] or []
    out: list[tuple[str, dict[str, str]]] = []
    for item in messages:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            msg_id, data = item[0], item[1]
            if isinstance(data, dict):
                out.append((str(msg_id), data))
    return out


async def publish_deadletter(
    r: redis.Redis,
    *,
    stream: str,
    job_id: str,
    correlation_id: str,
    command_id: str,
    original_payload_json: str,
    reason: str,
    producer: str,
) -> None:
    from uuid import uuid4

    from shared.contracts.streams import DeadLetterV1
    from shared.contracts.streams import SCHEMA_VERSION_V1

    dlq = DeadLetterV1(
        schema_version=SCHEMA_VERSION_V1,
        correlation_id=correlation_id,
        job_id=job_id,
        command_id=str(uuid4()),
        producer=producer,
        original_stream=stream,
        original_payload_json=original_payload_json,
        reason=reason,
    )
    from shared.stream_topology import STREAM_DLQ_V1

    await xadd_model(r, STREAM_DLQ_V1, dlq)
