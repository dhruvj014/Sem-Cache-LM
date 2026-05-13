"""Runtime threshold configuration (gateway)."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ThresholdConfigData(BaseModel):
    similarity_hit_threshold: float = Field(ge=0.0, le=1.0)
    similarity_gray_zone_low: float = Field(ge=0.0, le=1.0)
    quality_ema_alpha: float = Field(ge=0.0, le=1.0)
    quality_eviction_threshold: float = Field(ge=0.0, le=1.0)


class ThresholdConfigUpdate(BaseModel):
    similarity_hit_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    similarity_gray_zone_low: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_ema_alpha: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_eviction_threshold: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _require_some(self) -> "ThresholdConfigUpdate":
        if not any(
            [
                self.similarity_hit_threshold is not None,
                self.similarity_gray_zone_low is not None,
                self.quality_ema_alpha is not None,
                self.quality_eviction_threshold is not None,
            ]
        ):
            raise ValueError("At least one threshold field must be provided")
        return self
