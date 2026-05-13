# Operations: observability, AWS, and data cutover

## Grafana & Prometheus (local Docker Compose)

Start the full stack from the repo root (see [README.md](../README.md)). Observability containers start with the same `docker compose up --build -d`.

| Service | URL | Notes |
| ------- | --- | ----- |
| App UI | http://localhost:5173 | Vite dev server in default compose |
| Grafana | http://localhost:3000 | Default login `admin` / `admin123` (Grafana 10) |
| Prometheus | http://localhost:9090 | Scrapes service `/metrics` after backends are healthy |
| Dashboard | http://localhost:3000/d/semcachelm-main/semcachelm-observability | Loaded from `grafana/provisioning` |

Panels stay empty until traffic hits the gateway and workers. Use the chat UI or manual `POST /api/v1/query` calls.

**Troubleshooting**

| Symptom | Check |
| ------- | ----- |
| Grafana “No data” | Send a few queries through the UI first |
| Prometheus targets DOWN | `docker compose ps`; backends may still be in `start_period` |
| Grafana login fails | Use `admin` / `admin123`; skip forced password change if prompted |
| Port 3000 / 9090 busy | Free the port or remap in `docker-compose.yml` |

Fault tolerance: containers use `restart: unless-stopped`; Redis and Qdrant use named volumes so restarts keep data.

---

## AWS (`docker-compose.aws.yml`)

The SPA is built with Vite: **`VITE_API_URL` is baked in at image build time**. It must be a URL the **browser** can reach (for example `http://YOUR_PUBLIC_IP:8000` or your HTTPS API hostname), **not** `http://localhost:8000` (that points at the visitor’s laptop).

1. Set `VITE_API_URL` and `CORS_ORIGINS` in the `.env` next to the compose file before build.  
   `CORS_ORIGINS` must include the UI origin (for example `http://YOUR_PUBLIC_IP` on port 80).

2. Rebuild the frontend after changing `VITE_API_URL`:

   `docker compose -f docker-compose.aws.yml build --no-cache frontend`

Managed Redis (ElastiCache) and Qdrant Cloud are supported via the same variables as local compose; see root `.env.example` and `backend/.env.example`.

---

## Embedding / cache cutover (Gemini space change)

After changing the embedding model or vector size (for example moving to `gemini-embedding-001` with `outputDimensionality` aligned to `QDRANT_VECTOR_SIZE` / `RAG_QDRANT_VECTOR_SIZE`), **old vectors are not compatible** with new query embeddings.

Per environment:

1. **Semantic cache** — Clear the cache Qdrant collection (eviction / clear APIs or admin tools). Optionally reconcile Redis keys under quality prefixes if you need a perfectly clean metadata plane.

2. **RAG** — Invalidate Redis under `RAG_REDIS_MANIFEST_PREFIX` and/or drop RAG Qdrant collections matching your `RAG_QDRANT_COLLECTION` naming so `initialize()` rebuilds with the new embedder.

3. Prefer a short maintenance window or accept a cold cache until traffic repopulates.

4. Verify one end-to-end query and that reported vector size matches configuration.
