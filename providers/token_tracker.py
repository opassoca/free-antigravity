"""Real-time token usage tracker and quota manager.

Tracks consumption per model per provider and persists to disk.
Exposes real-time quota information for each model.
"""

import asyncio
import json
import os
import time

from loguru import logger

from providers.base import BaseProvider, QuotaInfo


class TokenTracker:
    """Centralized tracker for token usage across all providers.

    Maintains real-time quota state per model per provider and
    periodically persists to a JSON file.
    """

    def __init__(
        self,
        providers: dict[str, BaseProvider],
        stats_path: str | None = None,
        persist_interval: int = 30,
    ):
        self._providers = providers
        self._stats_path = stats_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "usage_stats.json",
        )
        self._persist_interval = persist_interval
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._running = False

        # Carregar estatisticas existentes do disco
        self._load_stats()

    def _load_stats(self) -> None:
        """Load persisted stats from disk into provider quota objects."""
        if not os.path.exists(self._stats_path):
            return

        try:
            with open(self._stats_path, "r") as f:
                data = json.load(f)

            providers_data = data.get("providers", {})
            for prov_name, models_data in providers_data.items():
                provider = self._providers.get(prov_name)
                if not provider:
                    continue

                for model_name, stats in models_data.items():
                    quota = provider.get_quota(model_name)
                    quota.input_tokens = stats.get("input_tokens", 0)
                    quota.output_tokens = stats.get("output_tokens", 0)
                    quota.total_tokens = stats.get("total_tokens", 0)
                    quota.requests_count = stats.get("requests_count", 0)
                    quota.last_updated = stats.get("last_updated", time.time())

                    if quota.quota_limit > 0:
                        quota.remaining_fraction = max(
                            0.0,
                            1.0 - (quota.total_tokens / quota.quota_limit),
                        )

            logger.info(
                "Estatisticas carregadas de {}",
                self._stats_path,
            )
        except Exception as e:
            logger.warning("Erro ao carregar estatisticas: {}", e)

    async def record_usage(
        self,
        provider_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> QuotaInfo | None:
        """Record token usage for a specific model on a provider.

        Updates the in-memory quota in real-time and returns the
        updated QuotaInfo.
        """
        provider = self._providers.get(provider_name)
        if not provider:
            logger.warning(
                "Provider '{}' nao encontrado no tracker",
                provider_name,
            )
            return None

        quota = provider.record_usage(model, input_tokens, output_tokens)

        logger.info(
            "[{}] {} | +{}in/+{}out | Total: {} | Restante: {:.1%}",
            provider_name, model,
            input_tokens, output_tokens,
            quota.total_tokens, quota.remaining_fraction,
        )

        return quota

    def get_quota(self, provider_name: str, model: str) -> QuotaInfo | None:
        """Get real-time quota info for a specific model on a provider."""
        provider = self._providers.get(provider_name)
        if not provider:
            return None
        return provider.get_quota(model)

    def get_all_quotas(self) -> dict[str, dict[str, QuotaInfo]]:
        """Get all quotas for all providers and models.

        Returns:
            {provider_name: {model_name: QuotaInfo}}
        """
        result = {}
        for name, provider in self._providers.items():
            quotas = provider.get_all_quotas()
            if quotas:
                result[name] = quotas
        return result

    def get_summary(self) -> dict:
        """Get a summary of all usage across providers and models.

        Returns a JSON-serializable dict suitable for API responses.
        """
        all_quotas = self.get_all_quotas()
        total_tokens = 0
        total_requests = 0
        providers_summary = {}

        for prov_name, models in all_quotas.items():
            prov_total = 0
            prov_requests = 0
            models_summary = {}

            for model_name, quota in models.items():
                prov_total += quota.total_tokens
                prov_requests += quota.requests_count
                models_summary[model_name] = {
                    "input_tokens": quota.input_tokens,
                    "output_tokens": quota.output_tokens,
                    "total_tokens": quota.total_tokens,
                    "requests_count": quota.requests_count,
                    "remaining_fraction": round(quota.remaining_fraction, 4),
                    "quota_limit": quota.quota_limit,
                    "last_updated": quota.last_updated,
                }

            total_tokens += prov_total
            total_requests += prov_requests
            providers_summary[prov_name] = {
                "total_tokens": prov_total,
                "requests_count": prov_requests,
                "models": models_summary,
            }

        return {
            "total_tokens_consumed": total_tokens,
            "total_requests": total_requests,
            "providers": providers_summary,
        }

    async def persist(self) -> None:
        """Persist current stats to disk."""
        async with self._lock:
            summary = self.get_summary()
            os.makedirs(os.path.dirname(self._stats_path), exist_ok=True)

            try:
                with open(self._stats_path, "w") as f:
                    json.dump(summary, f, indent=2)
                logger.debug("Estatisticas salvas em {}", self._stats_path)
            except Exception as e:
                logger.error("Erro ao salvar estatisticas: {}", e)

    async def start(self) -> None:
        """Start periodic persistence loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._persist_loop())
        logger.info(
            "TokenTracker iniciado | Persistencia a cada {}s",
            self._persist_interval,
        )

    async def stop(self) -> None:
        """Stop persistence loop and save final state."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Salvar estado final
        await self.persist()
        logger.info("TokenTracker encerrado")

    async def _persist_loop(self) -> None:
        """Internal loop that periodically saves stats."""
        while self._running:
            try:
                await asyncio.sleep(self._persist_interval)
                await self.persist()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Erro no loop de persistencia: {}", e)
