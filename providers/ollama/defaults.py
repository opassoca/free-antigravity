"""Ollama provider defaults (local)."""
NAME = "ollama"
ENV_KEY = ""  # Ollama nao precisa de API key
BASE_URL = "http://localhost:11434/v1"
MODELS_URL = "http://localhost:11434/api/tags"
PREFIX = "ollama-"
ROUTE_PREFIX = "ollama/"
DEFAULT_MODEL = "deepseek-r1"
RATE_LIMIT = 999
MAX_CONCURRENCY = 2
TIMEOUT = 300.0
HEALTH_CHECK_INTERVAL = 60
MODEL_ALIASES = {}
