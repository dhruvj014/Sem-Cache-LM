import pytest

from app.services.base.llm_base import LLMClient
from app.services.false_hit_detector import FalseHitDetector


class _FakeLLM(LLMClient):
    def __init__(self, response: str):
        self._response = response

    async def generate(self, prompt: str, system: str | None = None) -> str:
        return self._response

    async def health(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_validates_yes(settings):
    llm = _FakeLLM("VERDICT: YES\nCONFIDENCE: 0.91\nREASON: Same topic and intent.")
    detector = FalseHitDetector(settings, llm)
    result = await detector.validate("new q", "cached r", 0.81)
    assert result.is_valid is True
    assert result.confidence == pytest.approx(0.91)
    assert "Same topic" in result.reason


@pytest.mark.asyncio
async def test_validates_no(settings):
    llm = _FakeLLM("VERDICT: NO\nCONFIDENCE: 0.85\nREASON: Different topic.")
    detector = FalseHitDetector(settings, llm)
    result = await detector.validate("new q", "cached r", 0.81)
    assert result.is_valid is False


@pytest.mark.asyncio
async def test_handles_malformed_output(settings):
    llm = _FakeLLM("nonsense")
    detector = FalseHitDetector(settings, llm)
    result = await detector.validate("q", "r", 0.8)
    assert result.is_valid is False


@pytest.mark.asyncio
async def test_handles_llm_error(settings):
    class _BrokenLLM(LLMClient):
        async def generate(self, prompt: str, system: str | None = None) -> str:
            raise RuntimeError("boom")

        async def health(self) -> bool:
            return False

    detector = FalseHitDetector(settings, _BrokenLLM())
    result = await detector.validate("q", "r", 0.8)
    assert result.is_valid is False
    assert "boom" in result.reason
