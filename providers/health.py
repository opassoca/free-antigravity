"""Background health monitor for all registered providers.

Periodically pings each provider and marks them as healthy/unhealthy.
"""

import asyncio

from loguru import logger

from providers.base import BaseProvider


class HealthMonitor:
    """Monitors health of all providers in the background.

    Usage:
        monitor = HealthMonitor(providers_dict)
        await monitor.start()
        ...
        await monitor.stop()
    """

    def __init__(
        self,
        providers: dict[str, BaseProvider],
        interval: int = 300,
    ):
        self._providers = providers
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background health check loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "HealthMonitor iniciado | {} provedores | Intervalo: {}s",
            len(self._providers), self._interval,
        )

    async def stop(self) -> None:
        """Stop the background health check loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("HealthMonitor encerrado")

    async def _loop(self) -> None:
        """Internal loop that checks all providers periodically."""
        while self._running:
            try:
                await self.check_all()
            except Exception as e:
                logger.error("Erro no loop de health check: {}", e)
            try:
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break

    async def check_all(self) -> dict[str, bool]:
        """Check health of all providers concurrently.

        Returns dict mapping provider name to health status.
        """
        results: dict[str, bool] = {}

        async def _check_one(name: str, provider: BaseProvider) -> None:
            try:
                healthy = await provider.maybe_health_check()
                results[name] = healthy
                if not healthy:
                    logger.warning("Provider '{}' marcado como OFFLINE", name)
            except Exception as e:
                results[name] = False
                logger.warning(
                    "Health check falhou para '{}': {}",
                    name, e,
                )

        tasks = [
            _check_one(name, provider)
            for name, provider in self._providers.items()
        ]
        if tasks:
            await asyncio.gather(*tasks)

        online = sum(1 for v in results.values() if v)
        total = len(results)
        logger.debug(
            "Health check completo: {}/{} provedores online",
            online, total,
        )
        return results

    def get_status(self) -> dict[str, bool]:
        """Return current health status of all providers (non-async)."""
        return {
            name: provider.is_healthy
            for name, provider in self._providers.items()
        }

    def add_provider(self, name: str, provider: BaseProvider) -> None:
        """Add a provider to be monitored."""
        self._providers[name] = provider

    def remove_provider(self, name: str) -> None:
        """Remove a provider from monitoring."""
        self._providers.pop(name, None)
