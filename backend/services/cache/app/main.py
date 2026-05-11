from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from services.cache.app.api.internal_cache import router as internal_cache_router
from services.cache.app.services.cache_service import CacheService
from services.cache.app.stream_worker import run_cache_stream_worker
from shared.config.settings import get_settings
from shared.infra.qdrant_client import QdrantInfrastructure
from shared.infra.redis_client import RedisInfrastructure
from shared.observability.correlation import CorrelationIdMiddleware
from shared.observability.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("cache_service.starting", env=settings.app_env, version=settings.app_version)

    qdrant = QdrantInfrastructure(settings)
    await qdrant.connect()
    redis_infra = RedisInfrastructure(settings)
    await redis_infra.connect()

    cache_service = CacheService(settings, qdrant, redis_infra)

    tasks: list[asyncio.Task] = []
    if settings.stream_workers_enabled:
        tasks.append(
            asyncio.create_task(
                run_cache_stream_worker(
                    settings=settings,
                    redis_infra=redis_infra,
                    cache_service=cache_service,
                ),
                name="cache-stream-worker",
            )
        )

    app.state.qdrant = qdrant
    app.state.redis = redis_infra
    app.state.cache_service = cache_service
    app.state.cache_boundary = cache_service
    app.state._bg_tasks = tasks

    logger.info("cache_service.started")
    try:
        yield
    finally:
        logger.info("cache_service.shutting_down")
        for t in getattr(app.state, "_bg_tasks", []):
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        await redis_infra.close()
        await qdrant.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SemCacheLM Cache Service",
        version=settings.app_version,
        description="Standalone cache boundary service for SemCacheLM",
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
    app.include_router(internal_cache_router, prefix="/internal", tags=["internal-cache"])
    Instrumentator().instrument(app).expose(app)
    return app


app = create_app()
