# SemCacheLM — Local run & test guide

This document is a **step-by-step** checklist to run the full stack on your machine and validate behavior with automated tests, HTTP API calls, and the web UI.

**Recommended order**

1. Prerequisites → 2. Infrastructure (Docker) → 3. Gemini API key → 4. Backend Python env + config → 5. Automated tests → 6. Run API + manual scenarios → 7. Frontend → 8. UI checklist.

All paths below assume the **repository root** (the folder that contains `docker-compose.yml`, `backend/`, and `frontend/`).

---

## 0. Prerequisites

Install and verify before continuing:

| Requirement | Notes |
| ----------- | ----- |
| **Docker Desktop** | Used for Qdrant + Redis only. |
| **Python 3.11+** | `python --version` |
| **Node.js 18+** | `node --version` |
| **Gemini API key** | Set **`GEMINI_API_KEY`** in `backend/.env` or repo-root `.env` (see `backend/.env.example`). AI and RAG call Google’s API over HTTPS. |

Optional but useful:

| Tool | Why |
| ---- | --- |
| `curl` | Windows 10/11 include `curl.exe`; in PowerShell, prefer `curl.exe` so you don’t hit the `Invoke-WebRequest` alias. |
| `redis-cli` | Only if you want to ping Redis from the host; otherwise use `docker exec` (below). |

---

## 1. Start Qdrant and Redis

**Step 1.1** — From the **repository root**:

```bash
docker compose up -d
```

(If your Docker install only provides the older CLI, use `docker-compose up -d`.)

**Step 1.2** — Wait until containers are healthy (`docker compose ps`).

**Step 1.3** — Verify Qdrant:

```bash
curl http://localhost:6333/healthz
```

(Windows: `curl.exe` if needed.)

Expect HTTP **200**.

**Step 1.4** — Verify Redis (no local `redis-cli` required):

```bash
docker exec semcachelm-redis redis-cli ping
```

Expect **`PONG`**.

**Troubleshooting:** If `docker exec` fails with “No such container”, run `docker ps` and use the actual Redis container name from `docker-compose.yml` (default: `semcachelm-redis`).

---

## 2. Gemini API key

Set **`GEMINI_API_KEY`** in `backend/.env` (and repo-root `.env` when using Docker Compose). Without it, the AI (`8004`) and RAG (`8001`) services cannot embed or generate.

Optionally confirm outbound HTTPS from your machine (corporate proxies sometimes block Generative Language API hosts).

---

## 3. Backend: virtual environment and configuration

**Step 3.1** — Create and activate a venv inside `backend/`:

```bash
cd backend
python -m venv venv
```

Activate:

- **Windows (cmd):** `venv\Scripts\activate.bat`
- **Windows (PowerShell):** `venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source venv/bin/activate`

**Step 3.2** — Install dependencies (includes pytest — needed for Section 5):

```bash
pip install -r requirements-dev.txt
```

**Step 3.3** — Create local config from the example:

- **Windows (cmd):** `copy .env.example .env`
- **Windows (PowerShell):** `Copy-Item .env.example .env`
- **macOS / Linux:** `cp .env.example .env`

Edit `.env` only if your ports differ from the defaults.

**Step 3.4** (optional **clean slate** for repeatable manual tests) — To wipe vector + Redis data so Scenario A always starts “cold”:

```bash
cd ..
docker compose down -v
docker compose up -d
```

Then repeat Section 1 checks. **Warning:** this deletes all cached vectors and Redis keys for this project.

---

## 4. Automated tests (no Docker / Gemini API key required for these)

Run from **`backend/`** with the venv **activated**.

**Step 4.1 — Unit tests**

```bash
pytest tests/unit/ -v
```

| File | Coverage |
| ---- | -------- |
| `tests/unit/test_agent_decision.py` | Decision branches + low-quality demotion |
| `tests/unit/test_false_hit_detector.py` | YES/NO verdicts, bad LLM text, LLM error path |
| `tests/unit/test_cache_service.py` | Quality EMA wiring, promote/demote |

**Step 4.2 — Integration tests**

```bash
pytest tests/integration/ -v
```

`tests/unit/test_false_hit_detector.py` covers validator verdicts, malformed LLM output, and LLM errors (async generate callable).

Stream orchestration behavior is implemented in `tests/integration/` via gateway/orchestrator/cache/rag stream contracts where applicable; the former `test_query_router.py` suite was removed when `QueryRouterService` was deleted.

**Step 4.3 — Full test pass (optional one-liner)**

```bash
pytest tests/ -v
```

Expect **all green**, no skips, for a healthy tree.

---

## 5. Run the API server

Keep this process running in its **own terminal**. Working directory: **`backend/`**, venv **activated**.

**Step 5.1**

```bash
uvicorn services.gateway.app.main:app --reload --port 8000
```

### Optional: run full microservice stack

From repo root, run each in a separate terminal:

```bash
PYTHONPATH=backend uvicorn services.gateway.app.main:app --port 8000 --reload
PYTHONPATH=backend uvicorn services.rag.app.main:app --port 8001 --reload
PYTHONPATH=backend uvicorn services.cache.app.main:app --port 8002 --reload
PYTHONPATH=backend uvicorn services.analytics.app.main:app --port 8003 --reload
PYTHONPATH=backend uvicorn services.ai.app.main:app --port 8004 --reload
```

**Step 5.2 — Smoke check**

Open in a browser:

- **Swagger UI:** [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **Health:** below

```bash
curl http://localhost:8000/api/v1/health
```

On Windows PowerShell you can use `curl.exe` explicitly.

Expect JSON with overall **`status`**, **`services`** (each backend dependency reachable), **`llm_model`**, **`embedding_model`**, and **`qdrant_collection`**. If **`ai_service`** or **`rag_service`** is false, fix **`GEMINI_API_KEY`** and service logs before UI/manual tests that need embeddings or LLM.

---

## 6. How to read API responses

Every business endpoint returns an **envelope**:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "..."
}
```

Manual expectations below are written in terms of **`data.*`** fields inside that object.

To pretty-print (optional), pipe to a formatter, e.g. `python -m json.tool` after saving output to a file, or use any JSON-aware HTTP client.

---

## 7. Manual API scenarios (full stack)

Use **`curl.exe`** on Windows if `curl` is aliased in PowerShell.

Replace `SESSION` with any non-empty string (e.g. `test-001`); reuse it if you want the same session context in logs/metadata.

**Quoting**

- **PowerShell:** wrap the JSON in **single quotes** so you do not need backslash escapes:

  ```powershell
  curl.exe -X POST http://localhost:8000/api/v1/query `
    -H "Content-Type: application/json" `
    -d '{"query": "What is a distributed system?", "session_id": "test-001"}'
  ```

- **cmd.exe:** use **`^`** at end of line and escaped interior double quotes:

  ```bat
  curl.exe -X POST http://localhost:8000/api/v1/query ^
    -H "Content-Type: application/json" ^
    -d "{\"query\": \"What is a distributed system?\", \"session_id\": \"test-001\"}"
  ```

- **Bash / zsh:** use `\` line breaks or one line; interior double quotes need no escape inside `'...'` if you single-quote the whole `-d` argument.

### Scenario A — Cold cache (first query on empty cache)

Use the **PowerShell** or **cmd.exe** snippet under **Quoting** above (same URL and JSON body).

**Expected in `data`:** `source` **`"llm"`**, `agent_action` **`"LLM_FALLBACK"`**, `similarity_score` **&lt; 0.75** (typically **0.0** when nothing is in the index), a non-null `cache_id` for the new entry.

### Scenario B — Exact repeat (cache hit)

Send **exactly the same** JSON body as Scenario A again.

**Expected:** `source` **`"cache"`**, `agent_action` **`"CACHE_HIT"`**, `similarity_score` **≥ 0.92**, latency much lower than the first call.

### Scenario C — Paraphrase (semantic hit or validate)

```bash
curl -s -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Can you explain what distributed systems are?", "session_id": "test-001"}'
```

On Windows with **`curl.exe`**, reuse the same JSON and headers; see **Quoting** (PowerShell single-quote form is easiest).

**Expected:** High `similarity_score`; `agent_action` may be **`CACHE_HIT`** or **`VALIDATE`**. If the validator approves, `source` can be **`"validated_cache"`**.

### Scenario D — Possible gray zone / false-hit path

After Scenario A’s text is cached, try a **related but different** question (embedding may fall in the 0.75–0.92 band — not guaranteed):

```bash
curl -s -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain CAP theorem trade-offs", "session_id": "test-001"}'
```

**Expected when validation runs:** structured logs include **`false_hit.validated`**. If the judge rejects the match, **`source`** **`"false_hit_fallback"`** and **`agent_action`** **`"LLM_FALLBACK"`**.

> **Note:** With real embeddings, this query might still be a strong hit, a miss, or gray zone. Treat this as a **best-effort** probe; integration tests already pin orchestration behavior with fakes.

### Scenario E — Feedback (downvotes) and eviction

1. Copy a **`cache_id`** from any prior `query` response’s `data.cache_id`.

2. Send downvotes (repeat several times), substituting your real id for `YOUR_CACHE_ID`:

   ```bash
   curl -s -X POST "http://localhost:8000/api/v1/feedback/YOUR_CACHE_ID" \
     -H "Content-Type: application/json" \
     -d '{"rating": "down"}'
   ```

   (**Windows:** `curl.exe` + body `'{"rating": "down"}'` in PowerShell.)

   Each response’s **`data.new_quality_score`** is the updated EMA (not a field named `quality_score`). With default **`QUALITY_EMA_ALPHA=0.2`** and starting quality **1.0**, about **six** consecutive downvotes brings score below **`QUALITY_EVICTION_THRESHOLD`** (**0.3**).

3. Evict low-quality entries:

   ```bash
   curl -X POST http://localhost:8000/api/v1/cache/evict
   ```

   **Expected:** `data.evicted_ids` lists IDs evicted at or below the threshold, which should include the heavily downvoted entry.

### Scenario F — Analytics

Summary:

```bash
curl http://localhost:8000/api/v1/analytics/summary
```

**Expected inside `data`:** e.g. `hit_rate`, `avg_cache_latency_ms`, `avg_llm_latency_ms`, `cache_entries`, `estimated_tokens_saved`, `estimated_time_saved_ms`, `last_decision`.

History (last 10 rows):

```bash
curl "http://localhost:8000/api/v1/analytics/history?limit=10"
```

**Expected:** `data.entries` is an array of recent rows (`query`, `source`, `agent_action`, `similarity_score`, `latency_ms`, etc.).

---

## 8. Frontend (local UI)

**Step 8.1** — Open a **new terminal**. Directory: **`frontend/`**.

**Step 8.2** — Ensure API URL is set (defaults to local backend):

```bash
copy .env.example .env
```

(Use `Copy-Item` on PowerShell or `cp` on Unix if you prefer.)

`VITE_API_URL` should be **`http://localhost:8000`** for local testing.

**Step 8.3**

```bash
npm install
npm run dev
```

**Step 8.4** — Open **[http://localhost:5173](http://localhost:5173)** with **Section 5** still running.

If the browser cannot reach the API, confirm **CORS** in `backend/.env`: `CORS_ORIGINS` should include `http://localhost:5173`.

---

## 9. Frontend visual verification checklist

With **`npm run dev`** and **`uvicorn`** both running:

- [ ] Source badge matches type (e.g. cache hit vs LLM vs validated vs false-hit fallback).
- [ ] Decision Trace Card shows action, reason, similarity, latency.
- [ ] Query Flow Visualizer runs Embed → Search → Agent → Result.
- [ ] System Monitor Panel refreshes on interval.
- [ ] Latency comparison shows cache lower than LLM after a few queries.
- [ ] Demo Sequence completes multiple queries and badge types.
- [ ] Cache Explorer reflects quality after up/down feedback.
- [ ] Analytics charts and savings counter reflect cache hits.
- [ ] Stopping Qdrant or Redis turns the corresponding health indicator red / shows warning (after refresh or next poll).

---

## 10. Performance baseline (informal)

Rough expectations on a capable laptop / discrete GPU:

| Workload | Ballpark |
| -------- | -------- |
| Repeated identical queries | Cache path much faster than first LLM call |
| Mixed paraphrases after warm-up | Hit rate depends on text; UI makes the split obvious |
| Cold Gemini generation | Often **hundreds of ms to a few seconds** — latency bar should contrast sharply with cache |

---

## 11. Quick troubleshooting

| Symptom | What to check |
| ------- | ------------- |
| `Connection refused` on **6333** / **6379** | `docker compose ps`; rerun Section 1. |
| Health shows **`ai_service`** or **`rag_service`** **false** | **`GEMINI_API_KEY`** set? Outbound HTTPS OK? Check **`docker compose logs ai`** / **`rag`**. |
| **500** on `/query` | Backend logs; often missing/invalid Gemini key or quota/rate limits. |
| Frontend **CORS** errors | `CORS_ORIGINS` in `backend/.env` includes UI origin. |
| Cache never hits | Different `session_id` is fine for caching — issue is usually empty index or very different wording below similarity threshold. |
| pytest **not found** | Use `pip install -r requirements-dev.txt` (not `requirements.txt` alone). |

---

## 12. Test inventory (reference)

| Layer | Command | Needs Docker / live Gemini |
| ----- | ------- | ---------------------- |
| Unit | `pytest tests/unit/ -v` | No |
| Integration | `pytest tests/integration/ -v` | No |
| Manual API + UI | Sections 5–9 | Yes (Qdrant, Redis, **`GEMINI_API_KEY`**, plus npm for UI) |

For architecture and endpoint tables, see [README.md](./README.md).
