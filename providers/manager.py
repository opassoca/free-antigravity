"""Central orchestrator for AI providers, quotas, and health monitoring.

Coordinates the modular provider system, tracks token consumption in real-time,
and resolves routing/mapping for incoming requests.
"""

import asyncio
import os
import time
from fastapi import Request
from loguru import logger

from config.settings import PROVIDER_CONFIGS, NVIDIA_NIM_API_KEY, NIM_MODEL, CACHE_TTL
from providers.base import BaseProvider
from providers.registry import initialize_providers
from providers.health import HealthMonitor
from providers.token_tracker import TokenTracker
from providers.converter import convert_gemini_to_openai

# Inicializacao global de todos os provedores modulares ativos
providers: dict[str, BaseProvider] = initialize_providers()

# Inicializacao do Monitor de Saude e Tracker de Tokens em tempo real
health_monitor = HealthMonitor(providers, interval=300)
token_tracker = TokenTracker(providers)

# Cache global de modelos para manter compatibilidade com routes.py
DYNAMIC_PROVIDERS_CACHE: dict[str, dict] = {}
REVERSE_MODEL_MAP: dict[str, str] = {}
CACHE_TIMESTAMPS: dict[str, float] = {}


async def start_background_tasks() -> None:
    """Inicia as tarefas de segundo plano (health check e persistencia)."""
    await health_monitor.start()
    await token_tracker.start()
    logger.info("Tarefas de segundo plano dos provedores iniciadas.")


async def stop_background_tasks() -> None:
    """Finaliza as tarefas de segundo plano salvando o estado final."""
    await health_monitor.stop()
    await token_tracker.stop()
    logger.info("Tarefas de segundo plano dos provedores finalizadas.")


async def fetch_provider_models(provider_name: str) -> dict:
    """Atualiza e retorna a lista de modelos dinamicos de um provedor específico."""
    global DYNAMIC_PROVIDERS_CACHE, REVERSE_MODEL_MAP, CACHE_TIMESTAMPS

    provider = providers.get(provider_name)
    cfg = PROVIDER_CONFIGS.get(provider_name)
    if not provider or not cfg:
        return {}

    # Verificar TTL do cache local
    now = time.time()
    last_update = CACHE_TIMESTAMPS.get(provider_name, 0.0)
    if provider_name in DYNAMIC_PROVIDERS_CACHE and (now - last_update) < CACHE_TTL:
        return DYNAMIC_PROVIDERS_CACHE[provider_name]

    try:
        logger.info("Atualizando cache do provedor '{}' via list_models()...", provider_name)
        models_list = await provider.list_models()
        
        dynamic_dict = {}
        counter = 300 + (list(PROVIDER_CONFIGS.keys()).index(provider_name) * 200)

        for m in models_list:
            if not isinstance(m, dict):
                continue
            orig_id = m.get("id")
            if not orig_id:
                continue

            # Gerar ID achatado amigavel
            flat_id = orig_id.replace("/", "-").replace("_", "-").replace(".", "-").lower()
            if not flat_id.startswith(cfg["prefix"]):
                flat_id = f"{cfg['prefix']}{flat_id}"

            # Mapeamento reverso para roteamento
            REVERSE_MODEL_MAP[flat_id] = f"{cfg['route_prefix']}{orig_id}"

            # Nome exibido amigavel
            friendly_name = orig_id.split("/")[-1].replace("-", " ").replace("_", " ").title()
            display_name = f"{friendly_name} (via {provider_name.upper()})"

            supports_thinking = (
                "reason" in orig_id.lower() or 
                "deepseek-r1" in orig_id.lower() or 
                "thinking" in orig_id.lower()
            )
            supports_images = (
                "vision" in orig_id.lower() or 
                "vl" in orig_id.lower() or 
                "multimodal" in orig_id.lower()
            )

            # Obter quota em tempo real do tracker
            quota = token_tracker.get_quota(provider_name, flat_id)
            remaining = quota.remaining_fraction if quota else 1.0

            dynamic_dict[flat_id] = {
                "displayName": display_name,
                "supportsImages": supports_images,
                "supportsThinking": supports_thinking,
                "recommended": False,
                "maxTokens": 16384,
                "maxOutputTokens": 4096,
                "tokenizerType": "LLAMA_WITH_SPECIAL",
                "quotaInfo": {
                    "remainingFraction": remaining,
                    "resetTime": "2026-07-12T00:00:00Z"
                },
                "model": f"MODEL_PLACEHOLDER_DP{counter}",
                "apiProvider": "API_PROVIDER_GOOGLE_GEMINI",
                "modelProvider": "MODEL_PROVIDER_GOOGLE"
            }
            counter += 1

        DYNAMIC_PROVIDERS_CACHE[provider_name] = dynamic_dict
        CACHE_TIMESTAMPS[provider_name] = now
        logger.info("Carregados {} modelos dinamicos do provedor '{}' com sucesso!", len(dynamic_dict), provider_name)
        return dynamic_dict

    except Exception as e:
        logger.error("Excecao ao carregar modelos de '{}': {}", provider_name, e)

    return DYNAMIC_PROVIDERS_CACHE.get(provider_name, {})


async def record_token_usage(model_name: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Registra o consumo de tokens no tracker global em tempo real (compatibilidade com routes.py)."""
    # Mapear o model_name (ex: deepseek-ai/deepseek-r1 ou nvidia-deepseek-ai-deepseek-r1)
    # para encontrar o provedor correto
    provider_name = "nvidia"
    flat_model = model_name

    # Extrair provedor se estiver no formato achatado (ex: nvidia-...)
    for p, provider_obj in providers.items():
        prefix = provider_obj.config.prefix
        if prefix and model_name.startswith(prefix):
            provider_name = p
            flat_model = model_name
            break

    await token_tracker.record_usage(provider_name, flat_model, prompt_tokens, completion_tokens)


async def resolve_active_provider(request: Request, default_model: str) -> tuple[BaseProvider | None, str, str]:
    """Resolve dinamicamente a instancia do provedor, chave e modelo com base nas envs e headers."""
    # Traduzir o modelo solicitado baseado em mapeamento das variaveis de ambiente
    if default_model:
        env_key = f"MODEL_MAP_{default_model.upper().replace('-', '_').replace('.', '_')}"
        mapped_model = os.environ.get(env_key)
        if mapped_model:
            logger.info("Mapeamento de modelo via ENV ({}): {} -> {}", env_key, default_model, mapped_model)
            default_model = mapped_model

    # Ler cabecalho de autenticacao para verificar override de provedor/modelo
    auth_header = (
        request.headers.get("x-api-key")
        or request.headers.get("authorization")
        or request.headers.get("anthropic-auth-token")
        or ""
    )
    
    token = auth_header.strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        
    model_override = None
    if token and ":" in token:
        parts = token.split(":", 1)
        token = parts[0].strip()
        model_override = parts[1].strip()
        logger.info("Override de modelo detectado no cabecalho: {}", model_override)

    target_model = model_override or default_model
    
    # Se o modelo solicitado for um modelo nativo do cliente agy (ex: gemini-3-flash-agent), limpamos para usar o padrao do provedor
    if target_model and "/" not in target_model and any(kw in target_model.lower() for kw in ("gemini", "code-assist", "bison", "agent", "flash")):
        target_model = ""

    # Atualizar cache do provedor se for modelo dinamico nao encontrado
    if target_model:
        matched_provider = None
        for p, provider_obj in providers.items():
            prefix = provider_obj.config.prefix
            if prefix and target_model.startswith(prefix):
                matched_provider = p
                break
        if matched_provider and target_model not in REVERSE_MODEL_MAP:
            logger.info("Modelo dinamico '{}' nao encontrado no cache. Atualizando provedor '{}'...", target_model, matched_provider)
            await fetch_provider_models(matched_provider)

    # Se o modelo solicitado estiver no mapeamento reverso dinamico, traduzi-lo de volta
    if target_model in REVERSE_MODEL_MAP:
        target_model = REVERSE_MODEL_MAP[target_model]
        logger.info("Resolvendo modelo dinamico: {}", target_model)
        
    # Fallbacks nativos (sem provider explicitado)
    NATIVE_FALLBACKS = {
        "deepseek-v4-pro": "nvidia/deepseek-ai/deepseek-v4-pro",
        "deepseek-v4-flash": "nvidia/deepseek-ai/deepseek-v4-flash",
        "llama-3-1-nemotron-70b-instruct": "nvidia/nvidia/llama-3.1-nemotron-70b-instruct",
        "llama-3-3-70b-instruct": "nvidia/meta/llama-3.3-70b-instruct",
        "gemma-4-31b-it": "nvidia/google/gemma-4-31b-it",
        "gemma-3-12b-it": "nvidia/google/gemma-3-12b-it",
        "mistral-large-3-675b": "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
        "qwen-3-5-397b": "nvidia/qwen/qwen3.5-397b-a17b"
    }
    if target_model in NATIVE_FALLBACKS:
        target_model = NATIVE_FALLBACKS[target_model]
    
    # Extrair provedor e nome do modelo no formato provider/model_name
    provider_name = "nvidia"
    model_name = target_model
    
    if "/" in target_model:
        parts = target_model.split("/", 1)
        provider_name = parts[0]
        model_name = parts[1]

    # Obter instancia modular do provedor correspondente
    provider = providers.get(provider_name)
    if not provider:
        # Fallback de seguranca caso o provedor nao esteja ativo ou configurado
        logger.warning("Provider '{}' nao esta ativo. Usando NVIDIA como fallback.", provider_name)
        provider = providers.get("nvidia")
        provider_name = "nvidia"
        model_name = target_model

    if provider:
        api_key = provider.get_api_key() or token
        resolved_model = provider.resolve_model(model_name)
        logger.info("Provedor resolvido: {} | Model: {}", provider_name, resolved_model)
        return provider, api_key, resolved_model

    # Caso nao consiga resolver de nenhuma forma
    nvidia_prov = providers.get("nvidia")
    return nvidia_prov, token or NVIDIA_NIM_API_KEY, NIM_MODEL
