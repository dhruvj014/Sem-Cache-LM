from fastapi import APIRouter, Depends, Query

from app.dependencies import get_analytics_service
from app.models.schemas import AnalyticsSummary, HistoryResponse, ResponseEnvelope
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/analytics/summary", response_model=ResponseEnvelope[AnalyticsSummary])
async def analytics_summary(
    service: AnalyticsService = Depends(get_analytics_service),
):
    return ResponseEnvelope.ok(await service.summary())


@router.get("/analytics/history", response_model=ResponseEnvelope[HistoryResponse])
async def analytics_history(
    limit: int = Query(20, ge=1, le=200),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return ResponseEnvelope.ok(await service.history(limit))
