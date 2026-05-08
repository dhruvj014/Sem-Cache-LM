from fastapi import APIRouter, Depends, Query

from services.gateway.app.dependencies import get_analytics_service
from shared.domain.analytics_ports import AnalyticsClient
from shared.models.schemas import AnalyticsSummary, HistoryResponse, ResponseEnvelope

router = APIRouter()


@router.get("/analytics/summary", response_model=ResponseEnvelope[AnalyticsSummary])
async def analytics_summary(
    service: AnalyticsClient = Depends(get_analytics_service),
):
    return ResponseEnvelope.ok(await service.summary())


@router.get("/analytics/history", response_model=ResponseEnvelope[HistoryResponse])
async def analytics_history(
    limit: int = Query(20, ge=1, le=200),
    service: AnalyticsClient = Depends(get_analytics_service),
):
    return ResponseEnvelope.ok(await service.history(limit))
