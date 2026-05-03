from abc import ABC, abstractmethod
from typing import List


class EmbeddingService(ABC):
    """Abstract embedding service. Liskov-substitutable: any concrete impl
    (Ollama, OpenAI, local SBERT) must satisfy this contract identically."""

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
