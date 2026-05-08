"""Cache reader/writer ports — shared by gateway and cache microservice."""

from abc import ABC, abstractmethod
from typing import List, Optional

from shared.models.schemas import CacheEntry, CacheHit, EvictionResult


class CacheReader(ABC):
    @abstractmethod
    async def search(self, embedding: List[float], top_k: int = 5) -> List[CacheHit]:
        ...

    @abstractmethod
    async def get(self, cache_id: str) -> Optional[CacheEntry]:
        ...

    @abstractmethod
    async def list_entries(
        self, page: int, page_size: int
    ) -> tuple[List[CacheEntry], int]:
        ...


class CacheWriter(ABC):
    @abstractmethod
    async def store(
        self,
        query: str,
        embedding: List[float],
        response: str,
        metadata: dict,
    ) -> str:
        ...

    @abstractmethod
    async def promote(self, cache_id: str, new_quality: float) -> None:
        ...

    @abstractmethod
    async def demote(self, cache_id: str, new_quality: float) -> None:
        ...

    @abstractmethod
    async def delete(self, cache_id: str) -> None:
        ...

    @abstractmethod
    async def increment_hit(self, cache_id: str) -> None:
        ...

    @abstractmethod
    async def evict_low_quality(self, threshold: float) -> EvictionResult:
        ...
