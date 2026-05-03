from app.models.enums import AgentAction
from app.models.schemas import CacheHit
from app.services.agent_decision import AgentDecisionLayer
from app.services.decision_thresholds import DecisionThresholds


def _hit(score: float, quality: float = 1.0) -> CacheHit:
    return CacheHit(
        id="abc",
        query="q",
        response="r",
        score=score,
        hit_count=0,
        quality_score=quality,
    )


def test_no_hits_falls_back_to_llm(settings):
    agent = AgentDecisionLayer(DecisionThresholds(settings))
    decision = agent.decide([])
    assert decision.action == AgentAction.LLM_FALLBACK
    assert decision.cache_id is None


def test_high_similarity_is_cache_hit(settings):
    agent = AgentDecisionLayer(DecisionThresholds(settings))
    decision = agent.decide([_hit(0.95)])
    assert decision.action == AgentAction.CACHE_HIT
    assert decision.cache_id == "abc"


def test_gray_zone_triggers_validate(settings):
    agent = AgentDecisionLayer(DecisionThresholds(settings))
    decision = agent.decide([_hit(0.80)])
    assert decision.action == AgentAction.VALIDATE


def test_below_floor_falls_back(settings):
    agent = AgentDecisionLayer(DecisionThresholds(settings))
    decision = agent.decide([_hit(0.50)])
    assert decision.action == AgentAction.LLM_FALLBACK


def test_low_quality_demotes_hit_to_validate(settings):
    agent = AgentDecisionLayer(DecisionThresholds(settings))
    decision = agent.decide([_hit(0.96, quality=0.2)])
    assert decision.action == AgentAction.VALIDATE
    assert "low quality_score" in decision.reason
