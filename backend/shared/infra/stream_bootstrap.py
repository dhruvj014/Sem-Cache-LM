"""Ensure Redis stream consumer groups exist for the async pipeline."""

from __future__ import annotations

import redis.asyncio as redis

from shared.config.settings import Settings
from shared.infra.stream_runtime import ensure_consumer_group
from shared.stream_topology import (
    CG_AI,
    CG_ANALYTICS,
    CG_CACHE,
    CG_RAG,
    STREAM_AI_COMMANDS_V1,
    STREAM_ANALYTICS_EVENTS_V1,
    STREAM_CACHE_COMMANDS_V1,
    STREAM_QUERY_COMMANDS_V1,
    STREAM_RAG_COMMANDS_V1,
)


async def ensure_async_pipeline_topology(client: redis.Redis, settings: Settings) -> None:
    await ensure_consumer_group(client, STREAM_QUERY_COMMANDS_V1, settings.orchestrator_consumer_group)
    await ensure_consumer_group(client, STREAM_CACHE_COMMANDS_V1, CG_CACHE)
    await ensure_consumer_group(client, STREAM_AI_COMMANDS_V1, CG_AI)
    await ensure_consumer_group(client, STREAM_RAG_COMMANDS_V1, CG_RAG)
    await ensure_consumer_group(client, STREAM_ANALYTICS_EVENTS_V1, CG_ANALYTICS)
