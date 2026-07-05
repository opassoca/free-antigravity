# 🛰️ Free Antigravity — Technical Architecture & Guide

Welcome to the central technical guide for **Free Antigravity**, a high-performance unified proxy designed to connect **Antigravity CLI (agy)** and **Claude Code** to any AI provider (NVIDIA NIM, OpenRouter, DeepSeek, Mistral, Groq, Ollama) with dynamic key resolution, simulated credentials authentication, and a zero-gravity Matter.js dashboard.

---

## 📌 Architectural Blueprint

Free Antigravity unifies two distinct AI client systems onto a single local port (`8084`):

```
                       ┌──────────────────────┐
                       │    Antigravity CLI   │
                       │     (Go Client)      │
                       └──────────┬───────────┘
                                  │ (FastAPI /v1internal:*)
                                  ▼
┌──────────────────┐   ┌──────────────────────┐   ┌─────────────────────┐
│    Claude Code   ├──►│ Free Antigravity     ├──►│ Active Provider API │
│  (Node.js CLI)   │   │ (Port 8084 Proxy)    │   │ (OpenAI Protocol)   │
└──────────────────┘   └──────────┬───────────┘   └─────────────────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │ usage_stats.json     │
                       └──────────────────────┘
```

1. **FastAPI Server (`api/routes.py`):** Acts as the ingress gateway. It serves both the legacy Google/Gemini protobuf-based endpoints (`/v1internal:*`) and the standard OpenAI chat completions endpoint (`/v1/messages`).
2. **Configuration Settings (`config/settings.py`):** Parses the `.env` settings, handles global application properties, and sets up centralized logging.
3. **Provider Engine (`providers/manager.py`):** Houses adapters that dynamically fetch third-party catalogs, translate prompt messages to target APIs, handle content streaming mapping (e.g., mapping Gemini stream structures to standard delta chunks), and calculate runtime token metrics.

---

## 🔑 Authentication & Simulated Google Login

One of the most complex challenges was bypassing the **"account under provisioning / not logged in"** check in the `agy` Go client binary. The binary checks local credentials stored under the user's home directory.

### Credential Backup & Injection Cycle
Free Antigravity automates this cycle in a non-destructive manner via FastAPI Lifespan hooks:

1. **Path Mapping:**
   - `oauth_creds.json` located at `~/.gemini/oauth_creds.json`.
   - `google_accounts.json` located at `~/.gemini/google_accounts.json`.
   
2. **FastAPI Lifespan Startup (`setup_mock_credentials`):**
   - The original credential files are backed up locally to `data/*.json.bak` in the project directory.
   - If backups exist from a prior crashed run, they are restored first to guarantee a clean start.
   - A mock `google_accounts.json` is generated, setting the `"active"` user email to `MOCK_EMAIL` (defaulting to `euodeioodiabo@gmail.com` or custom).
   - An expired `oauth_creds.json` triggers login blocks. The proxy injects a fake credential JSON with `expiry_date` set to **10 years in the future** (calculated via `time.time() + 315360000`).
   - A fake `id_token` JWT payload is encoded with the matching simulated email to bypass client validation checks.

3. **FastAPI Lifespan Shutdown (`restore_original_credentials`):**
   - When the proxy shuts down, the backup files are restored to their original locations.
   - Temporary files created by the proxy are deleted safely.

---

## 🎨 CLI Footer Customization

The footer printed by the `agy` CLI during initialization takes the following shape:

```
     ▀▀▀▀▀▀       zetdarkmint@gmail.com (Antigravity Starter Quota)
    ▀▀▀▀▀▀▀▀      Gemini 3.5 Flash (High)
   ▄▀▀    ▀▀▄     ~
```

These values are supplied dynamically by Free Antigravity endpoints:

1. **Email Display:** Read from the `fetchUserInfo` endpoint response (`"email"` field) and the simulated JWT token. Customized by `MOCK_EMAIL` in `.env`.
2. **Quota / Plan Name:** The string inside the parentheses is read from the `currentTier.name` field of the `loadCodeAssist` response, and also supplied in `retrieveUserQuotaSummary`. Customized by `MOCK_PLAN_NAME` in `.env`.
3. **Active Model Display Name:** Extracted from the `model.displayName` field of the `loadCodeAssist` response. The proxy dynamically infers the model selected as `NIM_MODEL` inside `.env` and returns a corresponding display name (e.g., `DeepSeek R1` or `Llama 3.3 70B`).

---

## 🔍 Protocol Mappings

The CLI relies on proprietary Google developer APIs, which we intercept and map:

* **`/v1internal:onboardUser`:** Invoked on startup to register the active tier (e.g. `free-tier`). We return an empty JSON `{}`.
* **`/v1internal:loadCodeAssist`:** Determines user settings, active tier configurations, and default model displays.
* **`/v1internal:fetchUserInfo`:** Supplies simulated email and name.
* **`/v1internal:retrieveUserQuotaSummary`:** Serves quota bounds (`quotaLimit`) and deducts consumed token stats dynamically.
* **`/v1internal:fetchAvailableModels`:** Returns the unified model list. The Go client maps flat string IDs to routing backends.
* **`/v1internal:streamGenerateContent` / `streamGenerateChat`:** Renders chat generation streams, rewritten from the Gemini protocols into the unified OpenAI provider schema.

---

## 🧠 Model Discovery & Catalog Cache

To prevent slow startup latencies when starting the CLI:

1. **Multi-Catalog Querying:** The proxy queries the catalog endpoints of configured providers concurrently.
2. **TTL Cache:** Fetched model lists are cached in memory for **5 minutes** (300s TTL). This ensures that calls to `fetchAvailableModels` respond in milliseconds while keeping the catalog fresh.
3. **Flat ID Aliases:** Because the CLI parses string IDs, we flatten complex nested paths (e.g., `nvidia-deepseek-ai-deepseek-v4-pro`). Upon chat request, these are resolved back to `nvidia/deepseek-ai/deepseek-v4-pro` dynamically.

---

## 📊 Usage Metrics & Persisted Quotas

To track consumption and enforce limits locally:

* Stream chunk chunks are analyzed to extract `prompt_tokens` and `completion_tokens` values.
* Consumption stats are appended in real-time to `data/usage_stats.json`.
* The quota endpoint `retrieveUserQuotaSummary` reads this JSON, subtracts consumed values from a starting balance of **1,000,000 tokens**, and reports the remaining quota to the client.
