from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RagClient(ABC):
    @abstractmethod
    async def answer(self, query: str) -> Any:
        ...
