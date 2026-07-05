"""Gemini provider implementation (via Google AI API key)."""
from typing import AsyncIterator
import httpx
from loguru import logger
from providers.base import BaseProvider
from providers.registry import register_provider
from providers.gemini.defaults import MODEL_ALIASES

@register_provider("gemini")
class GeminiProvider(BaseProvider):
    """Provider for Google Gemini via API key (generativelanguage.googleapis.com)."""

    async def check_health(self) -> bool:
        api_key = self.get_api_key()
        if not api_key:
            self._healthy = False
            return False
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    f"{self._config.base_url}/models?key={api_key}",
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
                resp = await client.get(
                    f"{self._config.base_url}/models?key={api_key}",
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("models", [])
        except Exception as e:
            logger.error("Gemini list_models erro: {}", e)
        return []

    def resolve_model(self, requested: str) -> str:
        if requested in MODEL_ALIASES:
            return MODEL_ALIASES[requested]
        return requested or self._config.default_model

    async def stream_response(
        self,
        model: str,
        openai_payload: dict,
        api_key: str,
    ) -> AsyncIterator[dict]:
        # Gemini's OpenAI-compatible endpoint requires the api_key in query params
        gemini_openai_url = f"{self.get_base_url()}/chat/completions?key={api_key}"
        async for chunk in self._stream_openai(
            model,
            openai_payload,
            api_key="", # Pass empty string because api_key is in the query params
            url=gemini_openai_url,
        ):
            yield chunk
