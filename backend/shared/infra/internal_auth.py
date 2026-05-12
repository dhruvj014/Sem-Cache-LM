"""Bearer-token middleware for service-to-service /internal/* routes.

How it works
------------
- If ``INTERNAL_SERVICE_TOKEN`` is empty (default for local dev), all requests
  pass through unchanged — no configuration needed for local testing.
- When the token is set, every request whose path starts with ``/internal``
  must carry an ``Authorization: Bearer <token>`` header that matches exactly.
  Any mismatch returns HTTP 403 immediately, before the route handler runs.

On AWS
------
Set ``INTERNAL_SERVICE_TOKEN`` from Secrets Manager on every service task.
The same token must be set on every client (gateway, orchestrator) so they
include the header in outgoing requests.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class InternalAuthMiddleware(BaseHTTPMiddleware):
    """Validate bearer token on /internal/* paths."""

    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._token = token
        self._enabled = bool(token)

    async def dispatch(self, request: Request, call_next):
        if not self._enabled:
            return await call_next(request)

        if request.url.path.startswith("/internal"):
            auth_header = request.headers.get("Authorization", "")
            if auth_header != f"Bearer {self._token}":
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "data": None,
                        "error": {"message": "Forbidden: invalid or missing service token"},
                        "timestamp": None,
                    },
                )

        return await call_next(request)
