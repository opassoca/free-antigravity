# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2026-07-05
### Fixed
- Fixed a crash in the `agy` (Antigravity CLI) Go client caused by unwrapped SSE chunks: streamed responses are now enveloped in `{"response": {...}}` to match the internal `streamGenerateContentFromCCPA` format the client expects, eliminating a nil-pointer panic on the first streamed text chunk.
- Replaced `response.iter_text()` with `response.aiter_text()` in `providers/base.py` for correct async streaming iteration.
- Fixed `TokenTracker` to read the nested `models` key from persisted usage stats and skip malformed entries, preventing crashes when loading quota data.
### Added
- Added `/internal/agy-session-start` and `/internal/agy-session-end` endpoints for explicit mock/restore of Google credentials, decoupled from the FastAPI app lifespan.
- Added automatic mock OAuth token responses for token/oauth refresh routes, keeping `agy` sessions alive without real Google credentials.
- Added pre-flight/warm-up request handling in `stream_generate_content`, returning an immediate empty mock chunk when `contents` is empty.
- Added a final `STOP` chunk with `usageMetadata` at the end of every stream to prevent client-side crashes on stream close.
- `mitm_proxy.py` now also intercepts `oauth2.googleapis.com`.
### Changed
- Default NIM model changed from the deprecated `deepseek-ai/deepseek-r1` to `deepseek-ai/deepseek-v4-pro` across settings, provider aliases, `.env.example`, and model maps.
- `install.sh` now tracks and kills proxy/MITM processes by their captured PIDs instead of `pgrep` pattern matching, and starts both with `python -u` and stdin redirected from `/dev/null` to avoid orphaned or blocking background processes.

## [1.3.0] - 2026-07-05
### Added
- Modularized provider system under `providers/` sub-packages, implementing the provider registry and decorator auto-discovery patterns (inspired by `free-claude-code`).
- Created dedicated providers for NVIDIA NIM, OpenRouter, DeepSeek, Mistral, Groq, Google Gemini (via API key), and Ollama.
- Introduced `HealthMonitor` for background health checks and offline provider recovery.
- Re-architected `TokenTracker` to support real-time token tracking and quota limit fraction calculations per model and provider.
- Added `/v1internal/quota` and `/v1internal:quotaSummary` endpoints to expose real-time quota status.
- Implemented `stream_response` inside each provider, encapsulating network streaming, error parsing, and rate-limit semaphore tracking inside the provider classes themselves.
- Unified the logging system to use `loguru` consistently across the entire project.
- Updated `install.sh` to configure the correct latest robust wrapper executable.

## [1.2.0] - 2026-07-05
### Added
- Created `docs/TECHNICAL_GUIDE.md`, consolidating all architectural blueprints, reverse-engineered protocol mappings, mock credential JSON structures, CLI footer custom configs, and cache implementations in a unified documentation file.
- Linked the technical guide from the main English and Portuguese READMEs.

## [1.1.0] - 2026-07-05
### Added
- Implemented automated fake Google credentials simulation (`oauth_creds.json` and `google_accounts.json`) in Python lifespan hooks, bypassing onboarding and "account provisioning" errors in `agy`.
- Built robust automatic file backup and restoration mechanism to clean up simulated credentials when the proxy shuts down or is stopped.

## [1.0.0] - 2026-07-05
### Added
- Created `pyproject.toml` to manage project packaging, metadata, and official versioning.
### Changed
- Complete refactoring and modularization of the project architecture. Fragmented the monolithic `free-antigravity.py` into specialized Python packages:
  - `config/settings.py`: Environment variable loading, logging, and global settings configuration.
  - `providers/manager.py`: Provider catalog metadata retrieval, API format adapters (Gemini contents to OpenAI Delta), provider routing, and token usage accounting.
  - `api/routes.py`: FastAPI application configuration, lifecycle hooks, and endpoints.
- Simplified `free-antigravity.py` to act solely as a lightweight entrypoint.

## [0.4.0] - 2026-07-04
### Added
- Integrated actual token consumption tracking for streaming responses by extracting `prompt_tokens` and `completion_tokens`.
- Created localized `data/usage_stats.json` file storage to persist cumulative token consumption.
- Implemented real quota deduction on the `/v1internal:retrieveUserQuotaSummary` endpoint.
### Changed
- Translated all README files to Portuguese, Spanish, Russian, and Chinese.

## [0.3.0] - 2026-07-04
### Added
- Implemented dynamic provider model querying to automatically merge provider catalogs (NVIDIA NIM, OpenRouter, Groq, Mistral, DeepSeek) into the available models response.
- Created cached TTL mechanism (5 minutes) for fetched provider models to ensure zero latency on UI loads.
- Implemented reverse model mapping logic to translate flattened IDs (e.g. `groq-llama-3-3-70b`) back to original route formats transparently.

## [0.2.0] - 2026-07-04
### Added
- Integrated 8 NVIDIA NIM models to the CLI selector with native fallbacks.
- Integrated automatic displayName renaming in CLI based on `MODEL_MAP_*` environment variables.

## [0.1.0] - 2026-07-03
### Changed
- Refactored API header resolution to read `x-api-key` in format `KEY:PROVIDER/MODEL` for dynamic provider switching.

## [0.0.1] - 2026-07-01
### Added
- Initial release of the unified zero-gravity AI proxy.
