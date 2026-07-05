# Gemini Auth Ecosystem - Documentação Técnica

Este documento descreve a arquitetura e operação do sistema de alternância de identidade e gestão de cotas para o Gemini CLI no Termux.

## Arquitetura do Sistema

O ecossistema é composto por dois componentes principais que operam em harmonia para garantir performance e persistência.

### 1. Gemini Sync Daemon (`gemini-sync-daemon.py`)
O "coração" lógico do sistema, rodando em background.
- **Função**: Monitora tokens OAUTH, renova sessões expiradas e centraliza a busca de cotas.
- **Quota Cache**: Utiliza a API `retrieveUserQuota` em lote para evitar limites de taxa (Rate Limiting).
- **Localização**: `~/bin/gemini-sync-daemon.py`
- **Dados**: Alimenta o arquivo `~/.gemini-switch/quota_cache.json`.

### 2. Gemini Auth TUI (`gemini-auth`)
A interface visual para o usuário.
- **Tecnologia**: Python Ncurses (TUI).
- **Injeção de Sessão**: Utiliza o padrão `eval "$(gemini-auth)"` para modificar variáveis de ambiente (`GEMINI_API_KEY`) no shell pai.
- **Isolamento de FD**: Redireciona via Kernel (os.dup2) o FD 1 para o FD 2 durante a execução para garantir que o `eval` capture apenas o comando final e não os artefatos visuais da interface.
- **Cores Sóbrias**: Design otimizado para Termux com fundo transparente e cores não-agressivas.

## Comandos e Atalhos no Painel

- **Setas ↑↓**: Navegação entre contas/chaves.
- **Setas ◄►**: Alterna entre modo **OAUTH** (Contas Google) e **API KEYS**.
- **ENTER**: Ativa a conta selecionada e fecha o painel.
- **TAB**: Abre janela de detalhes com tempo de reset por modelo.
- **R**: Renomeia o "Nick" da conta selecionada.
- **O**: Altera o modo de ordenação (Alfabética ou Ativa no Topo).
- **ESC**: Sai sem realizar alterações.

## Novidades da Versão 2026 (Refactor Opus)
- **Zero Latency**: O painel abre instantaneamente pois não faz requisições de rede (consome o cache do Daemon).
- **Calculo de Cota de Alta Precisão**: Utiliza `remainingFraction` para exibir porcentagem real de uso.
- **Blindagem de Terminal**: Sistema de recuperação de FD que impede erros de sintaxe no Bash ao sair do painel.
- **Multi-Model Sync**: Sincronização automática entre o cache de cotas e as configurações do Gemini CLI.

## Localização de Arquivos (Base: `~/.gemini-switch/`)
- `google_accounts.json`: Índice de contas vinculadas.
- `api_keys.json`: Dicionário de chaves de API manuais.
- `id-tokens/`: Armazenamento seguro de tokens de acesso individuais.
- `quota_cache.json`: Cache centralizado de uso da API.
