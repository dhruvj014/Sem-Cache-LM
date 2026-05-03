from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_query_router
from app.models.schemas import QueryRequest, QueryResponse, ResponseEnvelope
from app.services.query_router import QueryRouterService
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/query", response_model=ResponseEnvelope[QueryResponse])
async def submit_query(
    request: QueryRequest,
    service: QueryRouterService = Depends(get_query_router),
):
    try:
        result = await service.handle_query(
            request.query,
            request.session_id,
            similarity_hit_threshold=request.similarity_hit_threshold,
            similarity_gray_zone_low=request.similarity_gray_zone_low,
        )
        return ResponseEnvelope.ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("query.failed", error=str(e), query_preview=request.query[:80])
        raise HTTPException(status_code=500, detail=str(e))
