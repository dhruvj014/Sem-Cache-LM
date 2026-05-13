# Post-deploy cutover: semantic cache + RAG (Gemini embeddings)

After switching to **`gemini-embedding-001`** with **`outputDimensionality` aligned to `QDRANT_VECTOR_SIZE` / `RAG_QDRANT_VECTOR_SIZE` (768), treat **full recache** and **full RAG reindex** as required for each environment.

## Why

Old vectors from **`text-embedding-004`**, other embedding APIs, or any other embedding model live in a **different embedding space** than **`gemini-embedding-001`**. Queries embedded with Gemini must not be searched against stale points.

## Checklist (per environment)

1. **Semantic cache (cache service / Qdrant cache collection)**  
   Clear points in the cache **Qdrant collection** (use your admin/eviction/clear paths). Optionally reconcile Redis keys under prefixes such as **`semcache:quality:*`** (flush vs tolerate orphans—pick one approach and document it).

2. **RAG**  
   Invalidate Redis entries under **`RAG_REDIS_MANIFEST_PREFIX`** (`semcache:rag:index:v1` by default) and/or **drop** Qdrant collections matching `semcachelm_rag_chunks__*` (or your `RAG_QDRANT_COLLECTION` prefix) so RAG **`initialize()`** rebuilds indexes from configured repos with Gemini embeddings.

3. **Timing**  
   Prefer a short maintenance window or an empty-vector-store window before live traffic. Otherwise expect a **cold cache** until traffic repopulates entries.

4. **Verify**  
   Confirm an embed path reports **`vector_size`** **768** (or your configured size) and run one end-to-end query after cutover.
