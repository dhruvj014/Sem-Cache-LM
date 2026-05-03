from fastapi import APIRouter, Request

from app.config import get_settings
from app.models.schemas import HealthStatus, ResponseEnvelope

router = APIRouter()


@router.get("/health", response_model=ResponseEnvelope[HealthStatus])
async def health(request: Request):
    settings = get_settings()
    qdrant_ok = await request.app.state.qdrant.health()
    redis_ok = await request.app.state.redis.health()
    ollama_ok = await request.app.state.llm.health()

    services = {
        "qdrant": qdrant_ok,
        "redis": redis_ok,
        "ollama": ollama_ok,
    }
    status = "ok" if all(services.values()) else "degraded"
    return ResponseEnvelope.ok(
        HealthStatus(
            status=status,
            version=settings.app_version,
            services=services,
            llm_model=settings.ollama_llm_model,
            embedding_model=settings.ollama_embedding_model,
            qdrant_collection=settings.qdrant_collection,
        )
    )
