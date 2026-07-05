"""Groq provider defaults."""
NAME = "groq"
ENV_KEY = "GROQ_API_KEY"
BASE_URL = "https://api.groq.com/openai/v1"
MODELS_URL = "https://api.groq.com/openai/v1/models"
PREFIX = "groq-"
ROUTE_PREFIX = "groq/"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
RATE_LIMIT = 30
MAX_CONCURRENCY = 3
TIMEOUT = 60.0
HEALTH_CHECK_INTERVAL = 300
MODEL_ALIASES = {
    "llama-3.3-70b": "llama-3.3-70b-versatile",
    "mixtral-8x7b": "mixtral-8x7b-32768",
}
