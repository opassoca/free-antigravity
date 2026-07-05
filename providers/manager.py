import os
import json
import time
import asyncio
import httpx
from fastapi import Request

from config.settings import (
    logger,
    PROVIDER_CONFIGS,
    NVIDIA_NIM_API_KEY,
    NIM_MODEL,
    NIM_BASE_URL,
    CACHE_TTL
)

# Cache global para modelos dinamicos mapeados por provedor
DYNAMIC_PROVIDERS_CACHE = {}  # ex: {"nvidia": {...}, "openrouter": {...}}
REVERSE_MODEL_MAP = {}       # ex: {"nvidia-google-gemma-4-31b-it": "nvidia/google/gemma-4-31b-it"}
CACHE_TIMESTAMPS = {}

# Lock para evitar condicoes de corrida ao gravar estatisticas de cota/tokens
stats_lock = asyncio.Lock()

async def fetch_provider_models(provider_name: str) -> dict:
    global DYNAMIC_PROVIDERS_CACHE, REVERSE_MODEL_MAP, CACHE_TIMESTAMPS
    
    cfg = PROVIDER_CONFIGS.get(provider_name)
    if not cfg:
        return {}
        
    api_key = os.environ.get(cfg["env_key"]) or (NVIDIA_NIM_API_KEY if provider_name == "nvidia" else "")
    
    # Tentar ler do free-claude-code env importado se nao estiver local
    get_settings_fn = None
    try:
        from api.routes import get_settings as get_settings_fn
    except ImportError:
        pass
        
    if not api_key and get_settings_fn:
        try:
            settings = get_settings_fn()
            api_key = getattr(settings, cfg["env_key"].lower(), "")
        except Exception:
            pass
            
    if not api_key:
        DYNAMIC_PROVIDERS_CACHE.pop(provider_name, None)
        return {}
        
    # Verificar TTL do cache
    now = time.time()
    last_update = CACHE_TIMESTAMPS.get(provider_name, 0)
    if provider_name in DYNAMIC_PROVIDERS_CACHE and (now - last_update) < CACHE_TTL:
        return DYNAMIC_PROVIDERS_CACHE[provider_name]
        
    url = cfg["url"]
    headers = {"Authorization": f"Bearer {api_key}"}
    if provider_name == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/opassoca/free-antigravity"
        headers["X-Title"] = "Free Antigravity Proxy"

    try:
        logger.info(f"Atualizando cache do provedor '{provider_name}' de {url}...")
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models_list = data.get("data", [])
                if not isinstance(models_list, list):
                    models_list = data if isinstance(data, list) else []
                    
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
                    
                    # Nome amigavel
                    provider_tag = provider_name.upper()
                    friendly_name = orig_id.split("/")[-1].replace("-", " ").replace("_", " ").title()
                    display_name = f"{friendly_name} (via {provider_tag})"
                    
                    supports_thinking = "reason" in orig_id.lower() or "deepseek-r1" in orig_id.lower() or "thinking" in orig_id.lower()
                    supports_images = "vision" in orig_id.lower() or "vl" in orig_id.lower() or "multimodal" in orig_id.lower()
                    
                    dynamic_dict[flat_id] = {
                        "displayName": display_name,
                        "supportsImages": supports_images,
                        "supportsThinking": supports_thinking,
                        "recommended": False,
                        "maxTokens": 16384,
                        "maxOutputTokens": 4096,
                        "tokenizerType": "LLAMA_WITH_SPECIAL",
                        "quotaInfo": {
                            "remainingFraction": 1,
                            "resetTime": "2026-07-11T23:03:30Z"
                        },
                        "model": f"MODEL_PLACEHOLDER_DP{counter}",
                        "apiProvider": "API_PROVIDER_GOOGLE_GEMINI",
                        "modelProvider": "MODEL_PROVIDER_GOOGLE"
                    }
                    counter += 1
                
                DYNAMIC_PROVIDERS_CACHE[provider_name] = dynamic_dict
                CACHE_TIMESTAMPS[provider_name] = now
                logger.info(f"Carregados {len(dynamic_dict)} modelos dinamicos do provedor '{provider_name}' com sucesso!")
                return dynamic_dict
            else:
                logger.error(f"Erro ao buscar modelos de '{provider_name}': {resp.status_code}")
    except Exception as e:
        logger.error(f"Excecao ao carregar modelos de '{provider_name}': {e}")
        
    return DYNAMIC_PROVIDERS_CACHE.get(provider_name, {})

async def record_token_usage(model_name: str, prompt_tokens: int, completion_tokens: int):
    """Grava o consumo real de tokens das chamadas em arquivo JSON para contagem de cota."""
    global stats_lock
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    stats_dir = os.path.join(base_dir, "data")
    os.makedirs(stats_dir, exist_ok=True)
    stats_path = os.path.join(stats_dir, "usage_stats.json")
    
    async with stats_lock:
        stats = {"total_tokens_consumed": 0, "models": {}}
        if os.path.exists(stats_path):
            try:
                with open(stats_path, "r") as f:
                    stats = json.load(f)
            except Exception:
                pass
                
        total = prompt_tokens + completion_tokens
        stats["total_tokens_consumed"] = stats.get("total_tokens_consumed", 0) + total
        
        models_data = stats.setdefault("models", {})
        model_stats = models_data.setdefault(model_name, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
        
        model_stats["input_tokens"] += prompt_tokens
        model_stats["output_tokens"] += completion_tokens
        model_stats["total_tokens"] += total
        
        try:
            with open(stats_path, "w") as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Consumo registrado: +{total} tokens para {model_name}. Acumulado: {stats['total_tokens_consumed']}")
        except Exception as e:
            logger.error(f"Erro ao salvar estatisticas de consumo: {e}")

async def resolve_active_provider(request: Request, default_model: str) -> tuple[str, str, str]:
    """Resolve dinamicamente a base_url, api_key e model com base nas envs e headers."""
    # Traduzir o modelo solicitado baseado em mapeamento das variaveis de ambiente (MODEL_MAP_...)
    if default_model:
        env_key = f"MODEL_MAP_{default_model.upper().replace('-', '_').replace('.', '_')}"
        mapped_model = os.environ.get(env_key)
        if mapped_model:
            logger.info(f"Mapeamento de modelo via ENV ({env_key}): {default_model} -> {mapped_model}")
            default_model = mapped_model

    # Ler cabecalho de autenticacao para verificar se o usuario embutiu o provedor/modelo
    # Formato suportado: x-api-key: SUA_CHAVE:PROVEDOR/MODELO
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
        # O token real fica na primeira parte
        token = parts[0].strip()
        model_override = parts[1].strip()
        logger.info(f"Override de modelo detectado no cabecalho: {model_override}")

    # Determinar qual o modelo a ser usado (do payload da request, override de cabecalho ou default_model)
    target_model = model_override or default_model
    
    # Se o modelo solicitado comecar com o prefixo de algum provedor e nao estiver mapeado, tentar forcar a atualizacao
    if target_model:
        matched_provider = None
        for p, cfg in PROVIDER_CONFIGS.items():
            if target_model.startswith(cfg["prefix"]):
                matched_provider = p
                break
        if matched_provider and target_model not in REVERSE_MODEL_MAP:
            logger.info(f"Modelo dinamico '{target_model}' nao encontrado no cache. Atualizando provedor '{matched_provider}'...")
            await fetch_provider_models(matched_provider)

    # Se o modelo solicitado estiver no mapeamento reverso dinamico, traduzi-lo de volta
    if target_model in REVERSE_MODEL_MAP:
        original_mapped = REVERSE_MODEL_MAP[target_model]
        logger.info(f"Resolvendo modelo dinamico: {target_model} -> {original_mapped}")
        target_model = original_mapped
        
    # Mapeamento de fallbacks nativos para os 8 modelos customizados caso selecionados sem provider
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
    
    # Extrair provedor e nome do modelo a partir do formato provider/model_name
    provider = "nvidia_nim"
    model_name = target_model
    
    if "/" in target_model:
        parts = target_model.split("/", 1)
        provider = parts[0]
        model_name = parts[1]
        
    # Resolver configuracoes baseado no provedor determinado
    base_url = NIM_BASE_URL
    api_key = NVIDIA_NIM_API_KEY
    
    if provider == "nvidia_nim":
        base_url = "https://integrate.api.nvidia.com/v1"
        api_key = os.environ.get("NVIDIA_NIM_API_KEY", "") or token
        # Se for nemotron (padrao do fcc), substituir por deepseek r1 para melhor qualidade de resposta
        if "nemotron" in model_name or not model_name:
            model_name = "deepseek-ai/deepseek-r1"
            
    elif provider == "open_router" or provider == "openrouter":
        base_url = "https://openrouter.ai/api/v1"
        api_key = os.environ.get("OPENROUTER_API_KEY", "") or token
        if not model_name or model_name == target_model:
            model_name = "google/gemini-2.5-pro"
            
    elif provider == "deepseek":
        base_url = "https://api.deepseek.com/v1"
        api_key = os.environ.get("DEEPSEEK_API_KEY", "") or token
        if not model_name or model_name == target_model:
            model_name = "deepseek-reasoner"
            
    elif provider == "mistral":
        base_url = "https://api.mistral.ai/v1"
        api_key = os.environ.get("MISTRAL_API_KEY", "") or token
        if not model_name or model_name == target_model:
            model_name = "codestral-latest"
            
    elif provider == "groq":
        base_url = "https://api.groq.com/openai/v1"
        api_key = os.environ.get("GROQ_API_KEY", "") or token
        if not model_name or model_name == target_model:
            model_name = "llama-3.3-70b-versatile"
            
    elif provider == "gemini":
        base_url = "https://generativelanguage.googleapis.com/v1beta"
        api_key = os.environ.get("GEMINI_API_KEY", "") or token
        
    elif provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/v1"
        api_key = "ollama"
        if not model_name or model_name == target_model:
            model_name = "deepseek-r1"
            
    # Se nao casou com nenhum, tenta usar as chaves configuradas na env diretamente
    else:
        # Se comecar com a chave NIM
        if token.startswith("nvapi-") or NVIDIA_NIM_API_KEY:
            base_url = "https://integrate.api.nvidia.com/v1"
            api_key = NVIDIA_NIM_API_KEY or token
            model_name = target_model
        else:
            # Fallback generico
            base_url = "https://integrate.api.nvidia.com/v1"
            api_key = token or NVIDIA_NIM_API_KEY
            model_name = target_model

    logger.info(f"Provedor resolvido: {provider} | Base URL: {base_url} | Model: {model_name}")
    return base_url, api_key, model_name

def convert_gemini_to_openai(gemini_request: dict, target_model: str) -> dict:
    """Converte a chamada de API do Gemini para o formato da API OpenAI."""
    openai_messages = []
    
    # 1. Traduzir o historico de mensagens (contents)
    contents = gemini_request.get("contents", [])
    for content in contents:
        role = content.get("role")
        openai_role = "user" if role == "user" else "assistant"
        
        parts = content.get("parts", [])
        text_content = ""
        tool_calls = []
        
        for part in parts:
            if "text" in part:
                text_content += part["text"]
            elif "functionCall" in part:
                fcall = part["functionCall"]
                tool_calls.append({
                    "id": fcall.get("name"),
                    "type": "function",
                    "function": {
                        "name": fcall.get("name"),
                        "arguments": json.dumps(fcall.get("args", {}))
                    }
                })
            elif "functionResponse" in part:
                fresp = part["functionResponse"]
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": fresp.get("name"),
                    "content": json.dumps(fresp.get("response", {}))
                })
                
        if text_content or tool_calls:
            msg = {"role": openai_role}
            if text_content:
                msg["content"] = text_content
            if tool_calls:
                msg["tool_calls"] = tool_calls
            openai_messages.append(msg)
            
    # 2. Traduzir as declaracoes de ferramentas (tools)
    openai_tools = []
    if "tools" in gemini_request:
        for tool_group in gemini_request["tools"]:
            if "functionDeclarations" in tool_group:
                for decl in tool_group["functionDeclarations"]:
                    params = decl.get("parameters", {}).copy()
                    
                    def convert_types(schema):
                        if not isinstance(schema, dict):
                            return
                        if "type" in schema:
                            schema["type"] = schema["type"].lower()
                        if "properties" in schema:
                            for k, v in schema["properties"].items():
                                convert_types(v)
                                
                    convert_types(params)
                    
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": decl.get("name"),
                            "description": decl.get("description", ""),
                            "parameters": params
                        }
                    })
                    
    # Construir o corpo final para a OpenAI
    openai_payload = {
        "model": target_model,
        "messages": openai_messages,
        "stream": True,
        "stream_options": {"include_usage": True}
    }
    
    if openai_tools:
        openai_payload["tools"] = openai_tools
        
    # Mapear configuracoes extras de geracao
    gen_config = gemini_request.get("generationConfig", {})
    if "temperature" in gen_config:
        openai_payload["temperature"] = gen_config["temperature"]
    if "maxOutputTokens" in gen_config:
        openai_payload["max_tokens"] = gen_config["maxOutputTokens"]
        
    return openai_payload
