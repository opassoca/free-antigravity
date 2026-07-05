"""Provider auto-discovery and registry.

Providers register themselves using the @register_provider decorator.
The registry discovers all provider subdirectories on import.
"""

import importlib
import os
import pkgutil
from typing import Any

from loguru import logger

from providers.base import BaseProvider, ProviderConfig

# Global registry: maps provider name -> provider class
_REGISTRY: dict[str, type[BaseProvider]] = {}


def register_provider(name: str):
    """Decorator to register a provider class in the global registry.

    Usage:
        @register_provider("nvidia")
        class NvidiaProvider(BaseProvider):
            ...
    """
    def decorator(cls: type[BaseProvider]) -> type[BaseProvider]:
        if name in _REGISTRY:
            logger.warning(
                "Provider '{}' ja registrado ({}), sobrescrevendo com {}",
                name, _REGISTRY[name].__name__, cls.__name__,
            )
        _REGISTRY[name] = cls
        logger.debug("Provider '{}' registrado: {}", name, cls.__name__)
        return cls
    return decorator


def get_provider_class(name: str) -> type[BaseProvider] | None:
    """Return the provider class for a given name, or None."""
    return _REGISTRY.get(name)


def get_all_provider_classes() -> dict[str, type[BaseProvider]]:
    """Return a copy of the full provider registry."""
    return _REGISTRY.copy()


def discover_providers() -> None:
    """Auto-discover and import all provider subpackages.

    Scans the providers/ directory for subdirectories containing __init__.py
    and imports them, triggering their @register_provider decorators.
    """
    providers_dir = os.path.dirname(os.path.abspath(__file__))

    for entry in sorted(os.listdir(providers_dir)):
        entry_path = os.path.join(providers_dir, entry)
        init_path = os.path.join(entry_path, "__init__.py")

        if os.path.isdir(entry_path) and os.path.isfile(init_path):
            # Skip __pycache__ and other non-provider dirs
            if entry.startswith("_"):
                continue

            module_name = f"providers.{entry}"
            try:
                importlib.import_module(module_name)
                logger.debug("Modulo de provider descoberto: {}", module_name)
            except Exception as e:
                logger.warning(
                    "Falha ao importar provider '{}': {}",
                    module_name, e,
                )


def initialize_providers(env_overrides: dict[str, Any] | None = None) -> dict[str, BaseProvider]:
    """Instantiate all registered providers with configs from environment.

    Args:
        env_overrides: Optional dict of {provider_name: {config_key: value}}
            to override environment-based configuration.

    Returns:
        Dict mapping provider name to instantiated BaseProvider.
    """
    discover_providers()

    instances: dict[str, BaseProvider] = {}
    overrides = env_overrides or {}

    for name, cls in _REGISTRY.items():
        try:
            # Build config from provider defaults + environment
            defaults_module = None
            try:
                defaults_module = importlib.import_module(f"providers.{name}.defaults")
            except ImportError:
                pass

            config_kwargs: dict[str, Any] = {"name": name}

            # Load defaults from the provider's defaults.py if available
            if defaults_module:
                for field in ProviderConfig.model_fields:
                    default_val = getattr(defaults_module, field.upper(), None)
                    if default_val is not None:
                        config_kwargs[field] = default_val

            # Apply env overrides
            if name in overrides:
                config_kwargs.update(overrides[name])

            # Resolve API key from environment if not set
            config = ProviderConfig(**config_kwargs)
            if not config.api_key and config.env_key:
                config.api_key = os.environ.get(config.env_key, "")

            # Skip providers without API key (unless they don't need one, like ollama)
            if not config.api_key and name not in ("ollama", "llamacpp", "lmstudio"):
                logger.debug(
                    "Provider '{}' ignorado: sem API key (env: {})",
                    name, config.env_key,
                )
                continue

            instance = cls(config)
            instances[name] = instance
            logger.info(
                "Provider '{}' inicializado com sucesso | URL: {}",
                name, config.base_url,
            )

        except Exception as e:
            logger.error(
                "Erro ao inicializar provider '{}': {}",
                name, e,
            )

    return instances
