from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Abstract LLM client. Concrete implementations: Ollama, OpenAI, etc."""

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...
