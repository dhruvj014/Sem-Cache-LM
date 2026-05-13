from __future__ import annotations

from shared.config.settings import Settings


def test_active_model_ids_use_gemini_fields() -> None:
    g = Settings(
        gemini_llm_model="gemini-2.5-flash-lite",
        gemini_embedding_model="gemini-embedding-001",
    )
    assert g.active_llm_model_id == "gemini-2.5-flash-lite"
    assert g.active_embedding_model_id == "gemini-embedding-001"


def test_llm_no_rag_system_prompt_default_covers_no_context() -> None:
    s = Settings()
    assert "without any retrieved" in s.llm_no_rag_system_prompt.lower()
    assert "general knowledge" in s.llm_no_rag_system_prompt.lower()
