"""Per-session last Q + answer snippet for multi-turn retrieval (Redis)."""

from __future__ import annotations

import json

from shared.infra.redis_client import RedisInfrastructure

CTX_KEY = "semcache:session_ctx:{session_id}"


class SessionContextService:
    """Stores short-lived context so follow-up questions embed closer to prior answers."""

    def __init__(self, redis_infra: RedisInfrastructure, ttl_seconds: int = 86_400):
        self._r = redis_infra.client
        self._ttl = ttl_seconds

    async def get(
        self, session_id: str
    ) -> tuple[str | None, str | None]:
        raw = await self._r.get(CTX_KEY.format(session_id=session_id))
        if not raw:
            return None, None
        try:
            data = json.loads(raw)
            return data.get("q"), data.get("snip")
        except (json.JSONDecodeError, TypeError):
            return None, None

    async def set(
        self,
        session_id: str,
        last_query: str,
        last_response: str,
        max_snippet_chars: int,
    ) -> None:
        snip = (last_response or "").strip()
        if max_snippet_chars > 0 and len(snip) > max_snippet_chars:
            snip = snip[:max_snippet_chars] + "…"
        blob = json.dumps(
            {"q": (last_query or "").strip(), "snip": snip},
            ensure_ascii=False,
        )
        await self._r.set(
            CTX_KEY.format(session_id=session_id),
            blob,
            ex=self._ttl,
        )


class NullSessionContextService:
    """No-op for tests."""

    async def get(self, session_id: str) -> tuple[str | None, str | None]:
        return None, None

    async def set(
        self,
        session_id: str,
        last_query: str,
        last_response: str,
        max_snippet_chars: int,
    ) -> None:
        pass
