from contextlib import asynccontextmanager

import asyncio
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.gateway.app.api.v1 import (
    analytics,
    cache,
    decision_thresholds_api,
    feedback,
    health,
    internal_services,
    query,
)
from services.gateway.app.config import get_settings
from services.gateway.app.services.agent_decision import AgentDecisionLayer
from services.gateway.app.services.decision_thresholds import DecisionThresholds
from services.gateway.app.services.analytics_stream_publish import (
    GatewayAnalyticsStreamPublisher,
)
from services.gateway.app.services.false_hit_detector import FalseHitDetector
from services.gateway.app.services.feedback_service import FeedbackService
from services.gateway.app.services.http_ai_client import HttpAIClient
from services.gateway.app.services.query_router import QueryRouterService
from services.gateway.app.services.session_context import SessionContextService
from services.gateway.app.clients import HttpAnalyticsClient, HttpCacheClient, HttpRagClient
from services.gateway.app.workers.query_stream_orchestrator import QueryStreamOrchestrator
from shared.infra.redis_client import RedisInfrastructure
from shared.infra.stream_bootstrap import ensure_async_pipeline_topology
from shared.observability.correlation import CorrelationIdMiddleware
from shared.observability.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("app.starting", env=settings.app_env, version=settings.app_version)

    redis_infra = RedisInfrastructure(settings)
    await redis_infra.connect()

    if settings.query_pipeline_async:
        await ensure_async_pipeline_topology(redis_infra.client, settings)

    http_client = httpx.AsyncClient()

    http_ai_client = HttpAIClient(settings, http_client)
    http_cache_client = HttpCacheClient(settings, http_client)
    http_rag_client = HttpRagClient(settings, http_client)
    analytics_client = HttpAnalyticsClient(settings, http_client)

    session_context = SessionContextService(
        redis_infra, ttl_seconds=settings.session_context_ttl_seconds
    )
    decision_thresholds = DecisionThresholds(settings)
    agent = AgentDecisionLayer(decision_thresholds)

    false_hit_detector = FalseHitDetector(settings, http_ai_client, redis_infra)

    analytics_publisher = GatewayAnalyticsStreamPublisher(redis_infra.client, settings)

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

    orch_tasks: list[asyncio.Task] = []
    if settings.query_pipeline_async:
        orchestrator = QueryStreamOrchestrator(
            settings,
            redis_infra,
            agent,
            session_context,
            false_hit_detector,
        )
        orch_tasks.append(
            asyncio.create_task(orchestrator.run_forever(), name="query-stream-orchestrator")
        )

    app.state.settings = settings
    app.state.redis = redis_infra
    app.state.http_client = http_client
    app.state.http_ai_client = http_ai_client
    app.state.embedder = http_ai_client
    app.state.llm = http_ai_client
    app.state.cache_boundary = http_cache_client
    app.state.false_hit_detector = false_hit_detector
    app.state.agent = agent
    app.state.analytics_boundary = analytics_client
    app.state.feedback_service = FeedbackService(settings, redis_infra, http_cache_client)
    app.state.query_router = query_router
    app.state.decision_thresholds = decision_thresholds
    app.state._orch_tasks = orch_tasks

    logger.info("app.started")
    try:
        yield
    finally:
        logger.info("app.shutting_down")
        for t in getattr(app.state, "_orch_tasks", []):
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
        title="SemCacheLM",
        version=settings.app_version,
        description="Quality-Aware Semantic Caching System for LLMs",
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

    prefix = "/api/v1"
    app.include_router(health.router, prefix=prefix, tags=["health"])
    app.include_router(query.router, prefix=prefix, tags=["query"])
    app.include_router(feedback.router, prefix=prefix, tags=["feedback"])
    app.include_router(cache.router, prefix=prefix, tags=["cache"])
    app.include_router(analytics.router, prefix=prefix, tags=["analytics"])
    app.include_router(
        internal_services.router,
        prefix="/internal",
        tags=["internal"],
    )
    app.include_router(decision_thresholds_api.router, prefix=prefix, tags=["config"])

    return app


app = create_app()
