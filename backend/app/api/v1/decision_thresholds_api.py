from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_decision_thresholds
from app.models.schemas import (
    DecisionThresholdsData,
    DecisionThresholdsUpdate,
    ResponseEnvelope,
)
from app.services.decision_thresholds import DecisionThresholds

router = APIRouter()


@router.get(
    "/config/decision-thresholds",
    response_model=ResponseEnvelope[DecisionThresholdsData],
)
async def get_decision_thresholds_endpoint(
    thresholds: DecisionThresholds = Depends(get_decision_thresholds),
):
    return ResponseEnvelope.ok(DecisionThresholdsData(**thresholds.as_dict()))


@router.put(
    "/config/decision-thresholds",
    response_model=ResponseEnvelope[DecisionThresholdsData],
)
async def put_decision_thresholds(
    body: DecisionThresholdsUpdate,
    thresholds: DecisionThresholds = Depends(get_decision_thresholds),
):
    try:
        thresholds.update(
            body.similarity_hit_threshold, body.similarity_gray_zone_low
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ResponseEnvelope.ok(DecisionThresholdsData(**thresholds.as_dict()))
