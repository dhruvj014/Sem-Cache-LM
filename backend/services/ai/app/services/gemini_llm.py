from __future__ import annotations

import httpx

from shared.config.settings import Settings
from shared.domain.model_providers import LLMClient
from shared.observability.logger import get_logger
from shared.observability.metrics import LLM_LATENCY

logger = get_logger(__name__)

GEMINI_REST_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _extract_generated_text(data: dict) -> str:
    cands = data.get("candidates") or []
    if not cands:
        return ""
    parts = (
        (cands[0].get("content") or {}).get("parts") or []
    )
    texts: list[str] = []
    for p in parts:
        if isinstance(p, dict) and p.get("text"):
            texts.append(str(p["text"]))
    return "".join(texts).strip()


class GeminiLLMClient(LLMClient):
    """Gemini text generation via Google AI REST (`generateContent`)."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http = http_client
        self._model = settings.gemini_llm_model

    async def generate(self, prompt: str, system: str | None = None) -> str:
        api_key = (self._settings.gemini_api_key or "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        url = f"{GEMINI_REST_BASE}/models/{self._model}:generateContent"
        body: dict = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]},
            ],
        }
        if system and system.strip():
            body["systemInstruction"] = {"parts": [{"text": system.strip()}]}

        timeout = float(self._settings.gemini_timeout_seconds)
        with LLM_LATENCY.labels(call_type="infer").time():
            try:
                resp = await self._http.post(
                    url,
                    headers={"x-goog-api-key": api_key},
                    json=body,
                    timeout=timeout,
                )
            except httpx.RequestError as e:
                raise RuntimeError(
                    "Cannot reach Google Gemini API (HTTPS to generativelanguage.googleapis.com). "
                    "Check outbound HTTPS/DNS from this host or Docker, VPN/firewall, "
                    "and HTTP_PROXY/HTTPS_PROXY when behind a proxy. "
                    f"Underlying error: {e}"
                ) from e
        resp.raise_for_status()
        data = resp.json()
        text = _extract_generated_text(data)
        if not text:
            logger.warning("gemini.generate_empty_text", model=self._model)
        return text

    async def health(self) -> bool:
        api_key = (self._settings.gemini_api_key or "").strip()
        if not api_key:
            return False
        try:
            url = f"{GEMINI_REST_BASE}/models"
            resp = await self._http.get(
                url,
                headers={"x-goog-api-key": api_key},
                params={"pageSize": 1},
                timeout=10.0,
            )
            return resp.status_code == 200
        except httpx.RequestError as e:
            logger.warning(
                "gemini.health_failed_unreachable",
                error=str(e),
                hint="Outbound HTTPS to generativelanguage.googleapis.com failed; check Docker "
                "network/DNS, VPN, or HTTP_PROXY/HTTPS_PROXY.",
            )
            return False
        except Exception as e:  # noqa: BLE001
            logger.warning("gemini.health_failed", error=str(e))
            return False
