"""FastAPI dependency providers."""

from fastapi import Request

from services.gateway.app.services.agent_decision import AgentDecisionLayer
from services.rag.app.services.api_catalog_service import ApiCatalogService
from services.rag.app.services.catalog_cache_service import CatalogCacheService
from services.gateway.app.services.decision_thresholds import DecisionThresholds
from services.gateway.app.services.false_hit_detector import FalseHitDetector
from services.gateway.app.services.feedback_service import FeedbackService
from services.gateway.app.services.query_router import QueryRouterService
from services.rag.app.services.repo_catalog_service import RepoCatalogService
from services.gateway.app.services.base.analytics_client_base import AnalyticsClient
from services.gateway.app.services.base.cache_client_base import CacheClient


def get_query_router(request: Request) -> QueryRouterService:
    return request.app.state.query_router


def get_cache_boundary(request: Request) -> CacheClient:
    return request.app.state.cache_boundary


def get_feedback_service(request: Request) -> FeedbackService:
    return request.app.state.feedback_service


def get_analytics_service(request: Request) -> AnalyticsClient:
    return request.app.state.analytics_boundary


def get_agent(request: Request) -> AgentDecisionLayer:
    return request.app.state.agent


def get_decision_thresholds(request: Request) -> DecisionThresholds:
    return request.app.state.decision_thresholds


def get_false_hit_detector(request: Request) -> FalseHitDetector:
    return request.app.state.false_hit_detector


def get_repo_catalog_service(request: Request) -> RepoCatalogService:
    return request.app.state.repo_catalog_service


def get_api_catalog_service(request: Request) -> ApiCatalogService:
    return request.app.state.api_catalog_service


def get_catalog_cache_service(request: Request) -> CatalogCacheService:
    return request.app.state.catalog_cache_service
