"""OpenRouter provider defaults."""

NAME = "openrouter"
ENV_KEY = "OPENROUTER_API_KEY"
BASE_URL = "https://openrouter.ai/api/v1"
MODELS_URL = "https://openrouter.ai/api/v1/models"
PREFIX = "openrouter-"
ROUTE_PREFIX = "openrouter/"
DEFAULT_MODEL = "google/gemini-2.5-pro"
RATE_LIMIT = 60
MAX_CONCURRENCY = 5
TIMEOUT = 120.0
HEALTH_CHECK_INTERVAL = 300

MODEL_ALIASES = {
    "gemini-2.5-pro": "google/gemini-2.5-pro",
    "claude-4-sonnet": "anthropic/claude-4-sonnet",
    "gpt-4.1": "openai/gpt-4.1",
}

# Headers extras requeridos pelo OpenRouter
EXTRA_HEADERS = {
    "HTTP-Referer": "https://github.com/opassoca/free-antigravity",
    "X-Title": "Free Antigravity Proxy",
}
