from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.rag.app.api.rag_internal import router
from services.rag.app.services.rag_service import RagCitation, RagResult


class _FakeRag:
    async def answer(self, query: str) -> RagResult:
        return RagResult(
            response=f"answer:{query}",
            citations=[
                RagCitation(
                    file_path="repo:backend/app/services/query_router.py",
                    score=0.88,
                    snippet="class QueryRouterService: ...",
                )
            ],
        )


def test_rag_internal_retrieve_returns_answer_and_citations():
    app = FastAPI()
    app.include_router(router, prefix="/internal")
    app.state.rag_service = _FakeRag()

    client = TestClient(app)
    resp = client.post(
        "/internal/v1/retrieve",
        json={"query": "what APIs exist?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["answer"] == "answer:what APIs exist?"
    assert len(body["data"]["citations"]) == 1
    assert body["data"]["citations"][0]["file_path"].endswith("query_router.py")
    assert body["data"]["citations"][0]["score"] == 0.88

