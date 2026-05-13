import pytest

from shared.contracts.internal import InternalEmbedRequest, InternalGenerateRequest
from services.ai.app.services.ai_inference_service import AIInferenceService


class _FakeEmbedder:
    def __init__(self):
        self.calls = 0

    async def embed(self, text: str):
        self.calls += 1
        return [0.1, 0.2, 0.3, 0.4]


class _FakeLLM:
    def __init__(self):
        self.calls = 0
        self.fail_once = False

    async def generate(self, prompt: str, system: str | None = None):
        self.calls += 1
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("transient")
        return "generated text"

    async def health(self):
        return True


class _FakeRedis:
    def __init__(self):
        self.counters = {}

    async def incr(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key, seconds):
        return True


class _FakeRedisInfra:
    def __init__(self):
        self.client = _FakeRedis()


@pytest.mark.asyncio
async def test_embed_and_generate_returns_contracts(settings):
    svc = AIInferenceService(settings, _FakeEmbedder(), _FakeLLM(), _FakeRedisInfra())
    emb = await svc.embed(InternalEmbedRequest(text="hello"))
    gen = await svc.generate(InternalGenerateRequest(prompt="question"))
    assert emb.vector_size == 4
    assert len(emb.embedding) == 4
    assert gen.text == "generated text"
    assert gen.estimated_cost_usd >= 0.0


@pytest.mark.asyncio
async def test_generate_retries_once(settings):
    llm = _FakeLLM()
    llm.fail_once = True
    svc = AIInferenceService(settings, _FakeEmbedder(), llm, _FakeRedisInfra())
    out = await svc.generate(InternalGenerateRequest(prompt="retry me"))
    assert out.text == "generated text"
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_provider_and_model_reflect_gemini_settings(settings):
    g = settings.model_copy(
        update={
            "gemini_llm_model": "custom-gemini-llm",
        }
    )
    svc = AIInferenceService(g, _FakeEmbedder(), _FakeLLM(), _FakeRedisInfra())
    emb = await svc.embed(InternalEmbedRequest(text="hello"))
    gen = await svc.generate(InternalGenerateRequest(prompt="q"))
    assert emb.provider == "gemini"
    assert gen.provider == "gemini"
    assert gen.model == "custom-gemini-llm"
