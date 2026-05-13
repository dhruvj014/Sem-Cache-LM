# SemCacheLM

**Quality-Aware Semantic Caching for LLMs** — CMPE 273 (Enterprise Distributed Systems), San José State University.

SemCacheLM cuts cost and latency by semantically reusing prior answers and choosing when to trust them. It implements the three required advanced features:

1. **Agentic decision layer** — `CACHE_HIT`, `VALIDATE`, or `LLM_FALLBACK` per query.  
2. **Feedback loop** — up/down votes adjust per-entry quality (EMA); low-quality rows can be evicted.  
3. **False-hit detection** — gray-zone similarity runs a lightweight LLM judge before reuse.

## Architecture

```
React (Vite + Tailwind) ── HTTP ──▶ Gateway (FastAPI) ──▶ Cache / RAG / AI / Analytics (HTTP)
                                                   └──▶ Redis Streams + Orchestrator worker
```

- **Backend:** FastAPI · Pydantic v2 · structlog · httpx · qdrant-client · redis-py  
- **Data:** Qdrant (vectors), Redis (metadata, streams, analytics projector input)  
- **LLM / embeddings:** Google **Gemini** (defaults in `backend/.env.example`)  
- **Frontend:** React 18 · Vite · Tailwind · Recharts · TanStack Query  

Cross-service calls use HTTP and stream contracts; shared code lives under `backend/shared/`.

## Documentation

| Doc | Use when you need… |
| --- | ------------------ |
| [docs/architecture.md](docs/architecture.md) | Service roles, async query flow, where to read code first |
| [docs/testing.md](docs/testing.md) | Pytest, curl/PowerShell scenarios, UI checklist, troubleshooting |
| [docs/operations.md](docs/operations.md) | Grafana/Prometheus, **AWS `VITE_API_URL` + CORS**, embedding cutover |
| [docs/roadmap.md](docs/roadmap.md) | Stretch goals / enterprise direction |

## Prerequisites

- Docker (Desktop or Engine)  
- **Python 3.11+** and **Node 18+** if you run services or the UI outside Docker  
- **`GEMINI_API_KEY`** in repo-root `.env` (Compose) and/or `backend/.env` (local uvicorn) — see [`.env.example`](.env.example) and [`backend/.env.example`](backend/.env.example)

On Windows PowerShell, prefer **`curl.exe`** for HTTP examples so you do not hit the `Invoke-WebRequest` alias.

---

## Run the full stack (recommended)

From the **repository root**:

```bash
cp .env.example .env   # then set GEMINI_API_KEY
docker compose up --build -d
```

Checks:

```bash
curl http://localhost:8000/api/v1/health
```

- **UI:** http://localhost:5173  
- **API docs:** http://localhost:8000/api/v1/docs  

Reset volumes (wipes Qdrant + Redis data for this compose project):

```bash
docker compose down -v
```

---

## Tests (no live Gemini required)

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
pytest tests/ -v
```

Manual API flows, PowerShell quoting, and UI verification: **[docs/testing.md](docs/testing.md)**.

---

## Run backends without Docker (optional)

Bring up **Redis + Qdrant** with Compose (`docker compose up -d`), then from repo root with `PYTHONPATH=backend`:

```bash
uvicorn services.gateway.app.main:app --port 8000 --reload
uvicorn services.rag.app.main:app --port 8001 --reload
uvicorn services.cache.app.main:app --port 8002 --reload
uvicorn services.analytics.app.main:app --port 8003 --reload
uvicorn services.ai.app.main:app --port 8004 --reload
uvicorn services.orchestrator.app.main:app --port 8005 --reload
```

Frontend: `cd frontend && cp .env.example .env && npm install && npm run dev` — set `VITE_API_URL=http://localhost:8000` for this layout. Ensure `CORS_ORIGINS` in `backend/.env` includes `http://localhost:5173`.

---

## Observability

Grafana and Prometheus start with the default Compose file. URLs, login, and troubleshooting: **[docs/operations.md](docs/operations.md)**.  
Grafana dashboard: `http://localhost:3000/d/semcachelm-main/semcachelm-observability` (after login `admin` / `admin123`).

---

## API (gateway)

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/api/v1/query` | Submit query (default **202** + `job_id`, async pipeline) |
| GET | `/api/v1/query/{job_id}` | Poll job status / result |
| POST | `/api/v1/feedback/{cache_id}` | `up` / `down` feedback |
| GET | `/api/v1/cache/entries` | Paginated cache listing |
| DELETE | `/api/v1/cache/{cache_id}` | Delete one entry |
| POST | `/api/v1/cache/evict` | Evict by quality threshold |
| GET | `/api/v1/analytics/summary` | Aggregate stats |
| GET | `/api/v1/analytics/history` | Recent query log |
| GET | `/api/v1/health` | Redis + dependency services |

Envelope: `{ "success", "data", "error", "timestamp" }`.

---

## Decision thresholds (env)

| Variable | Default | Role |
| -------- | ------- | ---- |
| `SIMILARITY_HIT_THRESHOLD` | `0.92` | At/above → direct cache serve |
| `SIMILARITY_GRAY_ZONE_LOW` | `0.7` | Below → tend toward LLM / validate |
| `QUALITY_EMA_ALPHA` | `0.20` | Feedback EMA learning rate |
| `QUALITY_EVICTION_THRESHOLD` | `0.30` | Evict at or below on demand |

More knobs: `backend/.env.example` (rerank weights, stream reclaim, RAG/Qdrant split, service URLs).

---

## Frontend highlights

Decision trace per reply, query-flow animation, system monitor + latency bars, demo sequence, cache explorer, analytics page, command palette (**⌘/Ctrl+K**), session export to Markdown.

---

## AWS

Use **`docker-compose.aws.yml`**. All configuration is env-driven; per-service Dockerfiles live under `backend/services/*/Dockerfile`.  

**Critical:** rebuild the frontend image whenever you change **`VITE_API_URL`** — it is compile-time in Vite. Set **`CORS_ORIGINS`** to your real UI origin. Details: **[docs/operations.md](docs/operations.md)**.

---

## Project layout

```
├── backend/
│   ├── services/     gateway, cache, rag, analytics, ai, orchestrator
│   ├── shared/       models, contracts, infra, observability
│   └── tests/        unit + integration
├── docs/             architecture, testing, operations, roadmap
├── frontend/         React + Vite
├── grafana/          datasource + dashboard provisioning
└── prometheus/       scrape config
```

---

## Migration note

The old `backend/app` monolith is removed. Run and import **`services.<name>.app.main`**, not `app.main`. Tests and scripts should use `services.*` and `shared.*` paths with `PYTHONPATH=backend` when running from the repo root.

---

## RAG Cache Invalidation

When RAG source material changes, vectors and cached answers that depended on that material can become stale. **RAG cache invalidation** lets you remove matching semantic-cache rows in Qdrant and matching RAG chunk points in Qdrant through a single gateway call, so clients are not served outdated answers tied to old chunks or paths.

### API endpoint

**`POST /api/v1/cache/invalidate`** (gateway; public, no auth header required)

Send **exactly one** of the following in the JSON body:

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `chunk_id` | string | Match cache entry id, or payload fields such as `chunk_id` / `rag_chunk_ids` / `rag_chunk_id`, or use as RAG Qdrant point id when propagating to the RAG service. |
| `source_identifier` | string | Match cache payload `rag_citations` paths (as stored when answers were cached from RAG), and match RAG Qdrant payloads (e.g. `file_path`, `filename`, `id`). |

**Success envelope** (`data` object; same outer envelope as other gateway APIs: `success`, `data`, `error`, `timestamp`):

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `cache_invalidated_count` | int | Number of semantic-cache entries deleted from the cache Qdrant collection. |
| `invalidated_cache_ids` | array of string | Qdrant point ids (cache entry ids) that were removed. |
| `rag_deleted_chunk_points` | int | Number of RAG chunk points deleted across RAG Qdrant collections. |
| `rag_collections_touched` | array of string | RAG collection names that were scanned for deletions. |
| `rag_confirmation` | string | Short status, e.g. `rag_chunks_deleted` or `no_matching_rag_points`. |

**Example — invalidate by source path** (matches `rag_citations` and RAG payload paths):

```bash
curl -sS -X POST http://localhost:8000/api/v1/cache/invalidate \
  -H "Content-Type: application/json" \
  -d '{"source_identifier":"myrepo:README.md"}'
```

**Example — invalidate by chunk / point id**:

```bash
curl -sS -X POST http://localhost:8000/api/v1/cache/invalidate \
  -H "Content-Type: application/json" \
  -d '{"chunk_id":"550e8400-e29b-41d4-a716-446655440000"}'
```

On Windows PowerShell, use **`curl.exe`** if `curl` is aliased to `Invoke-WebRequest`.

### How it works across services

1. **Gateway** receives `POST /api/v1/cache/invalidate`, validates the body, then calls the cache and RAG microservices over HTTP (with `INTERNAL_SERVICE_TOKEN` when configured).  
2. **Cache service** scans the semantic-cache Qdrant collection, finds entries linked to the given `chunk_id` or `source_identifier`, deletes them, and increments the **`semcachelm_invalidations_total`** Prometheus counter by the number of entries removed.  
3. **RAG service** scans RAG Qdrant collections (per-repo prefix), deletes chunk points whose id or payload matches the identifier passed through from the gateway.  
4. **Redis Streams** — after both calls succeed, the gateway appends an **`AnalyticsEventV1`** payload to the analytics events stream so the invalidation is visible in the analytics pipeline.  
5. The gateway returns the combined counts and ids in the response `data` object above.

### Prometheus metric

- **`semcachelm_invalidations_total`** — counter incremented on the **cache** service each time cache entries are actually deleted by invalidation (by the number of deleted entries). Scraped from the cache service metrics endpoint (e.g. `http://localhost:8002/metrics` when the cache port is published).

### Frontend

Open the **Cache Explorer** tab in the UI. In the **RAG-linked invalidation** panel, choose **Source identifier** or **Chunk ID**, enter the value, and click **Invalidate**. A success message shows how many cache entries were removed and how many RAG points were deleted; errors surface in the same panel.

### When to use it

- **Source documents changed** — e.g. README or docs were updated and old cached answers should not be served.  
- **Codebase changed** — RAG re-ingestion or chunk drift makes old chunk vectors or citations obsolete.  
- **Cached answers need a refresh** — you want to drop entries tied to a specific path or id before new queries repopulate the cache.
