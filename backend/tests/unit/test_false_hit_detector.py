import pytest

from services.orchestrator.app.domain.false_hit_detector import FalseHitDetector


@pytest.mark.asyncio
async def test_validates_yes(settings):
    async def gen(prompt: str, system: str | None = None) -> str:
        return "VERDICT: YES\nCONFIDENCE: 0.91\nREASON: Same topic and intent."

    detector = FalseHitDetector(settings, gen)
    result = await detector.validate("new q", "cached r", 0.81)
    assert result.is_valid is True
    assert result.confidence == pytest.approx(0.91)
    assert "Same topic" in result.reason


@pytest.mark.asyncio
async def test_validates_no(settings):
    async def gen(prompt: str, system: str | None = None) -> str:
        return "VERDICT: NO\nCONFIDENCE: 0.85\nREASON: Different topic."

    detector = FalseHitDetector(settings, gen)
    result = await detector.validate("new q", "cached r", 0.81)
    assert result.is_valid is False


@pytest.mark.asyncio
async def test_handles_malformed_output(settings):
    async def gen(prompt: str, system: str | None = None) -> str:
        return "nonsense"

    detector = FalseHitDetector(settings, gen)
    result = await detector.validate("q", "r", 0.8)
    assert result.is_valid is False


@pytest.mark.asyncio
async def test_handles_llm_error(settings):
    async def gen(prompt: str, system: str | None = None) -> str:
        raise RuntimeError("boom")

    detector = FalseHitDetector(settings, gen)
    result = await detector.validate("q", "r", 0.8)
    assert result.is_valid is False
    assert "boom" in result.reason
