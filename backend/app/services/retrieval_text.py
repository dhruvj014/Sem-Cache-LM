"""Text helpers for retrieval: composite index text and session-aware search text."""

def build_index_text_for_vector(
    query: str, response: str, max_response_chars: int = 1200
) -> str:
    """Text embedded when *writing* to Qdrant so neighbors encode answer facts."""
    q = (query or "").strip()
    r = (response or "").strip()
    if max_response_chars > 0 and len(r) > max_response_chars:
        r = r[:max_response_chars] + "…"
    if not r:
        return q
    return f"{q}\n\n{r}"


def build_search_text_for_vector(
    session_last_query: str | None,
    session_last_snippet: str | None,
    query: str,
    max_snippet_chars: int = 450,
) -> str:
    """Text embedded when *searching*: optional prior turn grounds follow-ups."""
    q = (query or "").strip()
    lq = (session_last_query or "").strip()
    sn = (session_last_snippet or "").strip()
    if max_snippet_chars > 0 and len(sn) > max_snippet_chars:
        sn = sn[:max_snippet_chars] + "…"
    if not lq and not sn:
        return q
    return (
        f"Previous user question: {lq}\n"
        f"Previous assistant answer (excerpt): {sn}\n\n"
        f"Current user question: {q}"
    )
