"""Public API: read/update runtime threshold configuration (gateway-local)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from services.gateway.app.dependencies import get_decision_thresholds
from shared.contracts.threshold import ThresholdConfigData, ThresholdConfigUpdate
from shared.domain.decision_thresholds import DecisionThresholds
from shared.models.schemas import ResponseEnvelope

router = APIRouter()


def _runtime_quality(request: Request) -> dict[str, float]:
    rq = getattr(request.app.state, "runtime_quality", None)
    if not isinstance(rq, dict):
        return {}
    return dict(rq)


@router.get("/config/thresholds", response_model=ResponseEnvelope[ThresholdConfigData])
async def get_thresholds(
    request: Request,
    thresholds: DecisionThresholds = Depends(get_decision_thresholds),
):
    d = thresholds.as_dict()
    st = request.app.state.settings
    rq = _runtime_quality(request)
    alpha = float(rq.get("quality_ema_alpha", st.quality_ema_alpha))
    evict = float(rq.get("quality_eviction_threshold", st.quality_eviction_threshold))
    return ResponseEnvelope.ok(
        ThresholdConfigData(
            similarity_hit_threshold=float(d["similarity_hit_threshold"]),
            similarity_gray_zone_low=float(d["similarity_gray_zone_low"]),
            quality_ema_alpha=alpha,
            quality_eviction_threshold=evict,
        )
    )


@router.post("/config/thresholds", response_model=ResponseEnvelope[ThresholdConfigData])
async def post_thresholds(
    body: ThresholdConfigUpdate,
    request: Request,
    thresholds: DecisionThresholds = Depends(get_decision_thresholds),
):
    st = request.app.state.settings
    rq = dict(_runtime_quality(request))
    if not rq:
        rq = {
            "quality_ema_alpha": float(st.quality_ema_alpha),
            "quality_eviction_threshold": float(st.quality_eviction_threshold),
        }
    d = thresholds.as_dict()
    hit = (
        float(body.similarity_hit_threshold)
        if body.similarity_hit_threshold is not None
        else float(d["similarity_hit_threshold"])
    )
    gray = (
        float(body.similarity_gray_zone_low)
        if body.similarity_gray_zone_low is not None
        else float(d["similarity_gray_zone_low"])
    )
    if body.similarity_hit_threshold is not None or body.similarity_gray_zone_low is not None:
        try:
            thresholds.update(hit, gray)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    if body.quality_ema_alpha is not None:
        rq["quality_ema_alpha"] = float(body.quality_ema_alpha)
    if body.quality_eviction_threshold is not None:
        rq["quality_eviction_threshold"] = float(body.quality_eviction_threshold)
    request.app.state.runtime_quality = rq

    d2 = thresholds.as_dict()
    return ResponseEnvelope.ok(
        ThresholdConfigData(
            similarity_hit_threshold=float(d2["similarity_hit_threshold"]),
            similarity_gray_zone_low=float(d2["similarity_gray_zone_low"]),
            quality_ema_alpha=float(rq.get("quality_ema_alpha", st.quality_ema_alpha)),
            quality_eviction_threshold=float(
                rq.get("quality_eviction_threshold", st.quality_eviction_threshold)
            ),
        )
    )
