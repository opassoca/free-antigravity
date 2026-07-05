"""DeepSeek provider defaults."""

NAME = "deepseek"
ENV_KEY = "DEEPSEEK_API_KEY"
BASE_URL = "https://api.deepseek.com/v1"
MODELS_URL = "https://api.deepseek.com/models"
PREFIX = "deepseek-"
ROUTE_PREFIX = "deepseek/"
DEFAULT_MODEL = "deepseek-reasoner"
RATE_LIMIT = 30
MAX_CONCURRENCY = 3
TIMEOUT = 120.0
HEALTH_CHECK_INTERVAL = 300

MODEL_ALIASES = {
    "deepseek-r1": "deepseek-reasoner",
    "deepseek-chat": "deepseek-chat",
    "deepseek-coder": "deepseek-coder",
}
