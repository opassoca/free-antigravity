# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
