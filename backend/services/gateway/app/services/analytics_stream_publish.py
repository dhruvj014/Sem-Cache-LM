"""Publish query analytics to Redis Streams (async projector path) — no HTTP hot path."""

from __future__ import annotations

import uuid

import structlog

from services.gateway.app.config import Settings
from shared.contracts.streams import SCHEMA_VERSION_V1, AnalyticsEventV1
from shared.infra.stream_runtime import xadd_model
from shared.models.schemas import QueryResponse
from shared.stream_topology import STREAM_ANALYTICS_EVENTS_V1


class GatewayAnalyticsStreamPublisher:
    def __init__(self, redis_client, settings: Settings) -> None:
        self._r = redis_client
        self._settings = settings

    async def publish(self, *, query: str, response: QueryResponse) -> None:
        if not self._settings.analytics_via_stream:
            return
        cid = structlog.contextvars.get_contextvars().get("correlation_id") or "unknown"
        cmd_id = str(uuid.uuid4())
        evt = AnalyticsEventV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=str(cid),
            job_id=f"sync-{cmd_id}",
            command_id=cmd_id,
            producer="gateway-sync",
            query=query,
            source=response.source.value,
            agent_action=response.agent_action.value,
            similarity_score=response.similarity_score,
            latency_ms=response.latency_ms,
            cache_id=response.cache_id,
            response_text=response.response,
        )
        await xadd_model(self._r, STREAM_ANALYTICS_EVENTS_V1, evt)
