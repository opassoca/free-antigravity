"""NVIDIA NIM provider defaults."""

# Provider identity
NAME = "nvidia"
ENV_KEY = "NVIDIA_NIM_API_KEY"
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODELS_URL = "https://integrate.api.nvidia.com/v1/models"
PREFIX = "nvidia-"
ROUTE_PREFIX = "nvidia/"

# Default model
DEFAULT_MODEL = "deepseek-ai/deepseek-v4-pro"

# Rate limiting
RATE_LIMIT = 60
MAX_CONCURRENCY = 5
TIMEOUT = 120.0

# Health check
HEALTH_CHECK_INTERVAL = 300

# Model aliases: map friendly names to actual NIM model IDs
MODEL_ALIASES = {
    "deepseek-r1": "deepseek-ai/deepseek-v4-pro",
    "deepseek-v4-pro": "deepseek-ai/deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek-ai/deepseek-v4-flash",
    "llama-3.3-70b": "meta/llama-3.3-70b-instruct",
    "llama-3.1-nemotron-70b": "nvidia/llama-3.1-nemotron-70b-instruct",
    "gemma-4-31b": "google/gemma-4-31b-it",
    "gemma-3-12b": "google/gemma-3-12b-it",
    "mistral-large-3": "mistralai/mistral-large-3-675b-instruct-2512",
    "qwen-3.5-397b": "qwen/qwen3.5-397b-a17b",
}
