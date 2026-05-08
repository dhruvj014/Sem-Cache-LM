from __future__ import annotations

from abc import ABC, abstractmethod

from shared.domain.cache_ports import CacheReader, CacheWriter


class CacheBoundary(CacheReader, CacheWriter, ABC):
    @abstractmethod
    async def clear_all(self) -> int:
        ...
