import time

from fastapi import APIRouter, HTTPException, Request

from shared.contracts.internal import (
    InternalEmbedRequest,
    InternalEmbedResponse,
    InternalGenerateRequest,
    InternalGenerateResponse,
)
from shared.models.schemas import ResponseEnvelope

router = APIRouter()


def _tok_estimate(text: str) -> int:
    return max(1, len(text or "") // 4)


@router.post("/v1/embed")
async def internal_embed(request: InternalEmbedRequest, app_request: Request):
    try:
        ai = app_request.app.state.http_ai_client
        t0 = time.perf_counter()
        embedding = await ai.embed(request.text)
        latency_ms = (time.perf_counter() - t0) * 1000
        vs = getattr(ai, "vector_size", None) or len(embedding)
        payload = InternalEmbedResponse(
            embedding=embedding,
            vector_size=int(vs),
            latency_ms=round(latency_ms, 2),
            provider="http-ai-gateway",
        )
        return ResponseEnvelope.ok(payload.model_dump())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=429 if "rate limit" in str(e).lower() else 500, detail=str(e)
        )


@router.post("/v1/generate")
async def internal_generate(request: InternalGenerateRequest, app_request: Request):
    try:
        ai = app_request.app.state.http_ai_client
        settings = app_request.app.state.settings
        t0 = time.perf_counter()
        text = await ai.generate(request.prompt, request.system)
        latency_ms = (time.perf_counter() - t0) * 1000
        in_t = _tok_estimate(request.prompt + (request.system or ""))
        out_t = _tok_estimate(text)
        payload = InternalGenerateResponse(
            text=text,
            latency_ms=round(latency_ms, 2),
            provider="http-ai-gateway",
            model=settings.ollama_llm_model,
            estimated_input_tokens=in_t,
            estimated_output_tokens=out_t,
            estimated_cost_usd=0.0,
        )
        return ResponseEnvelope.ok(payload.model_dump())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=429 if "rate limit" in str(e).lower() else 500, detail=str(e)
        )
