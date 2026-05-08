from __future__ import annotations

from typing import Any

import httpx
import structlog

from services.gateway.app.config import Settings
from shared.contracts.internal import (
    InternalCacheEvictRequest,
    InternalCacheFeedbackRequest,
    InternalCacheIncrementHitRequest,
    InternalCacheSearchRequest,
    InternalCacheStoreRequest,
)
from shared.models.schemas import CacheEntry, CacheHit, EvictionResult
from services.gateway.app.services.base.cache_client_base import CacheClient


class HttpCacheClient(CacheClient):
    """Gateway-side client for standalone cache service."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http = http_client
        self._base_url = (settings.cache_service_base_url or "").rstrip("/")

    async def search(self, embedding: list[float], top_k: int = 5) -> list[CacheHit]:
        body = await self._post(
            "/internal/v1/cache/search",
            InternalCacheSearchRequest(embedding=embedding, top_k=top_k).model_dump(),
        )
        return [CacheHit.model_validate(item) for item in body["hits"]]

    async def store(
        self,
        query: str,
        embedding: list[float],
        response: str,
        metadata: dict,
    ) -> str:
        body = await self._post(
            "/internal/v1/cache/store",
            InternalCacheStoreRequest(
                query=query,
                embedding=embedding,
                response=response,
                metadata=metadata or {},
            ).model_dump(),
        )
        return str(body["cache_id"])

    async def increment_hit(self, cache_id: str) -> None:
        await self._post(
            "/internal/v1/cache/increment_hit",
            InternalCacheIncrementHitRequest(cache_id=cache_id).model_dump(),
        )

    async def promote(self, cache_id: str, new_quality: float) -> None:
        await self._post(
            "/internal/v1/cache/feedback",
            InternalCacheFeedbackRequest(
                cache_id=cache_id, action="promote", new_quality=new_quality
            ).model_dump(),
        )

    async def demote(self, cache_id: str, new_quality: float) -> None:
        await self._post(
            "/internal/v1/cache/feedback",
            InternalCacheFeedbackRequest(
                cache_id=cache_id, action="demote", new_quality=new_quality
            ).model_dump(),
        )

    async def evict_low_quality(self, threshold: float) -> EvictionResult:
        body = await self._post(
            "/internal/v1/cache/evict",
            InternalCacheEvictRequest(threshold=threshold).model_dump(),
        )
        return EvictionResult.model_validate(body)

    async def get(self, cache_id: str) -> CacheEntry | None:
        data = await self._request("GET", f"/internal/v1/cache/{cache_id}")
        if data is None:
            return None
        return CacheEntry.model_validate(data)

    async def list_entries(self, page: int, page_size: int) -> tuple[list[CacheEntry], int]:
        data = await self._request(
            "GET",
            "/internal/v1/cache/entries",
            params={"page": page, "page_size": page_size},
        )
        entries = [CacheEntry.model_validate(e) for e in (data.get("entries") or [])]
        total = int(data.get("total", 0))
        return entries, total

    async def delete(self, cache_id: str) -> None:
        await self._request("DELETE", f"/internal/v1/cache/{cache_id}")

    async def clear_all(self) -> int:
        data = await self._post("/internal/v1/cache/clear", {})
        return int(data.get("deleted_entries", 0))

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, json=payload)

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {}
        cid = structlog.contextvars.get_contextvars().get("correlation_id")
        if cid:
            headers["x-correlation-id"] = str(cid)
        resp = await self._http.request(
            method,
            f"{self._base_url}{path}",
            json=json,
            params=params,
            headers=headers,
            timeout=self._settings.cache_service_request_timeout_seconds,
        )
        if (
            resp.status_code == 404
            and method == "GET"
            and path.startswith("/internal/v1/cache/")
            and not path.endswith("/entries")
        ):
            return None
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError("cache internal request failed")
        return data.get("data") or {}

