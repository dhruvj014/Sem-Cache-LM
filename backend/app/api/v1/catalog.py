from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import (
    get_api_catalog_service,
    get_catalog_cache_service,
    get_repo_catalog_service,
)
from app.models.schemas import ResponseEnvelope
from app.services.api_catalog_service import ApiCatalogService
from app.services.catalog_cache_service import CatalogCacheService
from app.services.repo_catalog_service import RepoCatalogService
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/catalog")


@router.get("/repos", response_model=ResponseEnvelope[dict])
async def get_repo_catalog(
    cache: CatalogCacheService = Depends(get_catalog_cache_service),
):
    data = await cache.get_cached_catalog("repo_catalog.json")
    if not data.get("content"):
        raise HTTPException(status_code=404, detail="repo catalog not found")
    return ResponseEnvelope.ok(
        {
            "name": "repo_catalog",
            "content": json.loads(data["content"]),
            "meta": json.loads(data["meta"]) if data.get("meta") else None,
        }
    )


@router.get("/apis", response_model=ResponseEnvelope[dict])
async def get_api_catalog(
    cache: CatalogCacheService = Depends(get_catalog_cache_service),
):
    data = await cache.get_cached_catalog("api_catalog.json")
    if not data.get("content"):
        raise HTTPException(status_code=404, detail="api catalog not found")
    return ResponseEnvelope.ok(
        {
            "name": "api_catalog",
            "content": json.loads(data["content"]),
            "meta": json.loads(data["meta"]) if data.get("meta") else None,
        }
    )


@router.post("/refresh", response_model=ResponseEnvelope[dict])
async def refresh_catalog(
    request: Request,
    repo_catalog: RepoCatalogService = Depends(get_repo_catalog_service),
    api_catalog: ApiCatalogService = Depends(get_api_catalog_service),
    cache: CatalogCacheService = Depends(get_catalog_cache_service),
):
    try:
        repo_artifacts = repo_catalog.generate()
        api_artifacts = api_catalog.generate(request.app)
        sync_result = await cache.sync_files(
            [
                repo_artifacts.catalog_json_path,
                repo_artifacts.catalog_md_path,
                api_artifacts.catalog_json_path,
                api_artifacts.catalog_md_path,
            ]
        )
        return ResponseEnvelope.ok(
            {
                "repo_count": repo_artifacts.payload.get("repo_count", 0),
                "api_count": api_artifacts.payload.get("api_count", 0),
                "sync": sync_result,
            }
        )
    except Exception as e:
        logger.error("catalog.refresh_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
