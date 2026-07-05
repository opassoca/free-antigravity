"""Gemini provider defaults."""
NAME = "gemini"
ENV_KEY = "GEMINI_API_KEY"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MODELS_URL = ""
PREFIX = "gemini-"
ROUTE_PREFIX = "gemini/"
DEFAULT_MODEL = "gemini-2.5-flash"
RATE_LIMIT = 15
MAX_CONCURRENCY = 2
TIMEOUT = 120.0
HEALTH_CHECK_INTERVAL = 300
MODEL_ALIASES = {
    "gemini-flash": "gemini-2.5-flash",
    "gemini-pro": "gemini-2.5-pro",
}
