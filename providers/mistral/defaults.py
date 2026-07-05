"""Mistral AI provider defaults."""
NAME = "mistral"
ENV_KEY = "MISTRAL_API_KEY"
BASE_URL = "https://api.mistral.ai/v1"
MODELS_URL = "https://api.mistral.ai/v1/models"
PREFIX = "mistral-"
ROUTE_PREFIX = "mistral/"
DEFAULT_MODEL = "codestral-latest"
RATE_LIMIT = 30
MAX_CONCURRENCY = 3
TIMEOUT = 120.0
HEALTH_CHECK_INTERVAL = 300
MODEL_ALIASES = {
    "codestral": "codestral-latest",
    "mistral-large": "mistral-large-latest",
    "mistral-medium": "mistral-medium-latest",
}
