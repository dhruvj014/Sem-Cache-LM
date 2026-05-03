"""Lightweight reranking: blend dense similarity with token overlap (no extra models)."""

import re
from typing import List

from app.models.schemas import CacheHit

_TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)


def lexical_overlap_ratio(user_query: str, document: str) -> float:
    """Token recall: fraction of query tokens that appear in document (0–1)."""
    q_raw = (user_query or "").lower()
    d_raw = (document or "").lower()
    q_tokens = {t for t in _TOKEN_RE.findall(q_raw) if len(t) > 1}
    if not q_tokens:
        return 0.0
    d_tokens = set(_TOKEN_RE.findall(d_raw))
    if not d_tokens:
        return 0.0
    hits = sum(1 for t in q_tokens if t in d_tokens)
    return hits / len(q_tokens)


def rerank_hits_with_lexical_blend(
    user_query: str,
    hits: List[CacheHit],
    lexical_weight: float,
    max_response_chars: int = 2500,
) -> List[CacheHit]:
    """
    Re-score hits: (1-w)*cosine + w*lexical_overlap(query, query+response).
    Improves ranking when the dense score understates factual overlap (e.g. follow-ups).
    """
    if not hits:
        return []
    w = max(0.0, min(1.0, lexical_weight))
    rescored: List[CacheHit] = []
    for h in hits:
        doc = f"{h.query}\n{(h.response or '')[:max_response_chars]}"
        lex = lexical_overlap_ratio(user_query, doc)
        combined = (1.0 - w) * float(h.score) + w * lex
        rescored.append(h.model_copy(update={"score": combined}))
    rescored.sort(key=lambda x: -x.score)
    return rescored
