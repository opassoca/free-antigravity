"""Providers package — modular AI provider system for free-antigravity.

Each provider lives in its own subdirectory and registers itself
automatically via the @register_provider decorator.

Usage:
    from providers.registry import initialize_providers
    providers = initialize_providers()
"""

from providers.base import BaseProvider, ProviderConfig, QuotaInfo
from providers.registry import (
    discover_providers,
    get_all_provider_classes,
    get_provider_class,
    initialize_providers,
    register_provider,
)

__all__ = [
    "BaseProvider",
    "ProviderConfig",
    "QuotaInfo",
    "discover_providers",
    "get_all_provider_classes",
    "get_provider_class",
    "initialize_providers",
    "register_provider",
]
