from __future__ import annotations

import asyncio
import math
import time

from shared.config.settings import Settings
from shared.contracts.internal import (
    InternalEmbedRequest,
    InternalEmbedResponse,
    InternalGenerateRequest,
    InternalGenerateResponse,
    InternalSparseEmbedRequest,
    InternalSparseEmbedResponse,
)
from shared.infra.redis_client import RedisInfrastructure
from shared.domain.model_providers import EmbeddingService
from shared.domain.model_providers import LLMClient
from shared.observability.logger import get_logger

logger = get_logger(__name__)

RATE_KEY = "semcache:ai:rate:{minute_bucket}"


class AIInferenceService:
    def __init__(
        self,
        settings: Settings,
        provider_embedder: EmbeddingService,
        provider_llm: LLMClient,
        redis_infra: RedisInfrastructure,
    ):
        self._settings = settings
        self._embedder = provider_embedder
        self._llm = provider_llm
        self._redis = redis_infra.client

    async def embed(self, request: InternalEmbedRequest) -> InternalEmbedResponse:
        await self._enforce_rate_limit("embed")
        start = time.perf_counter()
        embedding = await self._with_retries(self._embedder.embed, request.text)
        latency_ms = (time.perf_counter() - start) * 1000
        return InternalEmbedResponse(
            embedding=embedding,
            vector_size=len(embedding),
            latency_ms=round(latency_ms, 2),
            provider="ollama",
        )

    async def generate(self, request: InternalGenerateRequest) -> InternalGenerateResponse:
        await self._enforce_rate_limit("generate")
        start = time.perf_counter()
        text = await self._with_retries(
            self._llm.generate,
            request.prompt,
            request.system,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        in_tokens = self._estimate_tokens(request.prompt + (request.system or ""))
        out_tokens = self._estimate_tokens(text)
        estimated_cost = self._estimate_cost(in_tokens, out_tokens)
        logger.info(
            "ai_inference.generate",
            latency_ms=round(latency_ms, 2),
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            estimated_cost_usd=estimated_cost,
        )
        return InternalGenerateResponse(
            text=text,
            latency_ms=round(latency_ms, 2),
            provider="ollama",
            model=self._settings.ollama_llm_model,
            estimated_input_tokens=in_tokens,
            estimated_output_tokens=out_tokens,
            estimated_cost_usd=estimated_cost,
        )

    async def sparse_encode(self, request: InternalSparseEmbedRequest) -> InternalSparseEmbedResponse:
        await self._enforce_rate_limit("sparse_embed")
        start = time.perf_counter()
        indices, values = await self._embedder.sparse_encode(request.text)
        latency_ms = (time.perf_counter() - start) * 1000
        return InternalSparseEmbedResponse(
            indices=indices,
            values=values,
            latency_ms=round(latency_ms, 2),
        )

    async def health(self) -> bool:
        return await self._llm.health()

    async def _enforce_rate_limit(self, route_name: str) -> None:
        minute_bucket = int(time.time() // 60)
        key = RATE_KEY.format(minute_bucket=minute_bucket)
        current = await self._redis.incr(key)
        if current == 1:
            await self._redis.expire(key, 70)
        if current > self._settings.ai_inference_rate_limit_per_minute:
            logger.warning(
                "ai_inference.rate_limited",
                route=route_name,
                current=current,
                limit=self._settings.ai_inference_rate_limit_per_minute,
            )
            raise RuntimeError("AI inference rate limit exceeded")

    async def _with_retries(self, fn, *args):
        attempts = self._settings.ai_inference_retry_attempts + 1
        last_err: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await fn(*args)
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt >= attempts:
                    break
                await asyncio.sleep(0.2 * attempt)
        raise RuntimeError(f"AI inference failed after retries: {last_err}")

    def _estimate_tokens(self, text: str) -> int:
        return max(1, math.ceil(len(text or "") / 4))

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        in_cost = (
            input_tokens / 1000.0 * self._settings.ai_inference_cost_per_1k_input_tokens_usd
        )
        out_cost = (
            output_tokens
            / 1000.0
            * self._settings.ai_inference_cost_per_1k_output_tokens_usd
        )
        return round(in_cost + out_cost, 6)
