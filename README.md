# SemCacheLM

A production-grade, **Quality-Aware Semantic Caching System for LLMs**, built for
CMPE 273 (Enterprise Distributed Systems) at San José State University.

SemCacheLM reduces LLM inference cost and latency by semantically caching prior
responses and intelligently deciding when to reuse them. It implements all three
required advanced features:

1. **Agentic Decision Layer** — dynamically chooses CACHE_HIT, VALIDATE, or LLM_FALLBACK.
2. **Feedback Loop Learning** — upvote/downvote signals adjust cached entry quality
   via an exponential moving average; low-quality entries are evicted.
3. **False Hit Detection** — borderline (gray-zone) matches are validated by a
   lightweight LLM judge before reuse.

## Architecture

```
React (Vite + Tailwind) ── HTTP ──▶ Gateway (FastAPI) ──▶ Cache/RAG/AI/Analytics services
                                                   └────▶ Redis Streams orchestration
```

- **Backend:** FastAPI · Pydantic v2 · structlog · httpx (async) · qdrant-client · redis-py
- **Vector DB:** Qdrant (Docker)
- **Metadata / quality scores / analytics:** Redis (Docker)
- **LLM + embeddings:** local Ollama (`llama3.1:8b` + `nomic-embed-text`)
- **Frontend:** React 18 · Vite · Tailwind · shadcn-style UI · Recharts · TanStack Query · Framer Motion

SOLID principles are strictly enforced — services are abstract-base-driven, all
dependencies are injected, and `CacheReader` / `CacheWriter` are split for
interface segregation.

## Prerequisites

- **Docker Desktop** (Qdrant + Redis)
- **Python 3.11+** (`python --version`)
- **Node.js 18+** (`node --version`)
- **[Ollama](https://ollama.com)** installed and running on the host (default URL `http://localhost:11434`)

On Windows PowerShell, use **`curl.exe`** for HTTP checks if `curl` is bound to `Invoke-WebRequest`.

All paths below are relative to the **repository root** (folder containing `docker-compose.yml`, `backend/`, and `frontend/`).

---

## Run Everything in Docker (recommended)

1. Start Ollama on your host (default URL: `http://localhost:11434`) and pull models once:

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

2. From the repo root, start the full stack (backend services + frontend + Redis + Qdrant):

```bash
docker compose up --build -d
```

3. Verify:

```bash
curl http://localhost:8000/api/v1/health
```

4. Open the UI:

- http://localhost:5173

To wipe state and rerun from scratch:

```bash
docker compose down -v
```

---

## Testing locally (step-by-step)

### 1. Start Qdrant and Redis

From the repo root:

```bash
docker compose up -d
```

If your install only has the legacy CLI, use `docker-compose up -d`.

Wait until containers are healthy, then verify:

```bash
curl http://localhost:6333/healthz          # expect HTTP 200
docker exec semcachelm-redis redis-cli ping  # expect PONG
```

If `docker exec` fails, run `docker ps` and use the Redis container name from your compose file.

### 2. Ollama: models and health

Start the Ollama app or daemon on your OS so it listens on **port 11434**.

Pull models once per machine:

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

Confirm both appear:

```bash
curl http://localhost:11434/api/tags
```

Expect HTTP **200** and JSON listing those model names.

### 3. Backend: virtualenv and dependencies

```bash
cd backend
python -m venv venv
```

Activate the venv:

| Shell | Command |
| ----- | ------- |
| Windows (cmd) | `venv\Scripts\activate.bat` |
| Windows (PowerShell) | `venv\Scripts\Activate.ps1` |
| macOS / Linux | `source venv/bin/activate` |

Install dependencies. Use **`requirements-dev.txt`** so you get runtime packages **and** pytest:

```bash
pip install -r requirements-dev.txt
```

(`requirements.txt` alone is enough only to run the API; it does not install pytest.)

### 4. Backend configuration

Create `backend/.env` from the example:

| OS | Command |
| -- | ------- |
| Windows (cmd) | `copy .env.example .env` |
| Windows (PowerShell) | `Copy-Item .env.example .env` |
| macOS / Linux | `cp .env.example .env` |

Edit values only if your ports or Ollama URL differ. For the UI, ensure `CORS_ORIGINS` includes `http://localhost:5173`.

**Optional — clean slate for repeatable manual demos** (wipes vectors + Redis data for this project):

```bash
cd ..
docker compose down -v
docker compose up -d
```

Re-check Section 1, then continue.

### 5. Automated tests

With the venv **activated** and cwd **`backend/`**:

```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
```

Or one shot:

```bash
pytest tests/ -v
```

These tests use fakes and **do not** require Docker or Ollama. Expect all tests to pass on a healthy tree.

### 6. Run the API (manual option)

Still in **`backend/`** with venv active:
### 6.1 Run all backend services (microservice mode)

From repo root:

```bash
uvicorn services.gateway.app.main:app --port 8000 --reload
uvicorn services.rag.app.main:app --port 8001 --reload
uvicorn services.cache.app.main:app --port 8002 --reload
uvicorn services.analytics.app.main:app --port 8003 --reload
uvicorn services.ai.app.main:app --port 8004 --reload
uvicorn services.orchestrator.app.main:app --port 8005 --reload
```

Smoke checks:

- **Swagger:** [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **Health:** `curl http://localhost:8000/api/v1/health` — JSON reports gateway dependencies (`redis`, `ai_service`, `cache_service`, `rag_service`, `analytics_service`, `orchestrator_service`); if any are down, status may be **degraded**.

### 7. Manual API checks (optional)

Responses use a wrapper: `success`, `data`, `error`, `timestamp`. Use `session_id` (any non-empty string) on `POST /api/v1/query` for session-aware search.

**PowerShell example** (default async query submit):

```powershell
curl.exe -X POST http://localhost:8000/api/v1/query `
  -H "Content-Type: application/json" `
  -d '{"query": "What is a distributed system?", "session_id": "test-001"}'
```

Then poll status/result:

```powershell
curl.exe http://localhost:8000/api/v1/query/<job_id>
```

For full curl scenarios (feedback, eviction, analytics), **PowerShell vs cmd quoting**, and numeric expectations on `data.*`, see **[TESTING.md](./TESTING.md)** (sections on manual API and troubleshooting).

### 8. Frontend

Open a **second terminal**, repo root → **`frontend/`**:

| OS | Create `.env` from example |
| -- | -------------------------- |
| Windows (cmd) | `copy .env.example .env` |
| Windows (PowerShell) | `Copy-Item .env.example .env` |
| macOS / Linux | `cp .env.example .env` |

Ensure `VITE_API_URL` is `http://localhost:8000` for local testing.

```bash
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) while the API from Section 6 is still running.

**Quick UI sanity check:** submit a query, confirm the decision trace / source badge; run the in-app demo sequence if present; if the browser reports CORS errors, fix `CORS_ORIGINS` in `backend/.env`.

---

## Observability (Prometheus + Grafana)

Prometheus and Grafana start automatically when you run
`docker compose up --build -d` — no extra setup needed.

### URLs

| Service    | URL                                                                 | Login         |
|------------|---------------------------------------------------------------------|---------------|
| Grafana    | http://localhost:3000                                               | admin / admin123 |
| Prometheus | http://localhost:9090                                               | —             |
| Dashboard  | http://localhost:3000/d/semcachelm-main/semcachelm-observability   | auto-loads    |

### Grafana dashboard — 8 panels

| Panel | What it shows |
|-------|--------------|
| 1 — Cache Decision Breakdown | Rate of CACHE_HIT / VALIDATE / LLM_FALLBACK over time |
| 2 — Cache Hit Rate % | Live gauge of cache efficiency |
| 3 — LLM Latency p50/p99 | Ollama inference vs embedding vs judge latency |
| 4 — Similarity Score Distribution | Heatmap of cosine similarity scores |
| 5 — Cache Size + Evictions | Qdrant entry count + eviction rate |
| 6 — Redis Stream Lag | Async queue backlog |
| 7 — HTTP Request Rate | Requests/sec per microservice |
| 8 — HTTP p99 Latency | Slowest 1% of requests per service |

Panels are empty until queries are sent through the app UI.
Use the app normally — graphs update automatically every 10 seconds.

### Key metrics tracked

| Metric | What it measures |
|--------|-----------------|
| `semcachelm_cache_hits_total` | Queries served directly from cache |
| `semcachelm_llm_fallback_total` | Queries that called Ollama for inference |
| `semcachelm_validate_hits_total` | Gray-zone queries approved by LLM judge |
| `semcachelm_validate_misses_total` | Gray-zone queries rejected by LLM judge |
| `semcachelm_llm_latency_seconds` | Ollama call latency (embed / infer / judge) |
| `semcachelm_similarity_score` | Cosine similarity score distribution |
| `semcachelm_quality_score_observed` | EMA quality score at feedback time |
| `semcachelm_cache_size_total` | Current entries in Qdrant |
| `semcachelm_evictions_total` | Low-quality entries removed |
| `semcachelm_redis_stream_pending` | Unacknowledged async queue messages |

### Fault Tolerance

| Failure scenario | System behavior |
|-----------------|-----------------|
| Ollama slow or down | Cache hits still served in ~18ms — no LLM needed |
| One microservice crashes | Other 5 services keep running independently |
| Container crashes | Docker restarts it automatically (`restart: unless-stopped`) |
| Redis restarts | Data persists via `redis_data` volume |
| Qdrant restarts | Vector data persists via `qdrant_data` volume |
| Gray-zone similarity (0.70–0.92) | LLM judge validates before serving — prevents false hits |

### Troubleshooting observability

| Problem | Fix |
|---------|-----|
| Grafana login fails | Use `admin` / `admin123` (Grafana 10 rejects default `admin/admin`) |
| Grafana panels show No Data | Send queries through the app UI first to generate metrics |
| Prometheus targets show DOWN | Run `docker compose ps` — backend services may still be starting |
| Port 3000 or 9090 in use | `lsof -i :3000` then kill the conflicting process |

## Quick reference (experienced setup)

```bash
# Docker (full stack)
ollama pull llama3.1:8b && ollama pull nomic-embed-text
docker compose up --build -d
# UI: http://localhost:5173
# Grafana:    http://localhost:3000   (admin / admin123)
# Prometheus: http://localhost:9090

# Manual (microservice mode)
cd backend && python -m venv venv && . venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt && cp .env.example .env
PYTHONPATH=backend uvicorn services.gateway.app.main:app --reload --port 8000
PYTHONPATH=backend uvicorn services.rag.app.main:app --reload --port 8001
PYTHONPATH=backend uvicorn services.cache.app.main:app --reload --port 8002
PYTHONPATH=backend uvicorn services.analytics.app.main:app --reload --port 8003
PYTHONPATH=backend uvicorn services.ai.app.main:app --reload --port 8004
PYTHONPATH=backend uvicorn services.orchestrator.app.main:app --reload --port 8005
# Frontend (other terminal)
cd frontend && cp .env.example .env && npm install && npm run dev
```

## API Endpoints

| Method | Path                          | Purpose                                |
| ------ | ----------------------------- | -------------------------------------- |
| POST   | `/api/v1/query`               | Submit a query (default async: `202` + `job_id`) |
| GET    | `/api/v1/query/{job_id}`      | Poll async query status/result         |
| POST   | `/api/v1/feedback/{cache_id}` | Submit `up` / `down` feedback          |
| GET    | `/api/v1/cache/entries`       | List cache entries (paginated)         |
| DELETE | `/api/v1/cache/{cache_id}`    | Delete a cache entry                   |
| POST   | `/api/v1/cache/evict`         | Evict low-quality entries              |
| GET    | `/api/v1/analytics/summary`   | Aggregate stats                        |
| GET    | `/api/v1/analytics/history`   | Recent query log                       |
| GET    | `/api/v1/health`              | Health check (`redis`, `ai_service`, `cache_service`, `rag_service`, `analytics_service`, `orchestrator_service`)  |

All responses use this envelope:

```json
{ "success": true, "data": ..., "error": null, "timestamp": "..." }
```

## Decision Thresholds (configurable via `.env`)

| Variable                    | Default | Meaning                                   |
| --------------------------- | ------- | ----------------------------------------- |
| `SIMILARITY_HIT_THRESHOLD`  | `0.92`  | At/above this, serve from cache directly  |
| `SIMILARITY_GRAY_ZONE_LOW`  | `0.7`   | Below this, fall back to the LLM          |
| `QUALITY_EMA_ALPHA`         | `0.20`  | Feedback EMA learning rate                |
| `QUALITY_EVICTION_THRESHOLD`| `0.30`  | Quality below this → evict on demand      |

Quality EMA: `new = (1 − α)·old + α·feedback_value` where upvote = 1.0, downvote = 0.0.

## Frontend Highlights

- **Decision Trace Card** under every assistant response.
- **Query Flow Visualizer** that animates Embed → Search → Agent → (Validate?) → Result.
- **Live System Monitor** sidebar (cache size, hit rate, last decision, service health).
- **Live Latency Comparison Bar** (cache avg vs. LLM avg).
- **🎬 Demo Sequence** button that fires 5 pre-written queries to showcase every badge type.
- **Cache Explorer** with quality bars, PROMOTED / DEMOTED / LOW QUALITY badges, and on-demand eviction.
- **Analytics Dashboard** with 4 charts + savings counter + recent query log.

## AWS Deployment Notes

The system is AWS-ready out of the box:

- All configuration is read from environment variables (no hardcoded values).
- Service images use per-service Dockerfiles under `backend/services/*/Dockerfile` (for example `backend/services/gateway/Dockerfile` exposes port 8000 with a gateway health check).
- `frontend/Dockerfile` builds with `VITE_API_URL` as a build arg, served by Nginx.
- `docker-compose.aws.yml` is a single-stack composition for ECS-compatible deployments.
- For managed services, swap:
  - **Qdrant** → Qdrant Cloud or a Qdrant EC2 instance (set `QDRANT_HOST` / `QDRANT_PORT`).
  - **Redis** → AWS ElastiCache (set `REDIS_HOST` / `REDIS_PORT`).
  - **Ollama** → an EC2 GPU instance or any private Ollama-compatible endpoint
    (set `OLLAMA_BASE_URL`).
- Health endpoint: `GET /api/v1/health` returns `{ status: "ok", version, services }`,
  suitable for ALB / ECS health checks.

### Backend env vars

```
APP_ENV, APP_VERSION, LOG_LEVEL, CORS_ORIGINS,
QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION, QDRANT_VECTOR_SIZE,
REDIS_HOST, REDIS_PORT, REDIS_DB,
OLLAMA_BASE_URL, OLLAMA_LLM_MODEL, OLLAMA_EMBEDDING_MODEL, OLLAMA_TIMEOUT_SECONDS,
SIMILARITY_HIT_THRESHOLD, SIMILARITY_GRAY_ZONE_LOW,
QUALITY_EMA_ALPHA, QUALITY_EVICTION_THRESHOLD,
CACHE_SEARCH_TOP_K
```

Additional commonly tuned vars live in `backend/.env.example`, including:

- service URLs/timeouts (`AI_SERVICE_BASE_URL`, `CACHE_SERVICE_BASE_URL`, `RAG_SERVICE_BASE_URL`, `ANALYTICS_SERVICE_BASE_URL`, `ORCHESTRATOR_SERVICE_BASE_URL`)
- async pipeline flags (`STREAM_WORKERS_ENABLED`, `STREAM_RECLAIM_MIN_IDLE_MS`)
- RAG split storage (`RAG_QDRANT_*`, `RAG_REDIS_MANIFEST_PREFIX`)

### Frontend env vars

```
VITE_API_URL
```

## Project Layout

```
semcachelm/
├── backend/                FastAPI + services
│   ├── services/
│   │   ├── gateway/app/    Public API service
│   │   ├── cache/app/      Cache boundary service
│   │   ├── rag/app/        Retrieval + catalog service
│   │   ├── analytics/app/  Analytics boundary service
│   │   ├── ai/app/         AI inference service
│   │   └── orchestrator/app/ Query orchestration service
│   ├── shared/             Contracts, models, infra, observability
│   └── tests/              Unit + integration
└── frontend/               React + Vite UI
```

For more scenarios (eviction, analytics, extended troubleshooting), see **[TESTING.md](./TESTING.md)**.

## Migration Notes (Breaking Changes)

- `backend/app` was removed as part of the services/shared cutover.
- Old startup commands like `uvicorn app.main:app` are no longer valid.
- Use `services.*` module paths for runtime entrypoints and imports.
- Tests and scripts should import from `services.gateway.app.*`, `services.orchestrator.app.*`, `services.<service>.app.*`, and `shared.*`.
