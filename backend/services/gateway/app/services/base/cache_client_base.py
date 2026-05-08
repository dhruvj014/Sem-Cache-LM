from __future__ import annotations

from abc import ABC, abstractmethod

from shared.models.schemas import CacheEntry, CacheHit, EvictionResult


class CacheClient(ABC):
    """Boundary interface for orchestrator -> semantic cache operations."""

    @abstractmethod
    async def search(self, embedding: list[float], top_k: int = 5) -> list[CacheHit]:
        ...

    @abstractmethod
    async def store(
        self,
        query: str,
        embedding: list[float],
        response: str,
        metadata: dict,
    ) -> str:
        ...

    @abstractmethod
    async def increment_hit(self, cache_id: str) -> None:
        ...

    @abstractmethod
    async def promote(self, cache_id: str, new_quality: float) -> None:
        ...

    @abstractmethod
    async def demote(self, cache_id: str, new_quality: float) -> None:
        ...

    @abstractmethod
    async def get(self, cache_id: str) -> CacheEntry | None:
        ...

    @abstractmethod
    async def list_entries(self, page: int, page_size: int) -> tuple[list[CacheEntry], int]:
        ...

    @abstractmethod
    async def delete(self, cache_id: str) -> None:
        ...

    @abstractmethod
    async def clear_all(self) -> int:
        ...

    @abstractmethod
    async def evict_low_quality(self, threshold: float) -> EvictionResult:
        ...

