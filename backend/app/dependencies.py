"""FastAPI dependency providers. All services live on app.state and are
constructed once during the lifespan event. This is the Composition Root."""

from fastapi import Request

from app.services.agent_decision import AgentDecisionLayer
from app.services.decision_thresholds import DecisionThresholds
from app.services.analytics_service import AnalyticsService
from app.services.cache_service import CacheService
from app.services.false_hit_detector import FalseHitDetector
from app.services.feedback_service import FeedbackService
from app.services.query_router import QueryRouterService


def get_query_router(request: Request) -> QueryRouterService:
    return request.app.state.query_router


def get_cache_service(request: Request) -> CacheService:
    return request.app.state.cache_service


def get_feedback_service(request: Request) -> FeedbackService:
    return request.app.state.feedback_service


def get_analytics_service(request: Request) -> AnalyticsService:
    return request.app.state.analytics_service


def get_agent(request: Request) -> AgentDecisionLayer:
    return request.app.state.agent


def get_decision_thresholds(request: Request) -> DecisionThresholds:
    return request.app.state.decision_thresholds


def get_false_hit_detector(request: Request) -> FalseHitDetector:
    return request.app.state.false_hit_detector
