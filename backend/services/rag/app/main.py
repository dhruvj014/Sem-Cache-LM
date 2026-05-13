from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from qdrant_client import AsyncQdrantClient

from services.rag.app.api.catalog import router as catalog_router
from services.rag.app.services.api_catalog_service import ApiCatalogService
from services.rag.app.services.catalog_cache_service import CatalogCacheService
from services.rag.app.services.rag_service import RagService
from services.rag.app.services.repo_catalog_service import RepoCatalogService
from services.rag.app.api.invalidation import router as rag_invalidation_router
from services.rag.app.api.rag_internal import router as rag_internal_router
from services.rag.app.stream_worker import run_rag_stream_worker
from shared.config.settings import get_settings
from shared.infra.internal_auth import InternalAuthMiddleware
from shared.infra.qdrant_client import build_qdrant_kwargs
from shared.infra.redis_client import RedisInfrastructure
from shared.observability.correlation import CorrelationIdMiddleware
from shared.observability.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("rag_service.starting", env=settings.app_env, version=settings.app_version)

    if not (settings.gemini_api_key or "").strip():
        raise RuntimeError("GEMINI_API_KEY is required for the RAG service")

    redis_infra = RedisInfrastructure(settings)
    await redis_infra.connect()

    rag_q_kwargs = build_qdrant_kwargs(
        settings.rag_qdrant_host_resolved,
        settings.rag_qdrant_port_resolved,
        api_key=settings.rag_qdrant_api_key_resolved,
        https=settings.rag_qdrant_https_resolved,
    )
    rag_q_kwargs["prefer_grpc"] = False
    rag_qdrant_client = AsyncQdrantClient(**rag_q_kwargs)

    rag_service = RagService(settings)
    await rag_service.initialize()

    repo_catalog_service = RepoCatalogService(settings)
    api_catalog_service = ApiCatalogService(settings)
    catalog_cache_service = CatalogCacheService(settings, redis_infra)

    if settings.rag_catalog_startup_generate:
        repo_artifacts = repo_catalog_service.generate()
        api_artifacts = api_catalog_service.generate(app)
        await catalog_cache_service.sync_files(
            [
                repo_artifacts.catalog_json_path,
                repo_artifacts.catalog_md_path,
                api_artifacts.catalog_json_path,
                api_artifacts.catalog_md_path,
            ]
        )
        await rag_service.initialize()

    tasks: list[asyncio.Task] = []
    if settings.stream_workers_enabled:
        tasks.append(
            asyncio.create_task(
                run_rag_stream_worker(
                    settings=settings,
                    redis_infra=redis_infra,
                    rag_service=rag_service,
                ),
                name="rag-stream-worker",
            )
        )

    app.state.redis = redis_infra
    app.state.rag_qdrant_client = rag_qdrant_client
    app.state.rag_service = rag_service
    app.state.repo_catalog_service = repo_catalog_service
    app.state.api_catalog_service = api_catalog_service
    app.state.catalog_cache_service = catalog_cache_service
    app.state._bg_tasks = tasks

    logger.info("rag_service.started")
    try:
        yield
    finally:
        logger.info("rag_service.shutting_down")
        for t in getattr(app.state, "_bg_tasks", []):
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        await rag_qdrant_client.close()
        await redis_infra.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SemCacheLM RAG Service",
        version=settings.app_version,
        description="RAG + catalog retrieval service for SemCacheLM",
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

    prefix = "/api/v1"
    app.include_router(catalog_router, prefix=prefix, tags=["catalog"])
    app.include_router(rag_internal_router, prefix="/internal", tags=["internal"])
    app.include_router(rag_invalidation_router, prefix="/internal", tags=["internal-rag-invalidate"])
    Instrumentator().instrument(app).expose(app)
    return app


app = create_app()
