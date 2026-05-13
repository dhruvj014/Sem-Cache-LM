import asyncio

import httpx
from fastapi import APIRouter, Request

from services.gateway.app.config import Settings, get_settings
from shared.models.schemas import HealthStatus, ResponseEnvelope
from shared.stream_topology import MONITORED_STREAM_GROUPS

router = APIRouter()


async def orchestrator_service_health(
    settings: Settings, http: httpx.AsyncClient
) -> bool:
    base = (settings.orchestrator_service_base_url or "").rstrip("/")
    if not base:
        return False
    try:
        resp = await http.get(
            f"{base}/api/v1/docs",
            timeout=min(5.0, settings.orchestrator_service_request_timeout_seconds),
        )
        return resp.status_code < 500
    except Exception:
        return False


@router.get("/health/streams")
async def health_streams(request: Request):
    """XPENDING summary per monitored command/event stream (ops / backlog)."""
    r = request.app.state.redis.client
    rows: list[dict] = []
    for stream, group in MONITORED_STREAM_GROUPS:
        try:
            pend = await r.xpending(stream, group)
            if isinstance(pend, dict):
                pending = int(pend.get("pending", 0) or 0)
            elif pend:
                pending = int(pend[0])
            else:
                pending = 0
            rows.append(
                {"stream": stream, "group": group, "pending": pending, "error": None}
            )
        except Exception as e:  # noqa: BLE001
            rows.append(
                {
                    "stream": stream,
                    "group": group,
                    "pending": None,
                    "error": str(e),
                }
            )
    return ResponseEnvelope.ok({"streams": rows})


@router.get("/health", response_model=ResponseEnvelope[HealthStatus])
async def health(request: Request):
    settings = get_settings()
    redis_ok = await request.app.state.redis.health()
    ai_ok, cache_ok, rag_ok, analytics_ok, orchestrator_ok = await asyncio.gather(
        request.app.state.http_ai_client.health(),
        request.app.state.cache_boundary.health(),
        request.app.state.http_rag_client.health(),
        request.app.state.analytics_boundary.health(),
        orchestrator_service_health(
            request.app.state.settings, request.app.state.http_client
        ),
    )

    services = {
        "redis": redis_ok,
        "ai_service": ai_ok,
        "cache_service": cache_ok,
        "rag_service": rag_ok,
        "analytics_service": analytics_ok,
        "orchestrator_service": orchestrator_ok,
    }
    status = "ok" if all(services.values()) else "degraded"
    return ResponseEnvelope.ok(
        HealthStatus(
            status=status,
            version=settings.app_version,
            services=services,
            llm_model=settings.active_llm_model_id,
            embedding_model=settings.active_embedding_model_id,
            qdrant_collection=settings.qdrant_collection,
        )
    )
