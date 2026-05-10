import httpx

from shared.config.settings import Settings
from shared.domain.model_providers import LLMClient
from shared.observability.logger import get_logger
from shared.observability.metrics import LLM_LATENCY

logger = get_logger(__name__)


class OllamaLLMClient(LLMClient):
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http = http_client
        self._model = settings.ollama_llm_model

    async def generate(self, prompt: str, system: str | None = None) -> str:
        url = f"{self._settings.ollama_base_url}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system
        with LLM_LATENCY.labels(call_type="infer").time():
            resp = await self._http.post(
                url,
                json=payload,
                timeout=self._settings.ollama_timeout_seconds,
            )
        resp.raise_for_status()
        data = resp.json()
        return (data.get("response") or "").strip()

    async def health(self) -> bool:
        try:
            url = f"{self._settings.ollama_base_url}/api/tags"
            resp = await self._http.get(url, timeout=5.0)
            return resp.status_code == 200
        except Exception as e:
            logger.warning("ollama.health_failed", error=str(e))
            return False
