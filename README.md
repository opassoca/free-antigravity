# 🌌 Free Antigravity — Unified Zero-Gravity AI Proxy

🌎 **Choose your language:**
[English](README.md) | [Português](README.pt-BR.md) | [Español](README.es.md) | [Русский](README.ru.md) | [中文](README.zh.md)

---

A high-performance unified proxy designed to connect **Antigravity CLI (agy)** and **Claude Code** to any AI provider (Nvidia NIM, OpenRouter, DeepSeek, Mistral, Groq, Ollama) with dynamic key resolution and a zero-gravity physics dashboard.

---

## ⚡ Features

*   **Unified Proxy Architecture:** Serves both Antigravity CLI `/v1internal` requests and Claude Code `/v1/messages` on a single local port (`8084`).
*   **Multi-Provider Engine:** Dynamic integration with Nvidia NIM, OpenRouter, native DeepSeek, Mistral AI, Groq, and local Ollama instances.
*   **Dynamic Request Headers:** Change the model and provider on-the-fly by formatting your API keys as `YOUR_KEY:PROVIDER/MODEL`.
*   **Interactive Zero-Gravity Landing Page:** A premium Google-inspired dashboard running **Matter.js 2D physics** where branding letters and cards float freely and react to your mouse pointer.

---

## 🚀 Quick Start

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/opassoca/free-antigravity.git
    cd free-antigravity
    ```
2.  **Configure environment variables:**
    Copy the `.env.example` file (from the `free-claude-code` directory) and populate it with your provider keys.
3.  **Run the Server:**
    ```bash
    python free-antigravity.py
    ```
4.  **Access the Dashboard:**
    Open `http://localhost:8084` in your browser.

---

## 🛠️ Configuration Details

### Dynamic API Key Header Format
Format your authentication token to switch backends dynamically:
```text
x-api-key: YOUR_API_TOKEN:nvidia/deepseek-ai/deepseek-r1
x-api-key: YOUR_API_TOKEN:openrouter/google/gemini-2.5-pro
```

---


## 📱 Termux Native Execution
Specifically optimized for Android Termux. Install packages and run the unified agent bridge easily:
```bash
pkg install python ndk-sysroot clang
pip install -r requirements.txt
./install.sh
```


## ⌨️ Auto-Proxy Aliases (Optional)

To run your original commands directly from any directory without manual proxy startup, append these functions to your `~/.bashrc` or `~/.zshrc`:

```bash
# Auto-start proxy for Claude Code
claude() {
    if ! curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8084/v1internal/" 2>/dev/null | grep -q "200"; then
        python ~/free-antigravity/free-antigravity.py >/dev/null 2>&1 &
        sleep 1
    fi
    CLAUDE_CODE_URL="http://127.0.0.1:8084" command claude "$@"
}

# Alias for Gemini CLI using the wrapper
alias agy="~/bin/free-antigravity"
```

Run `source ~/.bashrc` to apply the changes.

## 👨‍💻 Credits
Developed with 💙 by [Paçoca (@opassoca)](https://github.com/opassoca).
