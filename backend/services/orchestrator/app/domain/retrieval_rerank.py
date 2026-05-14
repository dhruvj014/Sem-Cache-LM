"""Reranking: blend RRF hybrid score with quality and popularity signals."""

import math
from typing import List

from shared.models.schemas import CacheHit


def rerank_hits_with_lexical_blend(
    hits: List[CacheHit],
    quality_weight: float = 0.08,
    popularity_weight: float = 0.04,
    popularity_cap: float = 50.0,
) -> List[CacheHit]:
    """Blend the Qdrant RRF hybrid score with quality and popularity.

    BM25 + dense fusion is handled upstream by Qdrant; hit.score is already
    the RRF-fused score so no lexical term is needed here.
    """
    if not hits:
        return []

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
        qual = max(0.0, min(1.0, float(h.quality_score)))
        pop = min(1.0, math.log1p(max(0, int(h.hit_count))) / log_cap)
        combined = w_base * float(h.score) + w_qual * qual + w_pop * pop
        rescored.append(h.model_copy(update={"score": combined}))

    rescored.sort(key=lambda x: -x.score)
    return rescored
