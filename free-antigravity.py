import os
import sys
import json
import logging
import asyncio
import httpx
from typing import Any, AsyncGenerator
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

# Carregar configuracoes locais do proprio .env se disponivel na raiz do script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_ENV_PATH = os.path.join(BASE_DIR, ".env")
if os.path.exists(LOCAL_ENV_PATH):
    load_dotenv(LOCAL_ENV_PATH)

# Adicionar pasta do free-claude-code ao path do sistema para importar seus modulos
FCC_PATH = "/data/data/com.termux/files/home/free-claude-code"
if FCC_PATH not in sys.path:
    sys.path.append(FCC_PATH)

# Carregar configuracoes do free-claude-code .env se disponivel como fallback
FCC_ENV_PATH = os.path.join(FCC_PATH, ".env")
if os.path.exists(FCC_ENV_PATH):
    load_dotenv(FCC_ENV_PATH)

# Configurar Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("FreeAntigravity")

# Tentar importar os roteadores e runtime do free-claude-code para unificar os proxies
fcc_router = None
fcc_admin_router = None
AppRuntime = None
get_settings = None

try:
    from api.routes import router as fcc_router
    from api.admin_routes import router as fcc_admin_router
    from api.runtime import AppRuntime
    from config.settings import get_settings
    logger.info("Modulos do Free Claude Code importados com sucesso para unificacao!")
except Exception as e:
    logger.warning(f"Nao foi possivel importar modulos do Free Claude Code: {e}")

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Lifespan que inicializa o AppRuntime do free-claude-code se disponivel."""
    runtime = None
    if AppRuntime and get_settings:
        try:
            settings = get_settings()
            runtime = AppRuntime.for_app(app, settings=settings)
            await runtime.startup()
            logger.info("AppRuntime do Free Claude Code iniciado com sucesso no lifespan!")
        except Exception as e:
            logger.error(f"Erro ao iniciar AppRuntime no lifespan: {e}")
            
    yield
    
    if runtime:
        try:
            await runtime.shutdown()
            logger.info("AppRuntime do Free Claude Code finalizado com sucesso no lifespan.")
        except Exception as e:
            logger.error(f"Erro ao finalizar AppRuntime no lifespan: {e}")

app = FastAPI(title="Free Antigravity API Server", lifespan=app_lifespan)

# Incluir roteadores do free-claude-code se disponiveis na mesma raiz
if fcc_router:
    app.include_router(fcc_router)
if fcc_admin_router:
    app.include_router(fcc_admin_router)

# Chaves API e URLs padrao obtidas do .env
NVIDIA_NIM_API_KEY = os.environ.get("NVIDIA_NIM_API_KEY", "")
NIM_MODEL = os.environ.get("NIM_MODEL", "deepseek-ai/deepseek-r1")
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Cache global para modelos dinamicos obtidos de APIs de provedores
DYNAMIC_MODELS_CACHE = {}
# Mapeamento reverso global de IDs achatados para os IDs originais com provedores
REVERSE_MODEL_MAP = {}

async def fetch_nvidia_nim_models() -> dict:
    global DYNAMIC_MODELS_CACHE, REVERSE_MODEL_MAP
    if DYNAMIC_MODELS_CACHE:
        return DYNAMIC_MODELS_CACHE

    api_key = os.environ.get("NVIDIA_NIM_API_KEY") or NVIDIA_NIM_API_KEY
    if not api_key:
        logger.warning("NVIDIA_NIM_API_KEY nao encontrada ao buscar modelos dinamicos.")
        return {}

    url = f"{NIM_BASE_URL}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        logger.info(f"Buscando catalogo completo de modelos da NVIDIA NIM de {url}...")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models_list = data.get("data", [])
                dynamic_dict = {}
                counter = 200
                for m in models_list:
                    orig_id = m.get("id")
                    if not orig_id:
                        continue
                    # Gerar um ID achatado e limpo (ex: "nvidia/google/gemma-4-31b-it" -> "nvidia-google-gemma-4-31b-it")
                    # Para compatibilidade com a CLI (que nao aceita barras nos IDs de modelo)
                    flat_id = orig_id.replace("/", "-").replace("_", "-").replace(".", "-").lower()
                    if not flat_id.startswith("nvidia-"):
                        flat_id = f"nvidia-{flat_id}"
                    
                    # Mapeamento reverso para roteamento posterior
                    REVERSE_MODEL_MAP[flat_id] = f"nvidia/{orig_id}"
                    
                    # Formatar nome amigavel
                    provider_part = orig_id.split("/")[0].upper() if "/" in orig_id else "NVIDIA"
                    model_name = orig_id.split("/")[-1].replace("-", " ").replace("_", " ").title()
                    display_name = f"{model_name} (via {provider_part})"
                    
                    # Determinar suporte a pensamento/imagens a partir do ID
                    supports_thinking = "reason" in orig_id.lower() or "deepseek-r1" in orig_id.lower()
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
                        "model": f"MODEL_PLACEHOLDER_D{counter}",
                        "apiProvider": "API_PROVIDER_GOOGLE_GEMINI",
                        "modelProvider": "MODEL_PROVIDER_GOOGLE"
                    }
                    counter += 1
                
                DYNAMIC_MODELS_CACHE = dynamic_dict
                logger.info(f"Carregados {len(dynamic_dict)} modelos dinamicos da NVIDIA NIM com sucesso!")
                return DYNAMIC_MODELS_CACHE
            else:
                logger.error(f"Erro ao buscar modelos da NVIDIA NIM: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Excecao ao buscar modelos da NVIDIA NIM: {e}")
    return {}

if not NVIDIA_NIM_API_KEY:
    logger.warning("NVIDIA_NIM_API_KEY nao configurada no .env!")

@app.post("/v1internal:onboardUser")
async def onboard_user(request: Request):
    logger.info("onboardUser chamado")
    return JSONResponse(content={})

async def log_request_details(request: Request, endpoint_name: str):
    """Log detalhado de headers e body para debug."""
    headers_dict = dict(request.headers)
    content_type = headers_dict.get("content-type", "NONE")
    accept = headers_dict.get("accept", "NONE")
    logger.info(f"[{endpoint_name}] Content-Type: {content_type} | Accept: {accept}")
    logger.info(f"[{endpoint_name}] All headers: {headers_dict}")
    raw_body = await request.body()
    logger.info(f"[{endpoint_name}] Raw body ({len(raw_body)} bytes): {raw_body[:500]}")
    try:
        body_json = json.loads(raw_body) if raw_body else {}
        logger.info(f"[{endpoint_name}] Parsed JSON body: {json.dumps(body_json, indent=2)[:1000]}")
    except Exception:
        logger.info(f"[{endpoint_name}] Body is NOT JSON")
    return raw_body

@app.post("/v1internal:loadCodeAssist")
async def load_code_assist(request: Request):
    await log_request_details(request, "loadCodeAssist")
    return JSONResponse(content={
        "userSettings": {
            "telemetryEnabled": True
        },
        "userTierId": "free-tier",
        "modelConfigId": "default-config",
        "disableTelemetry": False,
        "disableFeedback": False,
        "disableCitations": False,
        "model": {
            "name": "models/gemini-3.5-flash",
            "displayName": "Gemini 3.5 Flash (High)"
        },
        "experiments": []
    })

@app.post("/v1internal:fetchAdminControls")
async def fetch_admin_controls(request: Request):
    await log_request_details(request, "fetchAdminControls")
    return JSONResponse(content={})

@app.post("/v1internal:fetchUserInfo")
async def fetch_user_info(request: Request):
    await log_request_details(request, "fetchUserInfo")
    return JSONResponse(content={
        "email": "euodeioodiabo@gmail.com",
        "displayName": "Antigravity User"
    })

@app.post("/v1internal:setUserSettings")
async def set_user_settings(request: Request):
    await log_request_details(request, "setUserSettings")
    return JSONResponse(content={})

@app.post("/v1internal:retrieveUserQuotaSummary")
async def retrieve_quota(request: Request):
    await log_request_details(request, "retrieveUserQuotaSummary")
    return JSONResponse(content={
        "quotaLimit": 100000,
        "quotaRemaining": 100000,
        "resetTime": "2026-07-06T00:00:00Z"
    })

@app.post("/v1internal:listExperiments")
async def list_experiments(request: Request):
    await log_request_details(request, "listExperiments")
    return JSONResponse(content={
        "experimentIds": [],
        "experiments": [],
        "flags": []
    })

@app.post("/v1internal:fetchAvailableModels")
async def fetch_models(request: Request):
    await log_request_details(request, "fetchAvailableModels")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "data", "real_models_response.json")
    
    # 1. Carregar modelos estaticos originais
    data = {"models": {}}
    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            data = json.load(f)
            
    # 2. Buscar catalogo dinâmico completo da NVIDIA NIM
    nim_models = await fetch_nvidia_nim_models()
    if nim_models:
        # Mesclar modelos dinamicos no inicio para maior visibilidade
        merged_models = {}
        merged_models.update(nim_models)
        merged_models.update(data.get("models", {}))
        data["models"] = merged_models
        
    # 3. Patch dinâmico: renomear displayName dos modelos baseado em MODEL_MAP_* do .env
    models = data.get("models", {})
    for model_id, model_info in models.items():
        env_key = f"MODEL_MAP_{model_id.upper().replace('-', '_').replace('.', '_')}"
        mapped_target = os.environ.get(env_key)
        if mapped_target and "displayName" in model_info:
            # Extrair nome legivel do modelo mapeado (ex: "nvidia/deepseek-ai/deepseek-v4-pro" -> "DeepSeek V4 Pro")
            raw_name = mapped_target.split("/")[-1]  # pega o ultimo segmento
            friendly_name = raw_name.replace("-", " ").replace("_", " ").title()
            original_name = model_info["displayName"]
            model_info["displayName"] = f"{friendly_name} (via {mapped_target.split('/')[0].upper()})"
            logger.info(f"Patch displayName: '{original_name}' -> '{model_info['displayName']}' (ENV: {env_key})")
            
    return JSONResponse(content=data)

@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Free Antigravity Server is running!</h1>")

@app.get("/v1internal/")
async def root_probe(request: Request):
    return JSONResponse(content={"status": "ok"})

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
    
    # Se o modelo solicitado comecar com o prefixo do provedor e nao estiver mapeado, tentar forcar a atualizacao do catalogo
    if target_model and target_model.startswith("nvidia-") and target_model not in REVERSE_MODEL_MAP:
        logger.info(f"Modelo dinamico '{target_model}' nao encontrado no cache. Atualizando catalogo de modelos...")
        await fetch_nvidia_nim_models()

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
        base_url = "https://generativelanguage.googleapis.com/v1beta" # Exige payload diferente, tratar se necessario
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
        "stream": True
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

@app.post("/v1internal:streamGenerateContent")
@app.post("/v1internal:streamGenerateChat")
@app.post("/v1internal:internalAtomicAgenticChat")
async def stream_generate_content(request: Request):
    gemini_req = await request.json()
    req_model = gemini_req.get("model", NIM_MODEL)
    logger.info(f"Recebeu requisicao de chat/stream para o modelo: {req_model}")
    
    # Resolver dinamicamente a URL base, a chave e o nome do modelo correto
    base_url, api_key, target_model = await resolve_active_provider(request, req_model)
    
    # Converter para formato NIM/OpenAI
    nim_payload = convert_gemini_to_openai(gemini_req, target_model)
    logger.info(f"Payload convertido enviado ao provedor ({target_model}): {json.dumps(nim_payload)[:500]}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    async def event_generator() -> AsyncGenerator[str, None]:
        client = httpx.AsyncClient(timeout=120.0)
        current_tool_calls = {}
        
        try:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                json=nim_payload,
                headers=headers
            ) as response:
                
                if response.status_code != 200:
                    err_text = await response.aread()
                    logger.error(f"Erro da API do Provedor (HTTP {response.status_code}): {err_text}")
                    error_resp = {
                        "candidates": [{
                            "finishReason": "OTHER",
                            "content": {
                                "parts": [{"text": f"Erro de comunicacao com o Provedor: {err_text.decode('utf-8')}"}]
                            }
                        }]
                    }
                    yield f"data: {json.dumps(error_resp)}\n\n"
                    return

                buffer = ""
                async for chunk in response.iter_text():
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
                            chunk_json = json.loads(data_str)
                            choices = chunk_json.get("choices", [])
                            if not choices:
                                continue
                                
                            delta = choices[0].get("delta", {})
                            
                            # 1. Tratar conteudo de texto normal
                            text_content = delta.get("content", "")
                            reasoning = delta.get("reasoning_content", "")
                            
                            if reasoning:
                                text_content = reasoning
                                
                            if text_content:
                                gemini_chunk = {
                                    "candidates": [{
                                        "content": {
                                            "role": "model",
                                            "parts": [{"text": text_content}]
                                        }
                                    }]
                                }
                                yield f"data: {json.dumps(gemini_chunk)}\n\n"
                                
                            # 2. Tratar chamadas de ferramentas (tool_calls)
                            tool_deltas = delta.get("tool_calls", [])
                            for td in tool_deltas:
                                index = td.get("index", 0)
                                if index not in current_tool_calls:
                                    current_tool_calls[index] = {
                                        "name": "",
                                        "arguments": ""
                                    }
                                    
                                func_delta = td.get("function", {})
                                if "name" in func_delta:
                                    current_tool_calls[index]["name"] = func_delta["name"]
                                if "arguments" in func_delta:
                                    current_tool_calls[index]["arguments"] += func_delta["arguments"]
                                    
                        except Exception as e:
                            logger.error(f"Erro ao parsear chunk: {e} na linha {line}")
                            
            # Enviar todas as chamadas de ferramentas acumuladas de uma vez
            for idx, call in current_tool_calls.items():
                try:
                    args = json.loads(call["arguments"]) if call["arguments"] else {}
                except Exception:
                    args = {"raw_arguments": call["arguments"]}
                    
                logger.info(f"Modelo executando ferramenta: {call['name']} com {args}")
                gemini_tool_chunk = {
                    "candidates": [{
                        "content": {
                            "role": "model",
                            "parts": [{
                                "functionCall": {
                                    "name": call["name"],
                                    "args": args
                                }
                            }]
                        }
                    }]
                }
                yield f"data: {json.dumps(gemini_tool_chunk)}\n\n"
                
        except Exception as e:
            logger.error(f"Erro no stream do proxy: {e}")
            error_resp = {
                "candidates": [{
                    "finishReason": "OTHER",
                    "content": {
                        "parts": [{"text": f"Erro de processamento no Proxy: {str(e)}"}]
                    }
                }]
            }
            yield f"data: {json.dumps(error_resp)}\n\n"
        finally:
            await client.aclose()
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
async def catch_all(request: Request, path: str):
    logger.warning(f"CATCH-ALL: Rota nao mapeada acessada: {request.method} /{path} com params: {request.query_params}")
    try:
        body = await request.json()
        logger.warning(f"CATCH-ALL BODY: {body}")
    except Exception:
        body = await request.body()
        logger.warning(f"CATCH-ALL RAW BODY: {body}")
    return JSONResponse(content={})

if __name__ == "__main__":
    import uvicorn
    # Rodar localmente na porta 8084
    uvicorn.run(app, host="127.0.0.1", port=8084, log_level="info")
