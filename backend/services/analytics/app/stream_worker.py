"""Project analytics_events stream into Redis read model."""

from __future__ import annotations

import asyncio
import os

from redis.exceptions import ResponseError

from shared.config.settings import Settings
from shared.contracts.streams import AnalyticsEventV1, parse_payload_json
from shared.infra.stream_runtime import ensure_consumer_group, reclaim_stale_pending_messages
from shared.models.enums import AgentAction, ResponseSource
from shared.observability.logger import get_logger
from shared.stream_topology import CG_ANALYTICS, STREAM_ANALYTICS_EVENTS_V1

logger = get_logger(__name__)


async def run_analytics_projector(
    *, settings: Settings, redis_infra, analytics_service
) -> None:
    r = redis_infra.client
    stream = STREAM_ANALYTICS_EVENTS_V1
    group = CG_ANALYTICS
    consumer = f"analytics-{os.getpid()}"
    await ensure_consumer_group(r, stream, group)
    logger.info("analytics_stream.projector_started", consumer=consumer)

    while True:
        resp = None
        try:
            for msg_id, fields in await reclaim_stale_pending_messages(
                r,
                stream=stream,
                group=group,
                consumer=consumer,
                min_idle_ms=settings.stream_reclaim_min_idle_ms,
            ):
                try:
                    evt = parse_payload_json(fields, AnalyticsEventV1)
                    assert isinstance(evt, AnalyticsEventV1)
                    await analytics_service.record_query(
                        query=evt.query,
                        source=ResponseSource(evt.source),
                        agent_action=AgentAction(evt.agent_action),
                        similarity_score=evt.similarity_score,
                        latency_ms=evt.latency_ms,
                        cache_id=evt.cache_id,
                        response_text=evt.response_text,
                        job_id=evt.job_id,
                    )
                    await r.xack(stream, group, msg_id)
                except Exception as e:  # noqa: BLE001
                    logger.exception(
                        "analytics_stream.project_failed",
                        msg_id=msg_id,
                        error=str(e),
                    )
                    await r.xack(stream, group, msg_id)

            resp = await r.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: ">"},
                count=16,
                block=2000,
            )
        except asyncio.CancelledError:
            raise
        except ResponseError as e:
            logger.warning("analytics_stream.read_error", error=str(e))
            await asyncio.sleep(1.0)
            continue
        except Exception as e:  # noqa: BLE001
            logger.warning("analytics_stream.unexpected_read", error=str(e))
            await asyncio.sleep(0.5)
            continue

        if not resp:
            continue

        for _, messages in resp:
            for msg_id, fields in messages:
                try:
                    evt = parse_payload_json(fields, AnalyticsEventV1)
                    assert isinstance(evt, AnalyticsEventV1)
                    await analytics_service.record_query(
                        query=evt.query,
                        source=ResponseSource(evt.source),
                        agent_action=AgentAction(evt.agent_action),
                        similarity_score=evt.similarity_score,
                        latency_ms=evt.latency_ms,
                        cache_id=evt.cache_id,
                        response_text=evt.response_text,
                        job_id=evt.job_id,
                    )
                    await r.xack(stream, group, msg_id)
                except Exception as e:  # noqa: BLE001
                    logger.exception(
                        "analytics_stream.project_failed",
                        msg_id=msg_id,
                        error=str(e),
                    )
                    await r.xack(stream, group, msg_id)
