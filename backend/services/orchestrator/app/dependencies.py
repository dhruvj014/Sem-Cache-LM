from fastapi import Request

from services.orchestrator.app.query_router import QueryRouterService


def get_query_router(request: Request) -> QueryRouterService:
    return request.app.state.query_router
