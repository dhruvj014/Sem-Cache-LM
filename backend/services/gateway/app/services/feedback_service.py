from services.gateway.app.config import Settings
from shared.infra.redis_client import RedisInfrastructure
from shared.models.enums import FeedbackRating
from shared.models.schemas import FeedbackResult
from shared.domain.cache_ports import CacheWriter
from shared.observability.logger import get_logger

logger = get_logger(__name__)

QUALITY_KEY = "semcache:quality:{cache_id}"


class FeedbackService:
    """Updates cached entry quality scores using an exponential moving average,
    and signals promote/demote on the cache writer."""

    def __init__(
        self,
        settings: Settings,
        redis_infra: RedisInfrastructure,
        cache_writer: CacheWriter,
    ):
        self._settings = settings
        self._redis = redis_infra
        self._cache = cache_writer
        self._alpha = settings.quality_ema_alpha

    async def submit_feedback(
        self, cache_id: str, rating: FeedbackRating
    ) -> FeedbackResult:
        feedback_value = 1.0 if rating == FeedbackRating.UP else 0.0
        old = await self._get_quality(cache_id)
        new_score = (1 - self._alpha) * old + self._alpha * feedback_value
        new_score = max(0.0, min(1.0, new_score))

        promoted = False
        demoted = False
        if rating == FeedbackRating.UP:
            await self._cache.promote(cache_id, new_score)
            promoted = True
        else:
            await self._cache.demote(cache_id, new_score)
            demoted = True

        logger.info(
            "feedback.submitted",
            cache_id=cache_id,
            rating=rating.value,
            old=old,
            new=new_score,
        )
        return FeedbackResult(
            cache_id=cache_id,
            rating=rating,
            new_quality_score=new_score,
            promoted=promoted,
            demoted=demoted,
        )

    async def _get_quality(self, cache_id: str) -> float:
        raw = await self._redis.client.get(QUALITY_KEY.format(cache_id=cache_id))
        if raw is None:
            return 1.0
        try:
            return float(raw)
        except ValueError:
            return 1.0
