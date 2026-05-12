"""Contracts for cache quality health score breakdown."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CacheHealthScoreBreakdown(BaseModel):
    healthy: int = Field(ge=0, description="Entries with quality score > 0.8")
    degrading: int = Field(ge=0, description="Entries with quality in [0.3, 0.8]")
    critical: int = Field(ge=0, description="Entries with quality score < 0.3")
    total: int = Field(ge=0)
    overall_health_percent: float = Field(
        ge=0.0,
        le=100.0,
        description="100 * healthy / total (100 if total is 0)",
    )


class InternalHealthScoreRequest(BaseModel):
    """Reserved for future filters; empty body accepted."""

    pass
