from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from services.gateway.app.api.v1 import (
    analytics,
    cache,
    cache_invalidate,
    decision_thresholds_api,
    feedback,
    health,
    query,
)
from services.gateway.app.config import get_settings
from services.gateway.app.services.feedback_service import FeedbackService
from shared.clients.http import HttpAIClient, HttpAnalyticsClient, HttpCacheClient, HttpRagClient
from shared.domain.decision_thresholds import DecisionThresholds
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

    await ensure_async_pipeline_topology(redis_infra.client, settings)

    http_client = httpx.AsyncClient()

    http_ai_client = HttpAIClient(settings, http_client)
    http_cache_client = HttpCacheClient(settings, http_client)
    http_rag_client = HttpRagClient(settings, http_client)
    analytics_client = HttpAnalyticsClient(settings, http_client)
    decision_thresholds = DecisionThresholds(settings)

    app.state.settings = settings
    app.state.redis = redis_infra
    app.state.http_client = http_client
    app.state.http_ai_client = http_ai_client
    app.state.cache_boundary = http_cache_client
    app.state.http_rag_client = http_rag_client
    app.state.analytics_boundary = analytics_client
    app.state.feedback_service = FeedbackService(settings, redis_infra, http_cache_client)
    app.state.decision_thresholds = decision_thresholds
    logger.info("app.started")
    try:
        yield
    finally:
        logger.info("app.shutting_down")
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
    app.include_router(cache_invalidate.router, prefix=prefix, tags=["cache-invalidate"])
    app.include_router(analytics.router, prefix=prefix, tags=["analytics"])
    app.include_router(decision_thresholds_api.router, prefix=prefix, tags=["config"])

    Instrumentator().instrument(app).expose(app)
    return app


app = create_app()
