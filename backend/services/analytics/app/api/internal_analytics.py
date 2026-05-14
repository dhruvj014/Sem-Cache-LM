from __future__ import annotations

from fastapi import APIRouter, Query, Request

from shared.models.enums import AgentAction, ResponseSource
from shared.contracts.internal import InternalQueryEvent
from shared.models.schemas import ResponseEnvelope

router = APIRouter()


@router.post("/v1/events/query")
async def internal_query_event(request: InternalQueryEvent, app_request: Request):
    analytics = app_request.app.state.analytics_boundary
    await analytics.record_query(
        query=request.query,
        source=ResponseSource(request.source),
        agent_action=AgentAction(request.agent_action),
        similarity_score=request.similarity_score,
        latency_ms=request.latency_ms,
        cache_id=request.cache_id,
        response_text=request.response_text,
        job_id=request.job_id,
    )
    return ResponseEnvelope.ok({"accepted": True, "correlation_id": request.correlation_id})


@router.get("/v1/summary")
async def internal_summary(app_request: Request):
    analytics = app_request.app.state.analytics_boundary
    return ResponseEnvelope.ok((await analytics.summary()).model_dump())


@router.get("/v1/history")
async def internal_history(app_request: Request, limit: int = Query(20, ge=1, le=200)):
    analytics = app_request.app.state.analytics_boundary
    return ResponseEnvelope.ok((await analytics.history(limit)).model_dump())


@router.post("/v1/reset")
async def internal_reset(app_request: Request):
    analytics = app_request.app.state.analytics_boundary
    await analytics.reset()
    return ResponseEnvelope.ok({"reset": True})

