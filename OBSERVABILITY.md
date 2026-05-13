# SemCacheLM — Observability (Prometheus + Grafana)

## For teammates — getting started after git pull

### Prerequisites (one-time setup on your machine)
Set **`GEMINI_API_KEY`** in `.env` at the repo root (see [`backend/.env.example`](backend/.env.example)). The AI and RAG services call Google Gemini over HTTPS.

### Start everything (app + observability) in one command
```bash
git pull
cp .env.example .env
docker compose up -d --build
```

Wait 60–90 seconds for all services to build and start.
Check status:
```bash
docker compose ps
```

### Your URLs
| Service    | URL                                  | Login          |
|------------|--------------------------------------|----------------|
| App UI     | http://localhost:5173                | —              |
| API docs   | http://localhost:8000/api/v1/docs    | —              |
| Grafana    | http://localhost:3000                | admin / admin123 |
| Prometheus | http://localhost:9090                | —              |

### Grafana dashboard
Direct link after login:
http://localhost:3000/d/semcachelm-main/semcachelm-observability

8 panels — auto-loaded, no setup needed:
1. Cache Decision Breakdown (hits vs fallbacks vs validates)
2. Cache Hit Rate % gauge
3. LLM Latency p50/p99
4. Similarity Score Distribution
5. Cache Size + Evictions
6. Redis Stream Lag
7. HTTP Request Rate per Service
8. HTTP p99 Latency per Service

Panels are empty until you send queries through the app UI.
Use the app normally — graphs fill automatically.

### Stopping everything
```bash
docker compose down
```

### Fault tolerance
- All containers restart automatically if they crash (`restart: unless-stopped`).
- Cache hits are served even if **Gemini** is slow or unreachable.
- Losing one microservice does not take down the others.
- Redis and Qdrant data persists across restarts (named volumes).
- Prometheus only starts scraping after every backend service reports healthy, so cold-start metrics aren't lost.

### Troubleshooting
| Symptom                | Fix                                                       |
|------------------------|-----------------------------------------------------------|
| Grafana shows no data  | Send a few queries in the app UI first                    |
| Container not starting | `docker compose logs <service-name>`                      |
| LLM provider unreachable | Confirm **`GEMINI_API_KEY`** and outbound HTTPS; check AI/RAG container logs |
| Port conflict          | `lsof -i :3000` (or `:9090`) and kill the process         |
| Login error in Grafana | Use `admin / admin123` — first login may prompt to change; click **Skip** |
