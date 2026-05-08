from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.orchestrator.app.api.internal_orchestrator import (
    router as internal_orchestrator_router,
)
from services.orchestrator.app.domain.agent_decision import AgentDecisionLayer
from services.orchestrator.app.domain.false_hit_detector import FalseHitDetector
from services.orchestrator.app.domain.session_context import SessionContextService
from services.orchestrator.app.query_router import QueryRouterService
from services.orchestrator.app.services.analytics_stream_publish import (
    OrchestratorAnalyticsStreamPublisher,
)
from services.orchestrator.app.stream_worker import QueryStreamOrchestrator
from shared.clients.http import HttpAIClient, HttpCacheClient, HttpRagClient
from shared.config.settings import get_settings
from shared.domain.decision_thresholds import DecisionThresholds
from shared.infra.redis_client import RedisInfrastructure
from shared.observability.correlation import CorrelationIdMiddleware
from shared.observability.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("orchestrator_service.starting", env=settings.app_env, version=settings.app_version)

    redis_infra = RedisInfrastructure(settings)
    await redis_infra.connect()
    http_client = httpx.AsyncClient()
    http_ai_client = HttpAIClient(settings, http_client)
    http_cache_client = HttpCacheClient(settings, http_client)
    http_rag_client = HttpRagClient(settings, http_client)

    session_context = SessionContextService(
        redis_infra, ttl_seconds=settings.session_context_ttl_seconds
    )
    decision_thresholds = DecisionThresholds(settings)
    agent = AgentDecisionLayer(decision_thresholds)
    false_hit_detector = FalseHitDetector(settings, http_ai_client, redis_infra)
    analytics_publisher = OrchestratorAnalyticsStreamPublisher(redis_infra.client, settings)
    query_router = QueryRouterService(
        settings=settings,
        embedder=http_ai_client,
        cache_reader=http_cache_client,
        cache_writer=http_cache_client,
        agent=agent,
        false_hit_detector=false_hit_detector,
        llm=http_ai_client,
        rag=http_rag_client,
        analytics_publisher=analytics_publisher,
        session_context=session_context,
    )

    tasks: list[asyncio.Task] = []
    if settings.query_pipeline_async:
        orchestrator = QueryStreamOrchestrator(
            settings,
            redis_infra,
            agent,
            session_context,
            false_hit_detector,
        )
        tasks.append(
            asyncio.create_task(orchestrator.run_forever(), name="query-stream-orchestrator")
        )

    app.state.redis = redis_infra
    app.state.http_client = http_client
    app.state.query_router = query_router
    app.state._bg_tasks = tasks
    logger.info("orchestrator_service.started")
    try:
        yield
    finally:
        logger.info("orchestrator_service.shutting_down")
        for t in getattr(app.state, "_bg_tasks", []):
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        await http_client.aclose()
        await redis_infra.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SemCacheLM Orchestrator Service",
        version=settings.app_version,
        description="Standalone query stream orchestration service",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(
        internal_orchestrator_router, prefix="/internal", tags=["internal-orchestrator"]
    )
    return app


app = create_app()
