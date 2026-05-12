"""Contracts for analytics export (JSON / CSV)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalyticsExportPayload(BaseModel):
    """Structured export: summary hash + history rows."""

    summary: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    exported_at: str = Field(..., min_length=1)


class AnalyticsExportEnvelope(BaseModel):
    """Internal service wraps CSV as text or JSON as payload."""

    kind: str = Field(..., pattern="^(json|csv)$")
    json_payload: dict[str, Any] | None = None
    csv_text: str | None = None
