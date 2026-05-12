"""Cache warming (pre-populate semantic cache)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CacheWarmRequest(BaseModel):
    questions: list[str] = Field(..., min_length=1, max_length=400)

    @classmethod
    def from_lines(cls, text: str) -> "CacheWarmRequest":
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        return cls(questions=lines)


class CacheWarmResponse(BaseModel):
    warmed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
