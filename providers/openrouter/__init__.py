"""OpenRouter provider implementation."""

from typing import AsyncIterator
import httpx
from loguru import logger

from providers.base import BaseProvider, ProviderConfig
from providers.registry import register_provider
from providers.openrouter.defaults import MODEL_ALIASES, EXTRA_HEADERS


@register_provider("openrouter")
class OpenRouterProvider(BaseProvider):
    """Provider for OpenRouter API."""

    async def check_health(self) -> bool:
        api_key = self.get_api_key()
        if not api_key:
            self._healthy = False
            return False
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                headers = {"Authorization": f"Bearer {api_key}"}
                headers.update(EXTRA_HEADERS)
                resp = await client.get(
                    f"{self._config.base_url}/models",
                    headers=headers,
                )
                self._healthy = resp.status_code == 200
        except Exception:
            self._healthy = False
        return self._healthy

    async def list_models(self) -> list[dict]:
        api_key = self.get_api_key()
        if not api_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                headers = {"Authorization": f"Bearer {api_key}"}
                headers.update(EXTRA_HEADERS)
                resp = await client.get(
                    self._config.models_url or f"{self._config.base_url}/models",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", [])
        except Exception as e:
            logger.error("OpenRouter list_models erro: {}", e)
        return []

    def resolve_model(self, requested: str) -> str:
        if requested in MODEL_ALIASES:
            return MODEL_ALIASES[requested]
        if not requested:
            return self._config.default_model
        return requested

    async def stream_response(
        self,
        model: str,
        openai_payload: dict,
        api_key: str,
    ) -> AsyncIterator[dict]:
        async for chunk in self._stream_openai(
            model,
            openai_payload,
            api_key,
            extra_headers=EXTRA_HEADERS,
        ):
            yield chunk
