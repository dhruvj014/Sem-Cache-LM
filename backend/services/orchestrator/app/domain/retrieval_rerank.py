"""Lightweight reranking: blend dense similarity, lexical overlap, quality, and popularity."""

import math
import re
from typing import List

from shared.models.schemas import CacheHit

_TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)


def lexical_overlap_ratio(user_query: str, document: str) -> float:
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
    quality_weight: float = 0.08,
    popularity_weight: float = 0.04,
    popularity_cap: float = 50.0,
    max_response_chars: int = 2500,
) -> List[CacheHit]:
    if not hits:
        return []

    w_lex = max(0.0, min(1.0, lexical_weight))
    w_qual = max(0.0, min(0.3, quality_weight))
    w_pop = max(0.0, min(0.2, popularity_weight))
    if w_qual + w_pop > 0.5:
        scale = 0.5 / (w_qual + w_pop)
        w_qual *= scale
        w_pop *= scale
    w_base = 1.0 - w_qual - w_pop

    log_cap = math.log1p(max(1.0, popularity_cap))

    rescored: List[CacheHit] = []
    for h in hits:
        doc = f"{h.query}\n{(h.response or '')[:max_response_chars]}"
        lex = lexical_overlap_ratio(user_query, doc)
        base = (1.0 - w_lex) * float(h.score) + w_lex * lex
        qual = max(0.0, min(1.0, float(h.quality_score)))
        pop = math.log1p(max(0, int(h.hit_count))) / log_cap
        pop = min(1.0, pop)
        combined = w_base * base + w_qual * qual + w_pop * pop
        rescored.append(h.model_copy(update={"score": combined}))

    rescored.sort(key=lambda x: -x.score)
    return rescored
