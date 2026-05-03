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
React (Vite + Tailwind) ── HTTP ──▶ FastAPI ──▶ Qdrant + Redis + Ollama
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

### 6. Run the API

Still in **`backend/`** with venv active:

```bash
uvicorn app.main:app --reload --port 8000
```

Smoke checks:

- **Swagger:** [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **Health:** `curl http://localhost:8000/api/v1/health` — JSON should report Qdrant, Redis, and Ollama; if Ollama is down, health may be **degraded** — fix Section 2 before exercises that need embeddings or the LLM.

### 7. Manual API checks (optional)

Responses use a wrapper: `success`, `data`, `error`, `timestamp`. Use `session_id` (any non-empty string) on `POST /api/v1/query` for session-aware search.

**PowerShell example** (first query, cold or warm cache):

```powershell
curl.exe -X POST http://localhost:8000/api/v1/query `
  -H "Content-Type: application/json" `
  -d '{"query": "What is a distributed system?", "session_id": "test-001"}'
```

Repeat the same body to exercise a **cache hit**; try paraphrases to see **validate** / gray-zone behavior.

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

## Quick reference (experienced setup)

```bash
# Root: infra
docker compose up -d
ollama pull llama3.1:8b && ollama pull nomic-embed-text

# Backend
cd backend && python -m venv venv && . venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt && cp .env.example .env
pytest tests/ -q && uvicorn app.main:app --reload --port 8000

# Frontend (other terminal)
cd frontend && cp .env.example .env && npm install && npm run dev
```

## API Endpoints

| Method | Path                          | Purpose                                |
| ------ | ----------------------------- | -------------------------------------- |
| POST   | `/api/v1/query`               | Submit a user query                    |
| POST   | `/api/v1/feedback/{cache_id}` | Submit `up` / `down` feedback          |
| GET    | `/api/v1/cache/entries`       | List cache entries (paginated)         |
| DELETE | `/api/v1/cache/{cache_id}`    | Delete a cache entry                   |
| POST   | `/api/v1/cache/evict`         | Evict low-quality entries              |
| GET    | `/api/v1/analytics/summary`   | Aggregate stats                        |
| GET    | `/api/v1/analytics/history`   | Recent query log                       |
| GET    | `/api/v1/health`              | Health check (Qdrant + Redis + Ollama) |

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
- `backend/Dockerfile` exposes port 8000 and includes a health check.
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

### Frontend env vars

```
VITE_API_URL
```

## Project Layout

```
semcachelm/
├── backend/                FastAPI + services
│   ├── app/
│   │   ├── api/v1/         Routes
│   │   ├── services/       Business logic (SOLID)
│   │   ├── infrastructure/ Qdrant + Redis clients
│   │   ├── models/         Pydantic schemas + enums
│   │   └── utils/          Logger + timer
│   └── tests/              Unit + integration
└── frontend/               React + Vite UI
```

For more scenarios (eviction, analytics, extended troubleshooting), see **[TESTING.md](./TESTING.md)**.
