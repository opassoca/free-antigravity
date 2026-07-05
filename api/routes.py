import os
import json
import asyncio
import httpx
import base64
import time
import shutil
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

from loguru import logger
from config.settings import (
    PROVIDER_CONFIGS,
    NIM_MODEL,
    MOCK_EMAIL,
    MOCK_PLAN_NAME
)
from providers.manager import (
    fetch_provider_models,
    record_token_usage,
    resolve_active_provider,
    convert_gemini_to_openai,
    REVERSE_MODEL_MAP,
    start_background_tasks,
    stop_background_tasks
)

# Tentar importar de forma lazy os roteadores e runtime do free-claude-code
fcc_router = None
fcc_admin_router = None
AppRuntime = None
get_settings = None

def load_fcc_modules():
    global fcc_router, fcc_admin_router, AppRuntime, get_settings
    FCC_PATH = "/data/data/com.termux/files/home/free-claude-code"
    if not os.path.exists(FCC_PATH):
        return
        
    import sys
    orig_sys_path = sys.path.copy()
    
    # Capturar todos os modulos locais carregados que colidem com os do FCC
    fcc_keys = ["api", "config", "providers"]
    fcc_modules = {}
    for k, v in list(sys.modules.items()):
        if any(k == key or k.startswith(key + ".") for key in fcc_keys):
            fcc_modules[k] = v
            sys.modules.pop(k, None)
            
    try:
        # Remover caminhos locais do sys.path
        local_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        while local_dir in sys.path:
            sys.path.remove(local_dir)
        for p in ["", ".", "./"]:
            while p in sys.path:
                sys.path.remove(p)
                
        if FCC_PATH not in sys.path:
            sys.path.append(FCC_PATH)
            
        from api.routes import router as fcc_router
        from api.admin_routes import router as fcc_admin_router
        from api.runtime import AppRuntime
        from config.settings import get_settings
        logger.info("Modulos do Free Claude Code importados com sucesso para unificacao!")
    except Exception as e:
        logger.warning(f"Nao foi possivel importar modulos do Free Claude Code: {e}")
    finally:
        # Restaurar sys.path e sys.modules locais
        sys.path = orig_sys_path
        for k, v in fcc_modules.items():
            sys.modules[k] = v

load_fcc_modules()

# Caminhos para arquivos de credenciais do Antigravity
OAUTH_CREDS_PATH = "/data/data/com.termux/files/home/.gemini/oauth_creds.json"
ACCOUNTS_PATH = "/data/data/com.termux/files/home/.gemini/google_accounts.json"
DATA_DIR = "/data/data/com.termux/files/home/free-antigravity/data"
BACKUP_OAUTH_CREDS_PATH = os.path.join(DATA_DIR, "oauth_creds.json.bak")
BACKUP_ACCOUNTS_PATH = os.path.join(DATA_DIR, "google_accounts.json.bak")

def setup_mock_credentials():
    logger.info("Configurando credenciais mockadas para o Antigravity...")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Se ja houver backups de execucao anterior (que caiu por exemplo), restauramos antes de prosseguir
    if os.path.exists(BACKUP_ACCOUNTS_PATH) or os.path.exists(BACKUP_OAUTH_CREDS_PATH):
        logger.info("Encontrado backups de sessao anterior. Restaurando primeiro para iniciar limpo...")
        restore_original_credentials()

    # 1. Gerenciar google_accounts.json
    if os.path.exists(ACCOUNTS_PATH):
        try:
            with open(ACCOUNTS_PATH, "r") as f:
                acc_data = json.load(f)
            # Fazer backup do original
            with open(BACKUP_ACCOUNTS_PATH, "w") as f:
                json.dump(acc_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Erro ao ler/backup google_accounts.json: {e}")
            acc_data = {}
    else:
        acc_data = {}
        
    acc_data["active"] = MOCK_EMAIL
    if "old" not in acc_data:
        acc_data["old"] = []
    if MOCK_EMAIL not in acc_data["old"]:
        acc_data["old"].append(MOCK_EMAIL)
        
    try:
        os.makedirs(os.path.dirname(ACCOUNTS_PATH), exist_ok=True)
        with open(ACCOUNTS_PATH, "w") as f:
            json.dump(acc_data, f, indent=2)
        logger.info("google_accounts.json mockado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao salvar google_accounts.json mockado: {e}")

    # 2. Gerenciar oauth_creds.json
    creds_exist = os.path.exists(OAUTH_CREDS_PATH)
    creds_data = None
    if creds_exist:
        try:
            with open(OAUTH_CREDS_PATH, "r") as f:
                creds_data = json.load(f)
            # Fazer backup
            with open(BACKUP_OAUTH_CREDS_PATH, "w") as f:
                json.dump(creds_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Erro ao ler/backup oauth_creds.json: {e}")
            
    # Gerar data no futuro distante: 10 anos a partir de agora
    future_time_sec = int(time.time()) + 315360000  # 10 anos em segundos
    future_time_ms = future_time_sec * 1000
    
    # Criar payload JWT fake
    jwt_header = "eyJhbGciOiJSUzI1NiIsImtpZCI6ImQxMjk3OGJhNGMyOWVmMTE1NGEzNGU0ODcwYzdhM2E1MWQyNmRmMTAiLCJ0eXAiOiJKV1QifQ"
    jwt_payload_data = {
        "iss": "https://accounts.google.com",
        "azp": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
        "aud": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
        "sub": "115126167026707501557",
        "email": MOCK_EMAIL,
        "email_verified": True,
        "at_hash": "LVX1aKT1hxLIDvtDD00svg",
        "name": "Pacoca",
        "picture": "https://lh3.googleusercontent.com/a/ACg8ocKfYvQJBLdPrhkuR-dvy4Tb_VoGgHqUSfmXYGqpePTb3ZH6TBk=s96-c",
        "given_name": "Pacoca",
        "iat": int(time.time()) - 3600,
        "exp": future_time_sec
    }
    
    # Codificar payload em base64url sem padding
    payload_bytes = json.dumps(jwt_payload_data).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    fake_jwt = f"{jwt_header}.{payload_b64}.mock_signature"
    
    # Montar credenciais
    if not creds_data:
        creds_data = {
            "access_token": "ya29.mock_access_token_value_here",
            "refresh_token": "1//mock_refresh_token_value_here",
            "scope": "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile openid",
            "token_type": "Bearer",
        }
    
    creds_data["expiry_date"] = future_time_ms
    creds_data["id_token"] = fake_jwt
    if "access_token" not in creds_data or not creds_data["access_token"]:
        creds_data["access_token"] = "ya29.mock_access_token_value_here"
        
    try:
        os.makedirs(os.path.dirname(OAUTH_CREDS_PATH), exist_ok=True)
        with open(OAUTH_CREDS_PATH, "w") as f:
            json.dump(creds_data, f, indent=2)
        logger.info("oauth_creds.json mockado com expiracao no futuro com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao salvar oauth_creds.json mockado: {e}")

def restore_original_credentials():
    logger.info("Restaurando credenciais originais do Antigravity...")
    # Restaurar google_accounts.json
    if os.path.exists(BACKUP_ACCOUNTS_PATH):
        try:
            shutil.copy2(BACKUP_ACCOUNTS_PATH, ACCOUNTS_PATH)
            os.remove(BACKUP_ACCOUNTS_PATH)
            logger.info("google_accounts.json original restaurado.")
        except Exception as e:
            logger.error(f"Erro ao restaurar google_accounts.json: {e}")
            
    # Restaurar oauth_creds.json
    if os.path.exists(BACKUP_OAUTH_CREDS_PATH):
        try:
            shutil.copy2(BACKUP_OAUTH_CREDS_PATH, OAUTH_CREDS_PATH)
            os.remove(BACKUP_OAUTH_CREDS_PATH)
            logger.info("oauth_creds.json original restaurado.")
        except Exception as e:
            logger.error(f"Erro ao restaurar oauth_creds.json: {e}")
    else:
        # Se nao existia o original, deleta o fake
        if os.path.exists(OAUTH_CREDS_PATH):
            try:
                os.remove(OAUTH_CREDS_PATH)
                logger.info("oauth_creds.json temporario removido.")
            except Exception as e:
                logger.error(f"Erro ao remover oauth_creds.json temporario: {e}")

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Lifespan que inicializa o AppRuntime do free-claude-code se disponivel e configura conta fake."""
    setup_mock_credentials()
    await start_background_tasks()
    
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
            
    await stop_background_tasks()
    restore_original_credentials()

app = FastAPI(title="Free Antigravity API Server", lifespan=app_lifespan)

# Incluir roteadores do free-claude-code se disponiveis na mesma raiz
if fcc_router:
    app.include_router(fcc_router)
if fcc_admin_router:
    app.include_router(fcc_admin_router)

@app.post("/v1internal:onboardUser")
async def onboard_user(request: Request):
    logger.info("onboardUser chamado")
    return JSONResponse(content={
        "name": "operations/mock-onboard-op",
        "metadata": {
            "@type": "type.googleapis.com/google.internal.cloud.code.v1internal.OnboardUserOperationMetadata"
        },
        "done": True,
        "response": {
            "@type": "type.googleapis.com/google.internal.cloud.code.v1internal.OnboardUserResponse",
            "cloudaicompanionProject": "mock-project",
            "cloudaicompanion_project": "mock-project",
            "releaseChannel": "STABLE",
            "release_channel": "STABLE",
            "status": {
                "statusCode": "ACTIVE",
                "status_code": "ACTIVE",
                "displayMessage": "User onboarded successfully",
                "display_message": "User onboarded successfully"
            }
        }
    })

@app.post("/v1internal:onboardUserBackgroundTasks")
async def onboard_user_background_tasks(request: Request):
    logger.info("onboardUserBackgroundTasks chamado")
    return JSONResponse(content={})

# Endpoint mockado para simular a API do Google OAuth2 userinfo
# O binario agy faz GET https://www.googleapis.com/oauth2/v2/userinfo
# O proxy MITM intercepta essa chamada e redireciona para ca
@app.get("/oauth2/v2/userinfo")
async def google_oauth2_userinfo(request: Request):
    logger.info("Google OAuth2 userinfo mockado chamado")
    return JSONResponse(content={
        "id": "115126167026707501557",
        "email": MOCK_EMAIL,
        "verified_email": True,
        "name": "Pacoca",
        "given_name": "Pacoca",
        "picture": "https://lh3.googleusercontent.com/a/ACg8ocKfYvQJBLdPrhkuR-dvy4Tb_VoGgHqUSfmXYGqpePTb3ZH6TBk=s96-c",
        "locale": "pt-BR"
    })

@app.get("/v1internal:quotaSummary")
@app.get("/v1internal/quota")
async def get_realtime_quota_summary():
    from providers.manager import token_tracker
    logger.info("Requisicao de cota em tempo real recebida")
    return JSONResponse(content=token_tracker.get_summary())

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
    
    # Determinar displayName dinamico com base em NIM_MODEL
    active_model = NIM_MODEL
    display_name = active_model.split("/")[-1].replace("-", " ").title()
    if "deepseek-r1" in active_model.lower():
        display_name = "DeepSeek R1"
    elif "llama-3.3" in active_model.lower():
        display_name = "Llama 3.3 70B"
    elif "gemini-3.5-flash" in active_model.lower():
        display_name = "Gemini 3.5 Flash (High)"
        
    model_name = f"models/{active_model.replace('/', '-')}"
    
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
            "name": model_name,
            "displayName": display_name
        },
        "currentTier": {
            "id": "free-tier",
            "name": MOCK_PLAN_NAME,
            "description": MOCK_PLAN_NAME,
            "isDefault": True
        },
        "allowedTiers": [
            {
                "id": "free-tier",
                "name": MOCK_PLAN_NAME,
                "description": MOCK_PLAN_NAME,
                "isDefault": True
            }
        ],
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
        "email": MOCK_EMAIL,
        "displayName": "Antigravity User"
    })

@app.post("/v1internal:setUserSettings")
async def set_user_settings(request: Request):
    await log_request_details(request, "setUserSettings")
    return JSONResponse(content={})

@app.post("/v1internal:retrieveUserQuotaSummary")
async def retrieve_quota(request: Request):
    await log_request_details(request, "retrieveUserQuotaSummary")
    quota_limit = 1000000  # 1 Milhao de tokens de cota limite padrão
    consumed = 0
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    stats_path = os.path.join(base_dir, "data", "usage_stats.json")
    if os.path.exists(stats_path):
        try:
            with open(stats_path, "r") as f:
                stats = json.load(f)
                consumed = stats.get("total_tokens_consumed", 0)
        except Exception:
            pass
            
    quota_remaining = max(0, quota_limit - consumed)
    
    return JSONResponse(content={
        "quotaLimit": quota_limit,
        "quotaRemaining": quota_remaining,
        "resetTime": "2026-07-12T00:00:00Z",
        "userTier": MOCK_PLAN_NAME,
        "userTiers": [
            {
                "id": "free-tier",
                "name": MOCK_PLAN_NAME,
                "description": MOCK_PLAN_NAME,
                "isDefault": True
            }
        ]
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
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "data", "real_models_response.json")
    
    # 1. Carregar modelos estaticos originais
    data = {"models": {}}
    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            data = json.load(f)
            
    # 2. Buscar catalogo dinamico completo de todos os provedores configurados em paralelo
    providers = list(PROVIDER_CONFIGS.keys())
    tasks = [fetch_provider_models(p) for p in providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_dynamic_models = {}
    for prov_models in results:
        if isinstance(prov_models, dict) and prov_models:
            all_dynamic_models.update(prov_models)
            
    if all_dynamic_models:
        # Mesclar modelos dinamicos no inicio para maior visibilidade
        merged_models = {}
        merged_models.update(all_dynamic_models)
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
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Free Antigravity Server is running!</h1>")

@app.get("/v1internal/")
async def root_probe(request: Request):
    return JSONResponse(content={"status": "ok"})

@app.post("/v1internal:streamGenerateContent")
@app.post("/v1internal:streamGenerateChat")
@app.post("/v1internal:internalAtomicAgenticChat")
async def stream_generate_content(request: Request):
    gemini_req = await request.json()
    req_model = gemini_req.get("model", NIM_MODEL)
    logger.info(f"Recebeu requisicao de chat/stream para o modelo: {req_model}")
       # Resolver dinamicamente a instancia do provedor, a chave e o nome do modelo correto
    provider, api_key, target_model = await resolve_active_provider(request, req_model)
    
    # Converter para formato NIM/OpenAI
    nim_payload = convert_gemini_to_openai(gemini_req, target_model)
    logger.info(f"Payload convertido enviado ao provedor '{provider.name}' ({target_model}): {json.dumps(nim_payload)[:500]}...")
    
    async def event_generator() -> AsyncGenerator[str, None]:
        current_tool_calls = {}
        
        try:
            async for chunk_json in provider.stream_response(target_model, nim_payload, api_key):
                if "error" in chunk_json:
                    err_msg = chunk_json["error"]
                    logger.error(f"Erro da API do Provedor '{provider.name}': {err_msg}")
                    error_resp = {
                        "candidates": [{
                            "finishReason": "OTHER",
                            "content": {
                                "parts": [{"text": f"Erro de comunicacao com o Provedor '{provider.name}': {err_msg}"}]
                            }
                        }]
                    }
                    yield f"data: {json.dumps(error_resp)}\n\n"
                    return

                # Interceptar consumo oficial de tokens e salvar estatisticas
                usage = chunk_json.get("usage")
                if usage:
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    if prompt_tokens or completion_tokens:
                        logger.info(f"Consumo retornado pelo provedor '{provider.name}': Input={prompt_tokens}, Output={completion_tokens}")
                        await record_token_usage(target_model, prompt_tokens, completion_tokens)
                        
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
