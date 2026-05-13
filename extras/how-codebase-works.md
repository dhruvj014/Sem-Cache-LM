# How This Codebase Works

This document explains how SemCacheLM is organized today, what each backend service does, and how a query moves through the system.

## 1) Big Picture

SemCacheLM is built as a **service-oriented backend** plus a React frontend:

- `frontend/`: user interface (Vite + React)
- `backend/services/gateway`: public API facade
- `backend/services/cache`: semantic cache boundary service
- `backend/services/rag`: retrieval and catalog service
- `backend/services/analytics`: analytics/event boundary service
- `backend/services/ai`: embedding + generation boundary service
- `backend/shared`: shared contracts, models, infrastructure, and observability

At runtime, the gateway is the entrypoint for client traffic (`/api/v1/*`) and calls internal service APIs over HTTP.

## 2) Main Backend Components

### Gateway (`backend/services/gateway`)

Role: public API facade and boundary routing.

Important files:

- `backend/services/gateway/app/main.py`: FastAPI app startup, dependency wiring, router registration.
- `backend/services/gateway/app/api/v1/query.py`: submit async jobs and poll job status.
- `backend/services/gateway/app/clients/http/orchestrator.py`: sync fallback call to orchestrator service.
- `backend/services/gateway/app/config.py`: environment-driven settings.

### Orchestrator Service (`backend/services/orchestrator`)

Role: owns query decision/orchestration logic for both async stream worker and sync internal API.

Important files:

- `backend/services/orchestrator/app/main.py`
- `backend/services/orchestrator/app/query_router.py`
- `backend/services/orchestrator/app/stream_worker.py`
- `backend/services/orchestrator/app/api/internal_orchestrator.py`

### Cache Service (`backend/services/cache`)

Role: semantic cache read/write/search and quality updates via internal endpoints.

Important files:

- `backend/services/cache/app/main.py`
- `backend/services/cache/app/api/internal_cache.py`

### RAG Service (`backend/services/rag`)

Role: retrieval-augmented answers and repository/API catalog generation.

Important files:

- `backend/services/rag/app/main.py`
- `backend/services/rag/app/api/rag_internal.py`
- `backend/rag_catalog/repo_catalog.md`
- `backend/rag_catalog/api_catalog.md`

### Analytics Service (`backend/services/analytics`)

Role: ingest and serve query metrics/history.

Important files:

- `backend/services/analytics/app/main.py`
- `backend/services/analytics/app/api/internal_analytics.py`

### AI Service (`backend/services/ai`)

Role: internal embedding and generation APIs, provider-backed by Ollama services.

Important files:

- `backend/services/ai/app/main.py`
- `backend/services/ai/app/api/internal_ai.py`

### Shared Module (`backend/shared`)

Role: reusable contracts and platform utilities.

Important files:

- `backend/shared/contracts/internal.py`: internal request/response models for service-to-service APIs.
- `backend/shared/contracts/public.py`: public-facing contract definitions.
- `backend/shared/models/schemas.py` and `backend/shared/models/enums.py`: shared data models.
- `backend/shared/infra/qdrant_client.py`: Qdrant connection/health abstraction.
- `backend/shared/infra/redis_client.py`: Redis connection/health abstraction.
- `backend/shared/observability/logger.py`: structured logging setup.
- `backend/shared/observability/correlation.py`: request correlation middleware.

## 3) End-to-End Query Flow

The primary path is `POST /api/v1/query` in `backend/services/gateway/app/api/v1/query.py`.

1. Gateway receives `QueryRequest`.
2. Gateway writes `QuerySubmittedV1` to Redis Streams and returns `202 + job_id`.
3. Orchestrator stream worker consumes the message and runs the decision pipeline:
   - build search text (optionally including session context),
   - request embedding,
   - search/rerank cache hits,
   - apply agent decision layer.
4. Agent decision layer chooses one of:
   - `CACHE_HIT`: serve cache result directly.
   - `VALIDATE`: run false-hit validation before serving/rejecting cached result.
   - `LLM_FALLBACK`: skip cache and generate a fresh answer.
5. On fallback/invalid cache:
   - call RAG service for retrieval-backed answer, or
   - call LLM generation path if no RAG answer is available.
6. Store resulting answer in cache (best-effort).
7. Persist session context.
8. Publish analytics event to Redis stream (`semcache:stream:analytics:events:v1`); analytics service projector consumes it.
9. Mark query job completed/failed in Redis and publish `QueryCompletedV1`.
10. Gateway `GET /api/v1/query/{job_id}` reads the job result.


## 4) Data and State Ownership

- **Qdrant**: dense vector search storage for semantic cache entries.
- **Redis**:
  - cache metadata (quality scores, hit counts),
  - validator/session state,
  - analytics/event support,
  - catalog artifact caching.
- **Ollama**: embeddings and LLM inference provider.

## 5) Configuration Model

Central config is in `backend/services/gateway/app/config.py` (`Settings` class). All services currently reuse this settings module.

Key categories:

- app/runtime (`app_env`, `app_version`, `log_level`, CORS)
- infrastructure (`qdrant_*`, `redis_*`)
- model/provider (`ollama_*`)
- cache/decision tuning (`similarity_*`, `quality_*`, rerank controls)
- session/validator controls (`session_context_ttl_seconds`, `validator_cache_ttl_seconds`)
- RAG/catalog settings (`rag_*`)
- service URLs and timeouts (`*_service_base_url`, `*_service_request_timeout_seconds`)

## 6) Service Boundaries and Current Coupling

The intended rule in `backend/services/README.md` is:

- allowed: `service -> shared`
- disallowed: direct imports of another service's internal modules

Current implementation: gateway and orchestrator both consume shared contracts/ports. Query handling defaults to the **async job API** (`POST /query` → **202** + Redis Streams); synchronous `POST /query` is an opt-in fallback routed gateway -> orchestrator HTTP.

## 7) Startup and Local Execution

From repository root, services are started individually:

- `PYTHONPATH=backend uvicorn services.gateway.app.main:app --port 8000 --reload`
- `PYTHONPATH=backend uvicorn services.rag.app.main:app --port 8001 --reload`
- `PYTHONPATH=backend uvicorn services.cache.app.main:app --port 8002 --reload`
- `PYTHONPATH=backend uvicorn services.analytics.app.main:app --port 8003 --reload`
- `PYTHONPATH=backend uvicorn services.ai.app.main:app --port 8004 --reload`
- `PYTHONPATH=backend uvicorn services.orchestrator.app.main:app --port 8005 --reload`

## 8) Legacy vs Current Layout

The root README describes a cutover from `backend/app` to `backend/services` + `backend/shared`. In this branch, you may still see leftover migration artifacts while service-first paths are the active runtime paths for startup and imports.

## 9) If You Are New to the Repo

Start in this order:

1. `backend/services/gateway/app/main.py` (wiring)
2. `backend/services/gateway/app/api/v1/query.py` (public query entrypoint)
3. `backend/services/orchestrator/app/query_router.py` (core behavior)
4. `backend/services/cache/app/api/internal_cache.py` (cache boundary)
5. `backend/services/rag/app/api/rag_internal.py` (retrieval boundary)
6. `backend/shared/contracts/internal.py` (service contracts)

This gives the fastest path to understanding behavior before diving into implementation details.
