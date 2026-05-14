from fastapi import APIRouter, HTTPException, Request

from shared.contracts.internal import (
    InternalEmbedRequest,
    InternalGenerateRequest,
    InternalSparseEmbedRequest,
)
from shared.models.schemas import ResponseEnvelope

router = APIRouter()


@router.post("/v1/embed")
async def internal_embed(request: InternalEmbedRequest, app_request: Request):
    try:
        data = await app_request.app.state.ai_inference_service.embed(request)
        return ResponseEnvelope.ok(data)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=429 if "rate limit" in str(e).lower() else 500, detail=str(e)
        )


@router.post("/v1/generate")
async def internal_generate(request: InternalGenerateRequest, app_request: Request):
    try:
        data = await app_request.app.state.ai_inference_service.generate(request)
        return ResponseEnvelope.ok(data)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=429 if "rate limit" in str(e).lower() else 500, detail=str(e)
        )


@router.post("/v1/sparse-embed")
async def internal_sparse_embed(request: InternalSparseEmbedRequest, app_request: Request):
    try:
        data = await app_request.app.state.ai_inference_service.sparse_encode(request)
        return ResponseEnvelope.ok(data)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=429 if "rate limit" in str(e).lower() else 500, detail=str(e)
        )

