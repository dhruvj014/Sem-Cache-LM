"""RAG service FastAPI dependencies (Request.state only)."""

from __future__ import annotations

from fastapi import Request

from services.rag.app.services.api_catalog_service import ApiCatalogService
from services.rag.app.services.catalog_cache_service import CatalogCacheService
from services.rag.app.services.repo_catalog_service import RepoCatalogService


def get_repo_catalog_service(request: Request) -> RepoCatalogService:
    return request.app.state.repo_catalog_service


def get_api_catalog_service(request: Request) -> ApiCatalogService:
    return request.app.state.api_catalog_service


def get_catalog_cache_service(request: Request) -> CatalogCacheService:
    return request.app.state.catalog_cache_service
