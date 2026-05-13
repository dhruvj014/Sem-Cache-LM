# Quick Start — SemCacheLM (local dev)

Assumes Docker Desktop, Python 3.11+, Node 18+. Set **`GEMINI_API_KEY`** in `.env` (repo root for Compose, and/or `backend/.env` for local uvicorn).

**Important:** The gateway does **not** embed Qdrant or call Gemini directly. It talks to standalone services over HTTP (`AI_SERVICE_BASE_URL`, `CACHE_SERVICE_BASE_URL`, `RAG_SERVICE_BASE_URL`, `ANALYTICS_SERVICE_BASE_URL`, `ORCHESTRATOR_SERVICE_BASE_URL`). For queries to work you must run **AI + Cache + RAG + Analytics + Orchestrator** alongside the gateway (see run section), or point those URLs at reachable deployments.

Use **`PYTHONPATH`** so Python can import `services.*` and `shared.*`:

| Where you run uvicorn from | Set |
| -------------------------- | --- |
| Repo root | `PYTHONPATH=backend` (macOS/Linux) or `$env:PYTHONPATH="backend"` (PowerShell) |
| `backend/` directory | `PYTHONPATH=.` or rely on cwd being `backend/` (usually works) |

---

## Run All Services in Docker (recommended)

Brings up Redis + Qdrant + gateway + orchestrator + AI + cache + RAG + analytics + the frontend.

1. Set **`GEMINI_API_KEY`** in a repo-root `.env` (used by Docker Compose).

2. From the repo root:

```bash
docker compose up --build -d
```

3. Verify:

```bash
curl http://localhost:8000/api/v1/health
```

4. Open the UI: http://localhost:5173

Reset everything:

```bash
docker compose down -v
```

Manual option: follow the remaining sections below.

---

## 1 — Infrastructure (Qdrant + Redis)

```powershell
# from repo root
docker compose up -d

# verify
curl.exe http://localhost:6333/healthz           # 200 OK
docker exec semcachelm-redis redis-cli ping       # PONG
```

---

## 2 — Gemini API key

Set **`GEMINI_API_KEY`** in `backend/.env` or repo-root `.env` before bringing up Compose or running uvicorn.

---

## 3 — Backend virtualenv + `.env`

```powershell
cd backend

# first time only
python -m venv venv
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit `.env` if needed:

- **`CORS_ORIGINS`** — include `http://localhost:5173` for the UI.
- **`AI_SERVICE_BASE_URL`**, **`CACHE_SERVICE_BASE_URL`**, **`RAG_SERVICE_BASE_URL`**, **`ANALYTICS_SERVICE_BASE_URL`**, **`ORCHESTRATOR_SERVICE_BASE_URL`** — defaults match local ports `8004`, `8002`, `8001`, `8003`, `8005`.
- **`RAG_QDRANT_*`** — optional separate Qdrant collection for RAG chunks (see `.env.example`).
- **`STREAM_RECLAIM_MIN_IDLE_MS`** — XAUTOCLAIM recovery for stale pending stream messages (`0` disables).
- **`GET /api/v1/health/streams`** — XPENDING backlog per monitored stream (gateway ops).

---

## 4 — Run all backend services (recommended)

Open **six terminals** from the **repo root** (PowerShell):

```powershell
$env:PYTHONPATH="backend"

uvicorn services.gateway.app.main:app --port 8000 --reload
uvicorn services.rag.app.main:app --port 8001 --reload
uvicorn services.cache.app.main:app --port 8002 --reload
uvicorn services.analytics.app.main:app --port 8003 --reload
uvicorn services.ai.app.main:app --port 8004 --reload
uvicorn services.orchestrator.app.main:app --port 8005 --reload
```

macOS / Linux:

```bash
export PYTHONPATH=backend
uvicorn services.gateway.app.main:app --port 8000 --reload
uvicorn services.rag.app.main:app --port 8001 --reload
uvicorn services.cache.app.main:app --port 8002 --reload
uvicorn services.analytics.app.main:app --port 8003 --reload
uvicorn services.ai.app.main:app --port 8004 --reload
uvicorn services.orchestrator.app.main:app --port 8005 --reload
```

- Swagger (gateway) → http://localhost:8000/api/v1/docs  
- Health (gateway) → http://localhost:8000/api/v1/health — reports **`redis`** and **`ai_service`** reachability (not gateway-local Qdrant or the LLM provider). Stream backlog: **`GET /api/v1/health/streams`**.

**RAG index storage:** vectors go to **Qdrant** (`RAG_QDRANT_*`), one logical collection per repo (`{RAG_QDRANT_COLLECTION}__{repo}`). **Redis** keys under `RAG_REDIS_MANIFEST_PREFIX` store fingerprints so re-ingest runs when files or embedding/chunk settings change. Clones under `RAG_REPO_CACHE_DIR` stay ephemeral. Queries retrieve in parallel across corpora, merge the top chunks, then run **one** LLM synthesis pass.

---

## 5 — Frontend (separate terminal)

```powershell
cd frontend

# first time only
Copy-Item .env.example .env    # VITE_API_URL=http://localhost:8000
npm install

# every time
npm run dev
```

Open → http://localhost:5173

---

## One-liner cheat sheet (returning developer)

```powershell
# Terminal 0 — infra
docker compose up -d

# Terminals 1–5 — backend (repo root, PYTHONPATH=backend each)
$env:PYTHONPATH="backend"; uvicorn services.gateway.app.main:app --port 8000 --reload
# + rag 8001, cache 8002, analytics 8003, ai 8004

# Terminal 6 — frontend
cd frontend; npm run dev
```

---

## Smoke test (async query — default)

Requires **gateway + orchestrator + ai + cache + rag + analytics** (§4).

```powershell
curl.exe -X POST http://localhost:8000/api/v1/query `
  -H "Content-Type: application/json" `
  -d "{\"query\": \"What is a distributed system?\", \"session_id\": \"dev-01\"}"
```

The response is **202 Accepted** with `data.job_id`. Poll for completion:

```powershell
curl.exe http://localhost:8000/api/v1/query/<job_id>
```

Repeat the same JSON after completion — expect `CACHE` / validated-cache behavior when the semantic hit threshold is met.


## Reset (clean slate)

```powershell
docker compose down -v
docker compose up -d
```

This wipes Qdrant volumes and Redis data for this compose stack.

---

## Key env knobs (`backend/.env`)

| Variable | Default | Effect |
| -------- | ------- | ------ |
| `SIMILARITY_HIT_THRESHOLD` | `0.92` | Cosine score above which cache is served directly |
| `SIMILARITY_GRAY_ZONE_LOW` | `0.7` | Below this score, policy tends toward LLM / validate paths |
| `STREAM_WORKERS_ENABLED` | `true` | Cache / RAG / AI services consume command streams |
| `ANALYTICS_VIA_STREAM` | `true` | Orchestrator publishes analytics events (async path) |
| `AI_SERVICE_BASE_URL` | `http://localhost:8004` | Gateway → AI HTTP |
| `ORCHESTRATOR_SERVICE_BASE_URL` | `http://localhost:8005` | Gateway → Orchestrator HTTP |
| `CACHE_SEARCH_TOP_K` | `12` | Neighbors fetched before rerank |
| `CACHE_RERANK_*` | see `.env.example` | Lexical / quality / popularity reranking |
| `VALIDATOR_CACHE_TTL_SECONDS` | `3600` | Redis TTL for memoised validator verdicts (`0` = off) |
| `QUALITY_EVICTION_THRESHOLD` | `0.3` | Quality below this evicts on `POST /api/v1/cache/evict` |

Full list → **`backend/.env.example`**.
