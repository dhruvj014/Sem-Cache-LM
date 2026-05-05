## Demo / UX ideas (from "realistically implement" brainstorm)

1. **Index "question + answer" for vectors** — On cache `store`, embed `query + "\n" + truncated response` so retrieval matches follow-ups against factual content, not only the original prompt.

2. **Top‑3 candidates in API + collapsible UI** — Optional `debug` (or dev-only) field on query responses listing neighbor `query`, `score`, `id`; small "Retrieval" panel in the trace.

3. **"Professor script" demo** — Extend the demo sequence with on-screen step captions (toast/banner) explaining cold LLM → cache hit → validate, etc.

4. **One-click "Warm cache for demo"** — Button or `POST` that runs a few fixed queries so the first live question isn't on an empty index.

5. **Print-friendly / Save as PDF** — Reuse Markdown or render HTML and `window.print()` / print CSS for a handout-style artifact.

6. **Latency "hero" banner** — Single strip: last query latency vs rolling LLM/cache averages from existing analytics (no new backends).

### Do these improve *real* performance?

- **Yes (retrieval / hit rate):** **(1)** — richer embedding target usually **improves** semantic recall and follow-up hits; can slightly **hurt** pure "same question" dupes if weights change, but generally nets better **useful** reuse.
- **No (mostly observability or narrative):** **(2)** through **(6)** — they help **explain**, **demo**, and **reduce awkward cold starts**; they don't change scoring or generation by themselves (except **(4)** only makes later queries *able* to hit cache sooner by pre-filling data).

---

## Performance-oriented ideas (actual latency, hit rate, or cost)

1. **Raise `CACHE_SEARCH_TOP_K` and rerank** — Retrieve more neighbors, score with a tiny reranker or a short LLM rubric on top-K only in the gray band; better precision at similar cost.

2. **Session-aware or multi-turn embedding** — Prefix the user message (or a 1-line running summary) when embedding so follow-ups stay in the same semantic neighborhood.

3. **Cache validator / LLM calls** — Memoize `(normalized_query, cache_id) → verdict` in Redis with TTL to skip repeated judge calls.

4. **Async or streaming** — Stream tokens from Ollama to TTFB; overlap embed + Qdrant round-trip where possible.

5. **Smaller / faster embed model for routing** — Dedicated small model for retrieval, larger model only for final answer (if you split pipelines).

6. **Batch embedding** — If you add batch endpoints, warm multiple queries in one Ollama call for benchmarks or bulk ingest.

7. **Qdrant tuning** — `hnsw_ef`, `exact` for small collections, or `quantization` for large local indexes; fewer points + good payload filters = faster search.

8. ~~**Redis pipelining / fewer round-trips**~~ ✅ **Implemented** — Replaced `2×top_k` sequential Redis GETs in `CacheService.search` with a single pipelined `MGET` call (1 round-trip instead of 24 for default `top_k=12`).

9. ~~**Quality + popularity weighted reranking**~~ ✅ **Implemented** — Reranking now blends dense cosine, lexical overlap, validated quality score, and log-scaled hit count: `combined = w_base·(dense+lex) + w_qual·quality + w_pop·pop`. Tunable via `CACHE_RERANK_QUALITY_WEIGHT`, `CACHE_RERANK_POPULARITY_WEIGHT`, `CACHE_RERANK_POPULARITY_CAP`.

10. **Stricter eviction + max collection size** — Cap vectors and evict LRU or lowest-quality so search stays fast as the demo runs on.
