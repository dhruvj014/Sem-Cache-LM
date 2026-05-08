# Service Boundaries (Monorepo)

- Allowed dependency direction: `service -> shared`.
- Disallowed: importing another service's internal modules directly.
- Cross-service communication must use HTTP/event contracts.

Current service entrypoints:
- Gateway: `services/gateway/app/main.py`
- RAG: `services/rag/app/main.py`
- Cache: `services/cache/app/main.py`
- Analytics: `services/analytics/app/main.py`
- AI inference: `services/ai/app/main.py`

Run locally from repo root:
- `PYTHONPATH=backend uvicorn services.gateway.app.main:app --port 8000 --reload`
- `PYTHONPATH=backend uvicorn services.rag.app.main:app --port 8001 --reload`
- `PYTHONPATH=backend uvicorn services.cache.app.main:app --port 8002 --reload`
- `PYTHONPATH=backend uvicorn services.analytics.app.main:app --port 8003 --reload`
- `PYTHONPATH=backend uvicorn services.ai.app.main:app --port 8004 --reload`

