import hashlib
import re

from shared.config.settings import Settings
from shared.domain.model_providers import LLMClient
from shared.infra.redis_client import RedisInfrastructure
from shared.models.schemas import ValidationResult
from shared.observability.logger import get_logger

logger = get_logger(__name__)

VALIDATION_SYSTEM_PROMPT = (
    "You validate whether a CACHED LLM answer can be reused for a NEW user question. "
    "Answer YES if the cache contains enough correct information that a user could "
    "accurately satisfy the new question—including indirect support (e.g. the entity "
    "appears in an MCU/Marvel movie list, timeline, or roster implies it is a Marvel "
    "film unless the cache says otherwise). "
    "Answer NO only if the cache is wrong, misleading, off-topic, contradicts the "
    "question, or omits facts needed to answer safely. Do not require the cache to "
    "repeat the exact phrasing of the new question (e.g. a Yes/No question does not "
    "require the word \"Yes\" if the facts clearly imply the answer). "
    "Reply ONLY in the exact format: "
    "VERDICT: <YES|NO>\nCONFIDENCE: <0.00-1.00>\nREASON: <one short sentence>."
)

VALIDATOR_CACHE_PREFIX = "semcache:validator:v1"


class FalseHitDetector:
    def __init__(
        self,
        settings: Settings,
        llm: LLMClient,
        redis_infra: RedisInfrastructure | None = None,
    ):
        self._settings = settings
        self._llm = llm
        self._redis = redis_infra.client if redis_infra is not None else None

    def _validator_cache_key(
        self, incoming_query: str, cache_id: str, candidate_response: str
    ) -> str | None:
        ttl = self._settings.validator_cache_ttl_seconds
        if not self._redis or ttl <= 0 or not cache_id:
            return None
        fp = hashlib.sha256((candidate_response or "").encode()).hexdigest()[:32]
        digest = hashlib.sha256(
            f"{incoming_query.strip()}|{cache_id}|{fp}".encode()
        ).hexdigest()
        return f"{VALIDATOR_CACHE_PREFIX}:{digest}"

    async def validate(
        self,
        incoming_query: str,
        candidate_response: str,
        similarity_score: float,
        cache_id: str | None = None,
    ) -> ValidationResult:
        cache_key = self._validator_cache_key(
            incoming_query, cache_id or "", candidate_response
        )
        if cache_key:
            try:
                raw = await self._redis.get(cache_key)
                if raw:
                    result = ValidationResult.model_validate_json(raw)
                    logger.info(
                        "false_hit.cache_hit",
                        cache_id=cache_id,
                        is_valid=result.is_valid,
                    )
                    return result
            except Exception as e:  # noqa: BLE001
                logger.warning("false_hit.cache_read_error", error=str(e))

        prompt = (
            f"NEW QUERY:\n{incoming_query}\n\n"
            f"CACHED RESPONSE:\n{candidate_response}\n\n"
            f"SIMILARITY SCORE: {similarity_score:.3f}\n\n"
            "Using only the CACHED RESPONSE, could a user accurately answer the NEW QUERY? "
            "(YES if the facts there are sufficient and correct; NO if not.)"
        )
        try:
            raw_llm = await self._llm.generate(prompt=prompt, system=VALIDATION_SYSTEM_PROMPT)
        except Exception as e:  # noqa: BLE001
            logger.warning("false_hit.llm_error", error=str(e))
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                reason=f"Validator LLM error: {e}",
            )

        verdict_match = re.search(r"VERDICT:\s*(YES|NO)", raw_llm, re.IGNORECASE)
        confidence_match = re.search(r"CONFIDENCE:\s*([0-9.]+)", raw_llm)
        reason_match = re.search(r"REASON:\s*(.+)", raw_llm)

        is_valid = bool(verdict_match) and verdict_match.group(1).upper() == "YES"
        try:
            confidence = float(confidence_match.group(1)) if confidence_match else 0.5
        except ValueError:
            confidence = 0.5
        reason = reason_match.group(1).strip() if reason_match else raw_llm.strip()[:200]

        result = ValidationResult(is_valid=is_valid, confidence=confidence, reason=reason)
        logger.info(
            "false_hit.validated",
            is_valid=result.is_valid,
            confidence=result.confidence,
            similarity=similarity_score,
        )

        if cache_key and self._redis and self._settings.validator_cache_ttl_seconds > 0:
            try:
                await self._redis.setex(
                    cache_key,
                    self._settings.validator_cache_ttl_seconds,
                    result.model_dump_json(),
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("false_hit.cache_write_error", error=str(e))

        return result
