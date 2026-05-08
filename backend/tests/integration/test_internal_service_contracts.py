from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.gateway.app.api.v1.internal_services import router


class _FakeHttpAI:
    vector_size = 4

    async def embed(self, text: str):
        return [0.1, 0.2, 0.3, 0.4]

    async def embed_batch(self, texts: list[str]):
        return [await self.embed(t) for t in texts]

    async def generate(self, prompt: str, system: str | None = None):
        return "ok"

    async def health(self) -> bool:
        return True


def test_internal_contract_routes_accept_payloads():
    app = FastAPI()
    app.include_router(router, prefix="/internal")
    app.state.http_ai_client = _FakeHttpAI()
    app.state.settings = SimpleNamespace(ollama_llm_model="test-model")

    client = TestClient(app)
    embed = client.post("/internal/v1/embed", json={"text": "hello"})
    assert embed.status_code == 200
    assert embed.json()["data"]["vector_size"] == 4

    gen = client.post("/internal/v1/generate", json={"prompt": "hello"})
    assert gen.status_code == 200
    assert gen.json()["data"]["text"] == "ok"
