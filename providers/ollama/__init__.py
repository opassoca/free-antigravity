"""Ollama provider implementation (local)."""
import os
from typing import AsyncIterator
import httpx
from loguru import logger
from providers.base import BaseProvider
from providers.registry import register_provider
from providers.ollama.defaults import MODEL_ALIASES

@register_provider("ollama")
class OllamaProvider(BaseProvider):
    """Provider for local Ollama instance."""

    def get_base_url(self) -> str:
        env_url = os.environ.get("OLLAMA_BASE_URL", "").rstrip("/")
        if env_url:
            return f"{env_url}/v1"
        return self._config.base_url

    def get_api_key(self) -> str:
        return "ollama"

    async def check_health(self) -> bool:
        try:
            base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{base}/api/tags")
                self._healthy = resp.status_code == 200
        except Exception:
            self._healthy = False
        return self._healthy

    async def list_models(self) -> list[dict]:
        try:
            base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("models", [])
                    return [{"id": m.get("name", "")} for m in models]
        except Exception as e:
            logger.debug("Ollama list_models (local nao disponivel): {}", e)
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
        # Ollama local endpoint
        async for chunk in self._stream_openai(model, openai_payload, api_key):
            yield chunk
