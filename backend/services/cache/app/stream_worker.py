"""Redis Streams consumer for cache commands (cache microservice)."""

from __future__ import annotations

import asyncio
import json
import os
from typing import TYPE_CHECKING

from redis.exceptions import ResponseError

from shared.config.settings import Settings
from shared.contracts.streams import (
    SCHEMA_VERSION_V1,
    CacheCommandKind,
    CacheCommandV1,
    CacheResultV1,
    parse_payload_json,
)
from shared.infra.stream_runtime import (
    ensure_consumer_group,
    get_cmd_result_json,
    publish_deadletter,
    reclaim_stale_pending_messages,
    set_cmd_result,
    xadd_model,
)
from shared.observability.logger import get_logger
from shared.stream_topology import CG_CACHE, STREAM_CACHE_COMMANDS_V1, STREAM_CACHE_RESULTS_V1

if TYPE_CHECKING:
    from shared.infra.redis_client import RedisInfrastructure
    from services.cache.app.services.cache_service import CacheService

logger = get_logger(__name__)


async def run_cache_stream_worker(
    *,
    settings: Settings,
    redis_infra: RedisInfrastructure,
    cache_service: CacheService,
) -> None:
    r = redis_infra.client
    stream = STREAM_CACHE_COMMANDS_V1
    group = CG_CACHE
    consumer = f"cache-{os.getpid()}"
    await ensure_consumer_group(r, stream, group)
    logger.info("cache_stream.worker_started", consumer=consumer)

    while True:
        try:
            for msg_id, fields in await reclaim_stale_pending_messages(
                r,
                stream=stream,
                group=group,
                consumer=consumer,
                min_idle_ms=settings.stream_reclaim_min_idle_ms,
            ):
                await _handle_one(
                    r=r,
                    settings=settings,
                    cache_service=cache_service,
                    stream=stream,
                    group=group,
                    msg_id=msg_id,
                    fields=fields,
                )

            resp = await r.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: ">"},
                count=8,
                block=2000,
            )
        except asyncio.CancelledError:
            raise
        except ResponseError as e:
            logger.warning("cache_stream.read_error", error=str(e))
            await asyncio.sleep(1.0)
            continue
        except Exception as e:  # noqa: BLE001
            logger.warning("cache_stream.unexpected_read", error=str(e))
            await asyncio.sleep(0.5)
            continue

        if not resp:
            continue

        for _, messages in resp:
            for msg_id, fields in messages:
                await _handle_one(
                    r=r,
                    settings=settings,
                    cache_service=cache_service,
                    stream=stream,
                    group=group,
                    msg_id=msg_id,
                    fields=fields,
                )


async def _handle_one(
    *,
    r,
    settings: Settings,
    cache_service: CacheService,
    stream: str,
    group: str,
    msg_id: str,
    fields: dict,
) -> None:
    cmd = parse_payload_json(fields, CacheCommandV1)
    assert isinstance(cmd, CacheCommandV1)
    cid = cmd.command_id
    ttl = settings.cmd_result_ttl_seconds

    existing = await get_cmd_result_json(r, cid)
    if existing:
        res = CacheResultV1.model_validate(existing)
        await xadd_model(r, STREAM_CACHE_RESULTS_V1, res)
        await r.xack(stream, group, msg_id)
        return

    try:
        if cmd.kind == CacheCommandKind.search:
            if not cmd.embedding or cmd.top_k is None:
                raise ValueError("cache search requires embedding and top_k")
            hits = await cache_service.search(
                cmd.embedding,
                top_k=cmd.top_k,
                sparse_indices=cmd.sparse_indices or None,
                sparse_values=cmd.sparse_values or None,
            )
            result = CacheResultV1(
                schema_version=SCHEMA_VERSION_V1,
                correlation_id=cmd.correlation_id,
                job_id=cmd.job_id,
                command_id=cid,
                trace_id=cmd.trace_id,
                producer="cache-service",
                attempt=cmd.attempt,
                hits=[h.model_dump() for h in hits],
            )
        elif cmd.kind == CacheCommandKind.store:
            if not cmd.query or not cmd.embedding or cmd.response is None:
                raise ValueError("cache store requires query, embedding, response")
            new_id = await cache_service.store(
                cmd.query,
                cmd.embedding,
                cmd.response,
                cmd.metadata or {},
                sparse_indices=cmd.sparse_indices or None,
                sparse_values=cmd.sparse_values or None,
            )
            result = CacheResultV1(
                schema_version=SCHEMA_VERSION_V1,
                correlation_id=cmd.correlation_id,
                job_id=cmd.job_id,
                command_id=cid,
                trace_id=cmd.trace_id,
                producer="cache-service",
                attempt=cmd.attempt,
                cache_id=new_id,
            )
        elif cmd.kind == CacheCommandKind.increment_hit:
            if not cmd.cache_id:
                raise ValueError("increment_hit requires cache_id")
            await cache_service.increment_hit(cmd.cache_id)
            result = CacheResultV1(
                schema_version=SCHEMA_VERSION_V1,
                correlation_id=cmd.correlation_id,
                job_id=cmd.job_id,
                command_id=cid,
                trace_id=cmd.trace_id,
                producer="cache-service",
                attempt=cmd.attempt,
                cache_id=cmd.cache_id,
            )
        else:
            raise ValueError(f"unknown cache command {cmd.kind}")

        payload = json.loads(result.model_dump_json())
        await set_cmd_result(r, cid, payload, ttl_seconds=ttl)
        await xadd_model(r, STREAM_CACHE_RESULTS_V1, result)
        await r.xack(stream, group, msg_id)

    except Exception as e:  # noqa: BLE001
        logger.exception("cache_stream.handler_failed", command_id=cid, error=str(e))
        err_res = CacheResultV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=cmd.correlation_id,
            job_id=cmd.job_id,
            command_id=cid,
            trace_id=cmd.trace_id,
            producer="cache-service",
            attempt=cmd.attempt,
            ok=False,
            error=str(e),
        )
        await set_cmd_result(
            r,
            cid,
            json.loads(err_res.model_dump_json()),
            ttl_seconds=ttl,
        )
        await xadd_model(r, STREAM_CACHE_RESULTS_V1, err_res)
        await publish_deadletter(
            r,
            stream=stream,
            job_id=cmd.job_id,
            correlation_id=cmd.correlation_id,
            command_id=cid,
            original_payload_json=json.dumps(fields),
            reason=str(e),
            producer="cache-service",
        )
        await r.xack(stream, group, msg_id)
