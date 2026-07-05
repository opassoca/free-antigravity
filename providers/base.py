"""Base provider interface and configuration for free-antigravity.

Extend BaseProvider to implement a new AI provider.
Each provider lives in its own subdirectory under providers/.
"""

import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

import httpx
from loguru import logger
from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """Configuration for a provider instance.

    Base fields apply to all providers. Provider-specific parameters
    are passed via the provider's own defaults.py.
    """

    name: str = Field(description="Provider slug (e.g. 'nvidia', 'openrouter')")
    api_key: str = Field(default="", description="API key for authentication")
    base_url: str = Field(default="", description="Base URL for the provider API")
    default_model: str = Field(default="", description="Default model to use")
    rate_limit: int = Field(default=60, description="Max requests per rate window")
    rate_window: int = Field(default=60, description="Rate limit window in seconds")
    max_concurrency: int = Field(default=5, description="Max concurrent requests (semaphore)")
    timeout: float = Field(default=120.0, description="HTTP request timeout in seconds")
    env_key: str = Field(default="", description="Environment variable name for API key")
    enabled: bool = Field(default=True, description="Whether this provider is active")
    health_check_interval: int = Field(default=300, description="Seconds between health checks")
    models_url: str = Field(default="", description="URL to fetch available models list")
    prefix: str = Field(default="", description="Prefix for flattened model IDs")
    route_prefix: str = Field(default="", description="Prefix for routing (e.g. 'nvidia/')")


class QuotaInfo(BaseModel):
    """Real-time quota information for a model on a provider."""

    model: str = Field(description="Model identifier")
    provider: str = Field(description="Provider name")
    total_tokens: int = Field(default=0, description="Total tokens consumed")
    input_tokens: int = Field(default=0, description="Input tokens consumed")
    output_tokens: int = Field(default=0, description="Output tokens consumed")
    requests_count: int = Field(default=0, description="Total requests made")
    remaining_fraction: float = Field(default=1.0, description="Fraction of quota remaining (0.0-1.0)")
    quota_limit: int = Field(default=1_000_000, description="Total quota limit in tokens")
    reset_time: str = Field(default="", description="ISO 8601 time when quota resets")
    last_updated: float = Field(default_factory=time.time, description="Unix timestamp of last update")


class BaseProvider(ABC):
    """Abstract base class for all AI providers.

    Subclasses must implement:
    - check_health() -> bool
    - list_models() -> list[dict]
    - resolve_model(requested: str) -> str
    - stream_response(...) -> AsyncIterator[dict]
    """

    def __init__(self, config: ProviderConfig):
        self._config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._healthy: bool = True
        self._last_health_check: float = 0.0
        self._quota: dict[str, QuotaInfo] = {}
        logger.info(
            "Provider '{}' inicializado | URL: {} | Modelo padrao: {}",
            config.name, config.base_url, config.default_model,
        )

    @property
    def is_healthy(self) -> bool:
        """Whether the provider is currently reachable."""
        return self._healthy

    @property
    def name(self) -> str:
        """Provider slug."""
        return self._config.name

    @property
    def config(self) -> ProviderConfig:
        """Provider configuration."""
        return self._config

    async def acquire(self) -> None:
        """Acquire rate-limiting semaphore before making a request."""
        await self._semaphore.acquire()

    def release(self) -> None:
        """Release rate-limiting semaphore after a request completes."""
        self._semaphore.release()

    def get_base_url(self) -> str:
        """Return the provider's base URL."""
        return self._config.base_url

    def get_api_key(self) -> str:
        """Return the API key, falling back to environment variable."""
        key = self._config.api_key
        if not key and self._config.env_key:
            key = os.environ.get(self._config.env_key, "")
        return key

    def get_quota(self, model: str) -> QuotaInfo:
        """Return real-time quota info for a specific model."""
        if model not in self._quota:
            self._quota[model] = QuotaInfo(
                model=model,
                provider=self.name,
            )
        return self._quota[model]

    def record_usage(self, model: str, input_tokens: int, output_tokens: int) -> QuotaInfo:
        """Record token usage and update quota in real-time."""
        quota = self.get_quota(model)
        quota.input_tokens += input_tokens
        quota.output_tokens += output_tokens
        quota.total_tokens += input_tokens + output_tokens
        quota.requests_count += 1
        quota.last_updated = time.time()

        # Recalcular a fracao restante
        if quota.quota_limit > 0:
            quota.remaining_fraction = max(
                0.0,
                1.0 - (quota.total_tokens / quota.quota_limit),
            )

        logger.debug(
            "Consumo registrado: {} +{}in/+{}out | Total: {} | Restante: {:.1%}",
            model, input_tokens, output_tokens,
            quota.total_tokens, quota.remaining_fraction,
        )
        return quota

    def get_all_quotas(self) -> dict[str, QuotaInfo]:
        """Return all quota info for this provider."""
        return self._quota.copy()

    @abstractmethod
    async def check_health(self) -> bool:
        """Ping the provider to verify it is reachable.

        Returns True if healthy, False otherwise.
        Updates self._healthy internally.
        """

    @abstractmethod
    async def list_models(self) -> list[dict]:
        """List available models from the provider API.

        Returns a list of dicts with at least 'id' and optional metadata.
        """

    @abstractmethod
    def resolve_model(self, requested: str) -> str:
        """Resolve a requested model name to the actual provider model ID.

        Handles aliases, defaults, and prefix-based lookups.
        """

    @abstractmethod
    async def stream_response(
        self,
        model: str,
        openai_payload: dict,
        api_key: str,
    ) -> AsyncIterator[dict]:
        """Send request to provider and yield parsed OpenAI-compatible JSON chunks."""

    async def _stream_openai(
        self,
        model: str,
        openai_payload: dict,
        api_key: str,
        url: str | None = None,
        extra_headers: dict | None = None,
    ) -> AsyncIterator[dict]:
        """Common helper to stream requests to standard OpenAI-compatible endpoints."""
        target_url = url or f"{self.get_base_url()}/chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            headers.update(extra_headers)

        await self.acquire()
        try:
            async with httpx.AsyncClient(timeout=self._config.timeout) as client:
                async with client.stream(
                    "POST",
                    target_url,
                    json=openai_payload,
                    headers=headers,
                ) as response:
                    if response.status_code != 200:
                        err_text = await response.aread()
                        logger.error(
                            "[{}] Erro da API (HTTP {}): {}",
                            self.name, response.status_code, err_text,
                        )
                        yield {
                            "error": f"Erro da API (HTTP {response.status_code}): {err_text.decode('utf-8')}"
                        }
                        return

                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line or not line.startswith("data:"):
                                continue

                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                break

                            try:
                                yield json.loads(data_str)
                            except Exception as e:
                                logger.debug("Erro ao decodificar JSON chunk: {}", e)
        except Exception as e:
            logger.error("[{}] Erro de conexao no streaming: {}", self.name, e)
            yield {"error": f"Erro de conexao no streaming: {e}"}
        finally:
            self.release()

    async def maybe_health_check(self) -> bool:
        """Run a health check if enough time has elapsed since the last one."""
        now = time.time()
        interval = self._config.health_check_interval
        if now - self._last_health_check >= interval:
            try:
                self._healthy = await self.check_health()
            except Exception as e:
                logger.warning(
                    "Health check falhou para '{}': {}",
                    self.name, e,
                )
                self._healthy = False
            self._last_health_check = now
        return self._healthy

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} name={self.name!r} "
            f"healthy={self._healthy} url={self._config.base_url!r}>"
        )
