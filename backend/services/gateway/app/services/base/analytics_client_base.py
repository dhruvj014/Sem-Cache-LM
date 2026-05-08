from __future__ import annotations

from abc import ABC, abstractmethod

from shared.models.enums import AgentAction, ResponseSource
from shared.models.schemas import AnalyticsSummary, HistoryResponse


class AnalyticsClient(ABC):
    @abstractmethod
    async def record_query(
        self,
        query: str,
        source: ResponseSource,
        agent_action: AgentAction,
        similarity_score: float,
        latency_ms: float,
        cache_id: str | None,
        response_text: str,
    ) -> None:
        ...

    @abstractmethod
    async def summary(self) -> AnalyticsSummary:
        ...

    @abstractmethod
    async def history(self, limit: int = 20) -> HistoryResponse:
        ...

    @abstractmethod
    async def reset(self) -> None:
        ...

