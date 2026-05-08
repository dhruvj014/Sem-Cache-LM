from fastapi import APIRouter, Depends

from services.orchestrator.app.dependencies import get_query_router
from services.orchestrator.app.query_router import QueryRouterService
from shared.models.schemas import QueryRequest, QueryResponse, ResponseEnvelope

router = APIRouter()


@router.post("/v1/query", response_model=ResponseEnvelope[QueryResponse])
async def orchestrate_query(
    request: QueryRequest,
    service: QueryRouterService = Depends(get_query_router),
):
    result = await service.handle_query(
        request.query,
        request.session_id,
        similarity_hit_threshold=request.similarity_hit_threshold,
        similarity_gray_zone_low=request.similarity_gray_zone_low,
    )
    return ResponseEnvelope.ok(result)
