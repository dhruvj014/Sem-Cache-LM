from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from services.orchestrator.app.domain.agent_decision import AgentDecisionLayer
from services.orchestrator.app.domain.session_context import SessionContextService
from services.orchestrator.app.stream_worker import QueryStreamOrchestrator
from shared.config.settings import get_settings
from shared.domain.decision_thresholds import DecisionThresholds
from shared.infra.internal_auth import InternalAuthMiddleware
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

    session_context = SessionContextService(
        redis_infra, ttl_seconds=settings.session_context_ttl_seconds
    )
    decision_thresholds = DecisionThresholds(settings)
    agent = AgentDecisionLayer(decision_thresholds)

    tasks: list[asyncio.Task] = []
    orchestrator = QueryStreamOrchestrator(
        settings,
        redis_infra,
        agent,
        session_context,
    )
    tasks.append(
        asyncio.create_task(orchestrator.run_forever(), name="query-stream-orchestrator")
    )

    app.state.redis = redis_infra
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
    app.add_middleware(InternalAuthMiddleware, token=settings.internal_service_token)

    Instrumentator().instrument(app).expose(app)
    return app


app = create_app()
