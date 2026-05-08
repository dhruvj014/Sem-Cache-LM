"""Abstract LLM / embedding ports shared across gateway and AI microservice."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class EmbeddingService(ABC):
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        ...

    @property
    @abstractmethod
    def vector_size(self) -> int:
        ...


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...
