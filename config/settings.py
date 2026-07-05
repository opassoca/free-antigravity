import os
import sys
import logging
from dotenv import load_dotenv

# Carregar configuracoes locais do proprio .env se disponivel na raiz do script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

# Chaves API e URLs padrao obtidas do .env
NVIDIA_NIM_API_KEY = os.environ.get("NVIDIA_NIM_API_KEY", "")
NIM_MODEL = os.environ.get("NIM_MODEL", "deepseek-ai/deepseek-r1")
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Cache TTL
CACHE_TTL = 300  # 5 minutos de TTL

# Configuracoes de provedores suportados para busca automatica de modelos
PROVIDER_CONFIGS = {
    "nvidia": {
        "env_key": "NVIDIA_NIM_API_KEY",
        "url": "https://integrate.api.nvidia.com/v1/models",
        "prefix": "nvidia-",
        "route_prefix": "nvidia/"
    },
    "openrouter": {
        "env_key": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/api/v1/models",
        "prefix": "openrouter-",
        "route_prefix": "openrouter/"
    },
    "deepseek": {
        "env_key": "DEEPSEEK_API_KEY",
        "url": "https://api.deepseek.com/models",
        "prefix": "deepseek-",
        "route_prefix": "deepseek/"
    },
    "groq": {
        "env_key": "GROQ_API_KEY",
        "url": "https://api.groq.com/openai/v1/models",
        "prefix": "groq-",
        "route_prefix": "groq/"
    },
    "mistral": {
        "env_key": "MISTRAL_API_KEY",
        "url": "https://api.mistral.ai/v1/models",
        "prefix": "mistral-",
        "route_prefix": "mistral/"
    }
}
