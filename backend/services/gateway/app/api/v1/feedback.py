from fastapi import APIRouter, Depends, HTTPException

from services.gateway.app.dependencies import get_feedback_service
from shared.models.schemas import FeedbackRequest, FeedbackResult, ResponseEnvelope
from services.gateway.app.services.feedback_service import FeedbackService
from shared.observability.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/feedback/{cache_id}", response_model=ResponseEnvelope[FeedbackResult])
async def submit_feedback(
    cache_id: str,
    request: FeedbackRequest,
    service: FeedbackService = Depends(get_feedback_service),
):
    try:
        result = await service.submit_feedback(cache_id, request.rating)
        return ResponseEnvelope.ok(result)
    except Exception as e:
        logger.error("feedback.failed", error=str(e), cache_id=cache_id)
        raise HTTPException(status_code=500, detail=str(e))
