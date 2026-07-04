# Claude-Gemini Bridge: Setup e Arquitetura

Este documento detalha o ecossistema criado para rodar o Claude Code CLI utilizando a API do Google Gemini, falsificando o endpoint da Anthropic.

## 1. Componentes Principais

### `claude-bridge` (Localizado em `~/bin/`)
- **Função**: Servidor proxy FastAPI que emula a API da Anthropic (`/v1/messages`).
- **TUI**: Interface `curses` que aparece ao iniciar para seleção do modelo Gemini (Flash, Pro, etc).
- **Tradução**: Converte `tool_use`/`tool_result` do Claude para `functionCall`/`functionResponse` do Gemini.
- **Segurança**: Injeta uma `ANTHROPIC_API_KEY` fictícia para contornar a validação do Claude CLI.

### `gemini-auth` & `gemini-sync-daemon.py`
- Gerenciam a troca de contas Google e a renovação de tokens OAuth em segundo plano.
- O daemon captura quotas em tempo real e salva no `quota_cache.json`, usado pelo bridge para mostrar o status.

## 2. Fluxo de Instalação (`install.sh`)
O instalador segue a lógica de "consumo de backup":
1. Move o binário de `~/gemini_bridge_backup/bin/` para `~/bin/`.
2. Instala dependências: `pip install fastapi uvicorn requests python-dotenv`.
3. Garante que o Claude Code esteja presente via NPM.
4. Configura o alias `claude='claude-bridge'` no `.bashrc`.
5. **Auto-limpeza**: Deleta a pasta `~/gemini_bridge_backup/` após a conclusão.
6. **Auto-refresh**: Executa `exec bash` para ativar o alias instantaneamente.

## 3. Variáveis de Ambiente Críticas
- `ANTHROPIC_BASE_URL`: Redirecionada para `http://127.0.0.1:8082`.
- `GEMINI_API_KEY`: Usada pelo bridge para autenticar no Google.
- `GEMINI_AUTH_MODE`: Define se está usando `OAUTH` ou `API_KEY`.

## 4. Troubleshooting
- Se o Claude der erro 400 em ferramentas: O Bridge traduz IDs de chamadas de função concatenando o nome (ex: `call_123_ls`).
- Se a cota bater 100%: Verifique o Reset Time no menu `auth` (TAB).
