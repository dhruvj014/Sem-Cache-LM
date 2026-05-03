"""Runtime decision thresholds (similarity hit + gray zone). Thread-safe."""

from threading import Lock

from app.config import Settings


class DecisionThresholds:
    def __init__(self, settings: Settings):
        self._lock = Lock()
        self.similarity_hit_threshold = settings.similarity_hit_threshold
        self.similarity_gray_zone_low = settings.similarity_gray_zone_low

    def update(self, hit: float, gray_low: float) -> None:
        if gray_low >= hit:
            raise ValueError(
                "similarity_gray_zone_low must be strictly less than similarity_hit_threshold"
            )
        with self._lock:
            self.similarity_hit_threshold = hit
            self.similarity_gray_zone_low = gray_low

    def as_dict(self) -> dict[str, float]:
        with self._lock:
            return {
                "similarity_hit_threshold": self.similarity_hit_threshold,
                "similarity_gray_zone_low": self.similarity_gray_zone_low,
            }

    def resolve(
        self,
        hit_override: float | None,
        gray_override: float | None,
    ) -> tuple[float, float]:
        with self._lock:
            hit = (
                hit_override
                if hit_override is not None
                else self.similarity_hit_threshold
            )
            gray = (
                gray_override
                if gray_override is not None
                else self.similarity_gray_zone_low
            )
        if gray >= hit:
            raise ValueError(
                "Effective gray_zone_low must be strictly less than hit_threshold"
            )
        return hit, gray
