from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from services.analytics.app.api.internal_analytics import (
    router as internal_analytics_router,
)
from services.analytics.app.services.analytics_service import AnalyticsService
from services.analytics.app.stream_worker import run_analytics_projector
from shared.config.settings import get_settings
from shared.infra.internal_auth import InternalAuthMiddleware
from shared.infra.redis_client import RedisInfrastructure
from shared.observability.correlation import CorrelationIdMiddleware
from shared.observability.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("analytics_service.starting", env=settings.app_env, version=settings.app_version)

    redis_infra = RedisInfrastructure(settings)
    await redis_infra.connect()

    analytics_service = AnalyticsService(redis_infra)

    tasks: list[asyncio.Task] = []
    if settings.analytics_stream_consumer_enabled:
        tasks.append(
            asyncio.create_task(
                run_analytics_projector(
                    settings=settings,
                    redis_infra=redis_infra,
                    analytics_service=analytics_service,
                ),
                name="analytics-stream-projector",
            )
        )

    app.state.analytics_boundary = analytics_service
    app.state.redis = redis_infra
    app.state._bg_tasks = tasks

    logger.info("analytics_service.started")
    try:
        yield
    finally:
        logger.info("analytics_service.shutting_down")
        for t in getattr(app.state, "_bg_tasks", []):
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        await redis_infra.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SemCacheLM Analytics Service",
        version=settings.app_version,
        description="Standalone analytics boundary service for SemCacheLM",
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
    app.add_middleware(InternalAuthMiddleware, token=settings.internal_service_token)
    app.include_router(
        internal_analytics_router, prefix="/internal", tags=["internal-analytics"]
    )
    Instrumentator().instrument(app).expose(app)
    return app


app = create_app()
