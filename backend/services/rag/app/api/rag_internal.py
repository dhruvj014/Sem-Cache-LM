from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from shared.contracts.internal import (
    InternalRagCitation,
    InternalRagRetrieveRequest,
    InternalRagRetrieveResponse,
)
from shared.models.schemas import ResponseEnvelope
from shared.observability.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/v1/retrieve")
async def rag_internal_retrieve(
    request: InternalRagRetrieveRequest,
    app_request: Request,
):
    try:
        rag = app_request.app.state.rag_service
        logger.info(
            "rag.internal_retrieve.start",
            query_preview=(request.query or "")[:80],
        )
        result = await rag.answer(request.query)
        citations = [
            InternalRagCitation(
                file_path=c.file_path,
                score=c.score,
                snippet=c.snippet,
            )
            for c in result.citations
        ]
        logger.info(
            "rag.internal_retrieve.done",
            citations_count=len(citations),
        )
        payload = InternalRagRetrieveResponse(answer=result.response, citations=citations)
        return ResponseEnvelope.ok(payload)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))

