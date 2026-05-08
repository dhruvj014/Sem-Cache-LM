"""Redis Streams consumer for AI commands."""

from __future__ import annotations

import asyncio
import json
import os

from redis.exceptions import ResponseError

from shared.config.settings import Settings
from shared.contracts.internal import InternalEmbedRequest, InternalGenerateRequest
from shared.contracts.streams import (
    SCHEMA_VERSION_V1,
    AiCommandKind,
    AiCommandV1,
    AiResultV1,
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
from shared.stream_topology import CG_AI, STREAM_AI_COMMANDS_V1, STREAM_AI_RESULTS_V1

logger = get_logger(__name__)


async def run_ai_stream_worker(*, settings: Settings, redis_infra, ai_inference_service) -> None:
    r = redis_infra.client
    stream = STREAM_AI_COMMANDS_V1
    group = CG_AI
    consumer = f"ai-{os.getpid()}"
    await ensure_consumer_group(r, stream, group)
    logger.info("ai_stream.worker_started", consumer=consumer)

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
                    svc=ai_inference_service,
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
            logger.warning("ai_stream.read_error", error=str(e))
            await asyncio.sleep(1.0)
            continue
        except Exception as e:  # noqa: BLE001
            logger.warning("ai_stream.unexpected_read", error=str(e))
            await asyncio.sleep(0.5)
            continue

        if not resp:
            continue

        for _, messages in resp:
            for msg_id, fields in messages:
                await _handle_one(
                    r=r,
                    settings=settings,
                    svc=ai_inference_service,
                    stream=stream,
                    group=group,
                    msg_id=msg_id,
                    fields=fields,
                )


async def _handle_one(*, r, settings: Settings, svc, stream: str, group: str, msg_id: str, fields: dict):
    cmd = parse_payload_json(fields, AiCommandV1)
    assert isinstance(cmd, AiCommandV1)
    cid = cmd.command_id
    ttl = settings.cmd_result_ttl_seconds

    existing = await get_cmd_result_json(r, cid)
    if existing:
        res = AiResultV1.model_validate(existing)
        await xadd_model(r, STREAM_AI_RESULTS_V1, res)
        await r.xack(stream, group, msg_id)
        return

    try:
        if cmd.kind == AiCommandKind.embed:
            out = await svc.embed(InternalEmbedRequest(text=cmd.text))
            result = AiResultV1(
                schema_version=SCHEMA_VERSION_V1,
                correlation_id=cmd.correlation_id,
                job_id=cmd.job_id,
                command_id=cid,
                trace_id=cmd.trace_id,
                producer="ai-service",
                attempt=cmd.attempt,
                embedding=out.embedding,
                vector_size=out.vector_size,
                latency_ms=out.latency_ms,
            )
        elif cmd.kind == AiCommandKind.generate:
            out = await svc.generate(
                InternalGenerateRequest(prompt=cmd.text, system=cmd.system)
            )
            result = AiResultV1(
                schema_version=SCHEMA_VERSION_V1,
                correlation_id=cmd.correlation_id,
                job_id=cmd.job_id,
                command_id=cid,
                trace_id=cmd.trace_id,
                producer="ai-service",
                attempt=cmd.attempt,
                generated_text=out.text,
                latency_ms=out.latency_ms,
            )
        else:
            raise ValueError(f"unknown ai kind {cmd.kind}")

        payload = json.loads(result.model_dump_json())
        await set_cmd_result(r, cid, payload, ttl_seconds=ttl)
        await xadd_model(r, STREAM_AI_RESULTS_V1, result)
        await r.xack(stream, group, msg_id)

    except Exception as e:  # noqa: BLE001
        logger.exception("ai_stream.handler_failed", command_id=cid, error=str(e))
        err_res = AiResultV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=cmd.correlation_id,
            job_id=cmd.job_id,
            command_id=cid,
            trace_id=cmd.trace_id,
            producer="ai-service",
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
        await xadd_model(r, STREAM_AI_RESULTS_V1, err_res)
        await publish_deadletter(
            r,
            stream=stream,
            job_id=cmd.job_id,
            correlation_id=cmd.correlation_id,
            command_id=cid,
            original_payload_json=json.dumps(fields),
            reason=str(e),
            producer="ai-service",
        )
        await r.xack(stream, group, msg_id)
