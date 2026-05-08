"""FastAPI dependency providers."""

from fastapi import Request

from services.gateway.app.services.feedback_service import FeedbackService
from services.gateway.app.clients.orchestrator import HttpOrchestratorClient
from shared.domain.analytics_ports import AnalyticsClient
from shared.domain.cache_boundary import CacheBoundary
from shared.domain.decision_thresholds import DecisionThresholds

def get_orchestrator_boundary(request: Request) -> HttpOrchestratorClient:
    return request.app.state.orchestrator_boundary


def get_cache_boundary(request: Request) -> CacheBoundary:
    return request.app.state.cache_boundary


def get_feedback_service(request: Request) -> FeedbackService:
    return request.app.state.feedback_service


def get_analytics_service(request: Request) -> AnalyticsClient:
    return request.app.state.analytics_boundary


def get_decision_thresholds(request: Request) -> DecisionThresholds:
    return request.app.state.decision_thresholds
