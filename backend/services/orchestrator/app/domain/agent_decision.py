from typing import List, Optional

from shared.domain.decision_thresholds import DecisionThresholds
from shared.models.enums import AgentAction
from shared.models.schemas import CacheHit, DecisionResult
from shared.observability.logger import get_logger

logger = get_logger(__name__)


class AgentDecisionLayer:
    """Strategy-driven decision layer."""

    def __init__(self, thresholds: DecisionThresholds):
        self._thresholds = thresholds

    def decide(
        self,
        hits: List[CacheHit],
        *,
        hit_threshold: Optional[float] = None,
        gray_zone_low: Optional[float] = None,
    ) -> DecisionResult:
        if not hits:
            return DecisionResult(
                action=AgentAction.LLM_FALLBACK,
                cache_id=None,
                confidence=0.0,
                reason="Empty cache or no candidate hits.",
                matched_hit=None,
            )

        top = hits[0]
        sim = top.score
        hit_threshold, gray_low = self._thresholds.resolve(
            hit_threshold, gray_zone_low
        )

        if sim >= hit_threshold:
            action = AgentAction.CACHE_HIT
            reason = (
                f"Similarity {sim:.3f} above hit threshold "
                f"({hit_threshold:.2f}). Safe reuse."
            )
        elif sim >= gray_low:
            action = AgentAction.VALIDATE
            reason = (
                f"Similarity {sim:.3f} in gray zone "
                f"[{gray_low:.2f}, {hit_threshold:.2f}). Validate before reuse."
            )
        else:
            action = AgentAction.LLM_FALLBACK
            reason = (
                f"Similarity {sim:.3f} below gray-zone floor "
                f"({gray_low:.2f}). Fall back to LLM."
            )

        if action == AgentAction.CACHE_HIT and top.quality_score < 0.4:
            action = AgentAction.VALIDATE
            reason += f" Demoted to VALIDATE due to low quality_score={top.quality_score:.2f}."

        result = DecisionResult(
            action=action,
            cache_id=top.id,
            confidence=sim,
            reason=reason,
            matched_hit=top,
        )
        logger.info(
            "agent.decision",
            action=action.value,
            cache_id=top.id,
            confidence=sim,
            reason=reason,
        )
        return result
