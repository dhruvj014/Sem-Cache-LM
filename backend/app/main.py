from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    analytics,
    cache,
    catalog,
    decision_thresholds_api,
    feedback,
    health,
    query,
)
from app.config import get_settings
from app.infrastructure.qdrant_client import QdrantInfrastructure
from app.infrastructure.redis_client import RedisInfrastructure
from app.services.agent_decision import AgentDecisionLayer
from app.services.api_catalog_service import ApiCatalogService
from app.services.analytics_service import AnalyticsService
from app.services.catalog_cache_service import CatalogCacheService
from app.services.decision_thresholds import DecisionThresholds
from app.services.cache_service import CacheService
from app.services.false_hit_detector import FalseHitDetector
from app.services.feedback_service import FeedbackService
from app.services.ollama_embedding import OllamaEmbeddingService
from app.services.ollama_llm import OllamaLLMClient
from app.services.query_router import QueryRouterService
from app.services.rag_service import RagService
from app.services.repo_catalog_service import RepoCatalogService
from app.services.session_context import SessionContextService
from app.utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("app.starting", env=settings.app_env, version=settings.app_version)

    qdrant = QdrantInfrastructure(settings)
    await qdrant.connect()

    redis_infra = RedisInfrastructure(settings)
    await redis_infra.connect()

    http_client = httpx.AsyncClient()

    embedder = OllamaEmbeddingService(settings, http_client)
    llm = OllamaLLMClient(settings, http_client)
    cache_service = CacheService(settings, qdrant, redis_infra)
    false_hit_detector = FalseHitDetector(settings, llm, redis_infra)
    session_context = SessionContextService(
        redis_infra, ttl_seconds=settings.session_context_ttl_seconds
    )
    decision_thresholds = DecisionThresholds(settings)
    agent = AgentDecisionLayer(decision_thresholds)
    analytics_service = AnalyticsService(qdrant, redis_infra)
    feedback_service = FeedbackService(settings, redis_infra, cache_service)
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
        # Re-run RAG init so newly generated catalog docs are indexed too.
        await rag_service.initialize()
    query_router = QueryRouterService(
        settings=settings,
        embedder=embedder,
        cache_reader=cache_service,
        cache_writer=cache_service,
        agent=agent,
        false_hit_detector=false_hit_detector,
        llm=llm,
        rag=rag_service,
        analytics=analytics_service,
        session_context=session_context,
    )

    app.state.decision_thresholds = decision_thresholds
    app.state.settings = settings
    app.state.qdrant = qdrant
    app.state.redis = redis_infra
    app.state.http_client = http_client
    app.state.embedder = embedder
    app.state.llm = llm
    app.state.cache_service = cache_service
    app.state.false_hit_detector = false_hit_detector
    app.state.agent = agent
    app.state.analytics_service = analytics_service
    app.state.feedback_service = feedback_service
    app.state.rag_service = rag_service
    app.state.repo_catalog_service = repo_catalog_service
    app.state.api_catalog_service = api_catalog_service
    app.state.catalog_cache_service = catalog_cache_service
    app.state.query_router = query_router

    logger.info("app.started")
    try:
        yield
    finally:
        logger.info("app.shutting_down")
        await http_client.aclose()
        await redis_infra.close()
        await qdrant.close()


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

    prefix = "/api/v1"
    app.include_router(health.router, prefix=prefix, tags=["health"])
    app.include_router(query.router, prefix=prefix, tags=["query"])
    app.include_router(feedback.router, prefix=prefix, tags=["feedback"])
    app.include_router(cache.router, prefix=prefix, tags=["cache"])
    app.include_router(analytics.router, prefix=prefix, tags=["analytics"])
    if settings.rag_catalog_enable_routes:
        app.include_router(catalog.router, prefix=prefix, tags=["catalog"])
    app.include_router(
        decision_thresholds_api.router, prefix=prefix, tags=["config"]
    )

    return app


app = create_app()
