# Roadmap & future ideas

High-level direction for CMPE 273 / production hardening. Not a commitment schedule.

## Enterprise gaps (from course rubric)

| Area | Direction |
| ---- | --------- |
| AWS | Multi-service mesh aligned with `docker-compose.aws.yml` (ECS/Fargate or EC2); secrets in Parameter Store / Secrets Manager |
| Service auth | Consistent bearer token on `/internal/v1/*` across services; no silent trust on the container network |
| Data plane | Replicated Redis, durable Qdrant (Cloud or EBS), persistent or object-store–backed RAG clone cache |
| Quality / latency | Tune thresholds and validator prompts; optional faster Gemini SKUs or regional placement |

**Non-goals for course scope:** multi-region active-active, zero-downtime blue/green.

## Product / UX ideas (backlog)

- Richer cache embedding target (e.g. query + truncated answer) for better follow-up recall  
- Optional debug payload with top‑k neighbor scores in the API + small UI panel  
- One-click “warm cache” scripted queries for demos  
- Streaming tokens to the UI for perceived latency  

Performance-oriented backlog includes session-aware embeddings, stricter eviction caps, and continued rerank / Redis tuning (see `backend/.env.example` for current knobs).
