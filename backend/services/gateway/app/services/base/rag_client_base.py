from __future__ import annotations

from abc import ABC, abstractmethod

from services.rag.app.services.rag_service import RagResult


class RagClient(ABC):
    """Boundary interface for orchestrator -> RAG retrieval."""

    @abstractmethod
    async def answer(self, query: str) -> RagResult:
        ...

