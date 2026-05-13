"""Request/response contracts for cache + RAG invalidation (internal + gateway)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class InternalCacheInvalidateRequest(BaseModel):
    """Exactly one of chunk_id or source_identifier must be set."""

    chunk_id: Optional[str] = None
    source_identifier: Optional[str] = Field(
        default=None,
        description="Matches cache payload rag_citations (file paths) or embedded chunk linkage fields.",
    )

    @model_validator(mode="after")
    def _exactly_one(self) -> "InternalCacheInvalidateRequest":
        has_chunk = bool((self.chunk_id or "").strip())
        has_src = bool((self.source_identifier or "").strip())
        if has_chunk == has_src:
            raise ValueError("Provide exactly one of chunk_id or source_identifier")
        return self


class InternalCacheInvalidateResponse(BaseModel):
    invalidated_count: int = Field(ge=0)
    invalidated_cache_ids: list[str] = Field(default_factory=list)


class InternalRagInvalidateRequest(BaseModel):
    source_identifier: str = Field(..., min_length=1)


class InternalRagInvalidateResponse(BaseModel):
    deleted_chunk_points: int = Field(ge=0)
    collections_touched: list[str] = Field(default_factory=list)


class PublicCacheInvalidateRequest(BaseModel):
    """Public gateway body — same XOR rule as internal cache invalidation."""

    chunk_id: Optional[str] = None
    source_identifier: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "PublicCacheInvalidateRequest":
        has_chunk = bool((self.chunk_id or "").strip())
        has_src = bool((self.source_identifier or "").strip())
        if has_chunk == has_src:
            raise ValueError("Provide exactly one of chunk_id or source_identifier")
        return self


class PublicCacheInvalidateResponse(BaseModel):
    cache_invalidated_count: int = Field(ge=0)
    invalidated_cache_ids: list[str] = Field(default_factory=list)
    rag_deleted_chunk_points: int = Field(ge=0)
    rag_collections_touched: list[str] = Field(default_factory=list)
    rag_confirmation: str = ""
