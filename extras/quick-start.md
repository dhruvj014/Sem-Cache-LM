# Quick Start — SemCacheLM (local dev)

Assumes Docker Desktop, Python 3.11+, Node 18+, and Ollama are already installed.

---

## 1 — Infrastructure

```powershell
# from repo root
docker compose up -d

# verify
curl.exe http://localhost:6333/healthz          # 200 OK
docker exec semcachelm-redis redis-cli ping     # PONG
```

---

## 2 — Ollama (once per machine)

```powershell
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

Make sure the Ollama app/daemon is running and listening on **port 11434**.

---

## 3 — Backend

```powershell
cd backend

# first time only
python -m venv venv
pip install -r requirements-dev.txt
Copy-Item .env.example .env    # edit only if your ports differ

# every time
venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

- Swagger UI → http://localhost:8000/api/v1/docs
- Health check → http://localhost:8000/api/v1/health

---

## 4 — Frontend (separate terminal)

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

## One-liner (returning developer)

```powershell
# Terminal 1 — infra + backend
docker compose up -d
cd backend; venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend; npm run dev
```

---

## Smoke test

```powershell
# cold query (LLM fallback, stores to cache)
curl.exe -X POST http://localhost:8000/api/v1/query `
  -H "Content-Type: application/json" `
  -d '{"query": "What is a distributed system?", "session_id": "dev-01"}'

# repeat — should return source: "CACHE" with sub-5 ms latency
curl.exe -X POST http://localhost:8000/api/v1/query `
  -H "Content-Type: application/json" `
  -d '{"query": "What is a distributed system?", "session_id": "dev-01"}'
```

---

## Reset (clean slate)

```powershell
docker compose down -v
docker compose up -d
```

This wipes all Qdrant vectors and Redis data for this project.

---

## Key env knobs (`backend/.env`)

| Variable | Default | Effect |
|---|---|---|
| `SIMILARITY_HIT_THRESHOLD` | `0.92` | Cosine score above which cache is served directly |
| `SIMILARITY_GRAY_ZONE_LOW` | `0.7` | Below this score, LLM is called |
| `CACHE_SEARCH_TOP_K` | `12` | Neighbors fetched from Qdrant before rerank |
| `CACHE_RERANK_LEXICAL_WEIGHT` | `0.22` | Lexical fraction of base rerank score |
| `CACHE_RERANK_QUALITY_WEIGHT` | `0.08` | Quality-score fraction of combined rerank score |
| `CACHE_RERANK_POPULARITY_WEIGHT` | `0.04` | Popularity (hit count) fraction of combined rerank score |
| `CACHE_RERANK_POPULARITY_CAP` | `50` | Hit count at which popularity boost saturates |
| `VALIDATOR_CACHE_TTL_SECONDS` | `3600` | Redis TTL for memoised validator verdicts (0 = disabled) |
| `QUALITY_EVICTION_THRESHOLD` | `0.3` | Quality below this evicts on `POST /api/v1/cache/evict` |
