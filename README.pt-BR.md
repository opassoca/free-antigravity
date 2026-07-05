# 🌌 Free Antigravity — Proxy de IA Unificado de Gravidade Zero

🌎 **Escolha seu idioma:**
[English](README.md) | [Português](README.pt-BR.md) | [Español](README.es.md) | [Русский](README.ru.md) | [中文](README.zh.md)

---

Um proxy unificado de alta performance projetado para conectar o **Antigravity CLI (agy)** e o **Claude Code** a qualquer provedor de IA (Nvidia NIM, OpenRouter, DeepSeek, Mistral, Groq, Ollama) com resolução dinâmica de chaves e um dashboard interativo com física de gravidade zero.

---

## ⚡ Recursos

*   **Arquitetura de Proxy Unificada:** Atende tanto a requisições do Antigravity CLI `/v1internal` quanto do Claude Code `/v1/messages` em uma única porta local (`8084`).
*   **Motor Multi-Provedores:** Integração dinâmica com Nvidia NIM, OpenRouter, DeepSeek nativo, Mistral AI, Groq e instâncias locais do Ollama.
*   **Cabeçalhos Dinâmicos de Requisição:** Altere o modelo e o provedor dinamicamente formatando suas chaves de API como `SUA_CHAVE:PROVEDOR/MODELO`.
*   **Página Inicial Interativa com Gravidade Zero:** Um painel premium inspirado no Google rodando **física 2D Matter.js** onde letras e cartões flutuam livremente e reagem ao ponteiro do mouse.

---

## 🚀 Início Rápido

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/opassoca/free-antigravity.git
    cd free-antigravity
    ```
2.  **Configure as variáveis de ambiente:**
    Copie o arquivo `.env.example` (da pasta `free-claude-code`) e preencha com suas chaves de provedor.
3.  **Inicie o Servidor:**
    ```bash
    python free-antigravity.py
    ```
4.  **Acesse o Dashboard:**
    Abra `http://localhost:8084` no seu navegador.

---

## 🛠️ Detalhes de Configuração

### Formato de Cabeçalho Dinâmico de API Key
Formate seu token de autenticação para alternar os backends dinamicamente:
```text
x-api-key: SEU_TOKEN_API:nvidia/deepseek-ai/deepseek-r1
x-api-key: SEU_TOKEN_API:openrouter/google/gemini-2.5-pro
```

---


## 📱 Execução Nativa no Termux
Especificamente otimizado para o Termux no Android. Instale os pacotes e execute o servidor do proxy unificado facilmente:
```bash
pkg install python ndk-sysroot clang
pip install -r requirements.txt
./install.sh
```


## ⌨️ Aliases de Auto-Proxy (Opcional)

Para executar seus comandos originais diretamente de qualquer diretório sem iniciar o proxy manualmente, adicione estas funções ao seu `~/.bashrc` ou `~/.zshrc`:

```bash
# Início automático do proxy para o Claude Code
claude() {
    if ! curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8084/v1internal/" 2>/dev/null | grep -q "200"; then
        python ~/free-antigravity/free-antigravity.py >/dev/null 2>&1 &
        sleep 1
    fi
    CLAUDE_CODE_URL="http://127.0.0.1:8084" command claude "$@"
}

# Alias para a Gemini CLI usando o wrapper
alias agy="~/bin/free-antigravity"
```

Execute `source ~/.bashrc` para aplicar as alterações.

## 👨‍💻 Créditos
Desenvolvido com 💙 por [Paçoca (@opassoca)](https://github.com/opassoca).
