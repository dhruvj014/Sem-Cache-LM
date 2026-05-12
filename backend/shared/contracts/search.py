"""Contracts for semantic cache search / filter."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CacheSearchHit(BaseModel):
    cache_id: str
    query_preview: str
    response_preview: str
    quality_score: float
    hit_count: int
    created_at: str
    source: str = ""
    last_used_at: str = ""
    similarity_rank: float = Field(
        default=0.0,
        description="Cosine similarity to query embedding when sort is similarity; else 0",
    )


class CacheSearchResponse(BaseModel):
    entries: list[CacheSearchHit] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)


class CacheSearchParams(BaseModel):
    """Query-string backed params for GET /internal/v1/cache/search."""

    query: str = ""
    min_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    max_quality: float = Field(default=1.0, ge=0.0, le=1.0)
    sort_by: Literal["quality", "date", "similarity"] = "quality"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
