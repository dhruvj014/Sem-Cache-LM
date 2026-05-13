from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.rag.app.services.rag_service import RagService
from shared.config.settings import Settings


def test_merge_synthesize_empty_repo_nodes_returns_empty():
    svc = RagService(Settings())
    svc._retrievers = {"only_repo": object()}
    out = svc._merge_synthesize_and_cite("what is x?", [])
    assert out.response == ""
    assert out.citations == []


def test_merge_synthesize_below_score_floor_skips_llm():
    lo = MagicMock()
    lo.score = 0.12
    lo.node.metadata = {"file_path": "a.py"}
    lo.node.get_content.return_value = "irrelevant"

    settings = Settings(rag_retrieval_score_floor=0.35)
    svc = RagService(settings)
    svc._retrievers = {"r1": object()}
    out = svc._merge_synthesize_and_cite("who won the 1969 world series?", [("r1", lo)])
    assert out.response == ""
    assert out.citations == []


@patch("llama_index.core.response_synthesizers.get_response_synthesizer")
def test_merge_synthesize_calls_llm_once_with_top_k_nodes(mock_get_synth):
    hi = MagicMock()
    hi.score = 0.95
    hi.node.metadata = {"file_path": "a.py"}
    hi.node.get_content.return_value = "alpha content"

    lo = MagicMock()
    lo.score = 0.10
    lo.node.metadata = {"file_path": "b.py"}
    lo.node.get_content.return_value = "beta content"

    mid = MagicMock()
    mid.score = 0.50
    mid.node.metadata = {"file_path": "c.py"}
    mid.node.get_content.return_value = "gamma content"

    mock_synth = MagicMock()
    mock_synth.synthesize.return_value = SimpleNamespace(response="synthesized once")
    mock_get_synth.return_value = mock_synth

    settings = Settings()
    svc = RagService(settings)
    svc._retrievers = {"r1": object(), "r2": object()}

    repo_nodes = [("r1", lo), ("r2", hi), ("r1", mid)]
    out = svc._merge_synthesize_and_cite("question?", repo_nodes)

    mock_get_synth.assert_called_once()
    call_kw = mock_get_synth.call_args.kwargs
    assert call_kw.get("response_mode").name == "SIMPLE_SUMMARIZE"
    tqt = call_kw.get("text_qa_template")
    assert tqt is not None
    assert "general knowledge" in tqt.template.lower()

    mock_synth.synthesize.assert_called_once()
    args, kwargs = mock_synth.synthesize.call_args
    assert args[0] == "question?"
    passed_nodes = args[1]
    assert len(passed_nodes) == settings.rag_top_k
    assert passed_nodes[0] is hi
    assert passed_nodes[1] is mid

    assert out.response == "synthesized once"
    assert len(out.citations) == settings.rag_top_k
    assert out.citations[0].file_path == "r2:a.py"
    assert out.citations[0].score == 0.95


def test_format_citation_path_catalog_and_repo():
    svc = RagService(Settings())
    assert svc._format_citation_path("myrepo", "src/x.py") == "myrepo:src/x.py"
    assert "catalog:repo:" in svc._format_citation_path(
        "catalog_docs", "foo/repo_catalog.json"
    )
    assert "catalog:api:" in svc._format_citation_path(
        "catalog_docs", "bar/api_catalog.md"
    )
