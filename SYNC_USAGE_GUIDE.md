# SYNC Ecosystem: Master Usage & Technical Guide

## 1. Comandos Rápidos (O Arsenal)
- **`auth`**: Abre o painel TUI (Ncurses) para trocar de conta/chave.
  - *Uso:* `auth` (O wrapper no `.bashrc` já faz o `eval`).
- **`oauth`**: Atalho para autenticação de novas contas Google.
- **`agy3`**: Motor de proxy/túnel para o CLI oficial.
- **`gemini-switcher`**: Seletor rápido de modelos e contas via linha de comando.

## 2. Atalhos do Painel `auth`
| Tecla | Ação |
| :--- | :--- |
| `↑↓` | Navegação entre contas/chaves. |
| `◄►` | Alterna entre modo **OAUTH** e **API KEYS**. |
| `ENTER` | Ativa a conta/chave e sincroniza com o motor oficial. |
| `TAB` | Janela de detalhes: Cotas e tempo de reset por modelo. |
| `N` | Renomeia o apelido (Nick) da conta selecionada. |
| `O` | Altera a ordenação (Alfabética / Ativa no topo). |
| `I` | Inverte a ordem da lista. |
| `ESC` | Sai do painel sem alterar nada. |

## 3. Comandos do Sistema (Referência Rápida)
- **Root:** `su -c "<comando>"` (Usa o namespace master).
- **Android UI:** `cmd activity <acao>` (Interage com apps e sistema).
- **Wi-Fi:** `cmd wifi status` ou `cmd wifi list-scan-results`.
- **Navegador:** `termux-open <url>` (Agora funcionando com a correção das variáveis `ANDROID_*`).

## 4. Arquitetura Técnica (Para IAs e Curiosos)
- **Daemon:** O `gemini-sync-daemon.py` roda em background cuidando do cache de cotas.
- **Integridade:** `ANDROID_ROOT=/system` e `ANDROID_DATA=/data` são OBRIGATÓRIOS.
- **Logs:** Auditoria em `~/.antigravity-auth/auth.log`. Se algo quebrar, olhe lá primeiro.
- **Fim da Linha:** O motor CLI oficial morre em 18/06/2026. Preparar para o **Agentic 2.0**.

---
*Este documento foi consolidado pela Velha Ácida em 16/06/2026. Leia e não faça pergunta idiota.*
