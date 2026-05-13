from __future__ import annotations

import asyncio
import os
import socket
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from services.ai.app.api.internal_ai import router as internal_ai_router
from services.ai.app.services.ai_inference_service import AIInferenceService
from services.ai.app.services.gemini_embedding import GeminiEmbeddingService
from services.ai.app.services.gemini_llm import GeminiLLMClient
from services.ai.app.stream_worker import run_ai_stream_worker
from shared.config.settings import Settings, get_settings
from shared.infra.internal_auth import InternalAuthMiddleware
from shared.infra.redis_client import RedisInfrastructure
from shared.observability.correlation import CorrelationIdMiddleware
from shared.observability.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def _require_gemini_api_key(settings: Settings) -> None:
    if not (settings.gemini_api_key or "").strip():
        raise RuntimeError("GEMINI_API_KEY is required for the AI service")


def _require_gemini_dns() -> None:
    """Fail fast if the container cannot resolve Google's Gemini API host."""
    host = "generativelanguage.googleapis.com"
    try:
        socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as e:
        raise RuntimeError(
            f"DNS lookup failed for {host} inside this container. "
            "Fix Docker DNS (e.g. add `dns: [8.8.8.8, 1.1.1.1]` under the `ai` service in "
            "docker-compose.yml), VPN/split tunneling, or corporate DNS. "
            f"Original error: {e}"
        ) from e


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("ai_service.starting", env=settings.app_env, version=settings.app_version)
    _require_gemini_api_key(settings)
    _require_gemini_dns()

    if any(os.environ.get(k) for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")):
        logger.info(
            "ai_service.proxy_env_present",
            http_proxy=bool(os.environ.get("HTTP_PROXY")),
            https_proxy=bool(os.environ.get("HTTPS_PROXY")),
            all_proxy=bool(os.environ.get("ALL_PROXY")),
        )

    redis_infra = RedisInfrastructure(settings)
    await redis_infra.connect()
    http_client = httpx.AsyncClient(trust_env=True)

    provider_embedder = GeminiEmbeddingService(settings, http_client)
    provider_llm = GeminiLLMClient(settings, http_client)
    ai_inference_service = AIInferenceService(
        settings=settings,
        provider_embedder=provider_embedder,
        provider_llm=provider_llm,
        redis_infra=redis_infra,
    )

    tasks: list[asyncio.Task] = []
    if settings.stream_workers_enabled:
        tasks.append(
            asyncio.create_task(
                run_ai_stream_worker(
                    settings=settings,
                    redis_infra=redis_infra,
                    ai_inference_service=ai_inference_service,
                ),
                name="ai-stream-worker",
            )
        )

    app.state.redis = redis_infra
    app.state.http_client = http_client
    app.state.ai_inference_service = ai_inference_service
    app.state._bg_tasks = tasks

    logger.info("ai_service.started")
    try:
        yield
    finally:
        logger.info("ai_service.shutting_down")
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
        title="SemCacheLM AI Service",
        version=settings.app_version,
        description="Standalone AI inference service for SemCacheLM",
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
    app.include_router(internal_ai_router, prefix="/internal", tags=["internal-ai"])
    Instrumentator().instrument(app).expose(app)
    return app


app = create_app()
