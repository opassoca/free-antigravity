# 🌌 Free Antigravity — 统一失重人工智能代理 (AI Proxy)

🌎 **选择语言:**
[English](README.md) | [Português](README.pt-BR.md) | [Español](README.es.md) | [Русский](README.ru.md) | [中文](README.zh.md)

---

一个高性能统一代理 (Proxy)，旨在将 **Antigravity CLI (agy)** 和 **Claude Code** 连接到任何 AI 提供商 (Nvidia NIM, OpenRouter, DeepSeek, Mistral, Groq, Ollama)，具有动态密钥解析和交互式失重物理控制面板。

---

## ⚡ 特性

*   **统一代理架构:** 在单个本地端口 (`8084`) 上同时服务 Antigravity CLI `/v1internal` 请求和 Claude Code `/v1/messages` 请求。
*   **多提供商引擎:** 与 Nvidia NIM, OpenRouter, 原生 DeepSeek, Mistral AI, Groq 以及本地 Ollama 实例进行动态集成。
*   **动态请求头:** 通过将您的 API 密钥格式化为 `YOUR_KEY:PROVIDER/MODEL` 来动态切换模型和提供商。
*   **交互式失重着陆页:** 受 Google 启发的优质控制面板，运行 **Matter.js 2D 物理引擎**，其中的品牌字母和卡片可自由漂浮并对鼠标指针做出反应。

---

## 🚀 快速开始

1.  **克隆仓库:**
    ```bash
    git clone https://github.com/opassoca/free-antigravity.git
    cd free-antigravity
    ```
2.  **配置环境变量:**
    复制 `.env.example` 文件 (自 `free-claude-code` 目录) 并填写您的提供商密钥。
3.  **运行服务器:**
    ```bash
    python free-antigravity.py
    ```
4.  **访问控制面板:**
    在浏览器中打开 `http://localhost:8084`。

---

## 🛠️ 配置详情

### 动态 API 密钥请求头格式
格式化您的身份验证令牌以动态切换后端:
```text
x-api-key: YOUR_API_TOKEN:nvidia/deepseek-ai/deepseek-r1
x-api-key: YOUR_API_TOKEN:openrouter/google/gemini-2.5-pro
```

---


## 📱 Termux 原生运行
专为 Android Termux 优化。轻松安装包并运行统一的代理桥接器：
```bash
pkg install python ndk-sysroot clang
pip install -r requirements.txt
./install.sh
```

## 👨‍💻 贡献者
由 [Paçoca (@opassoca)](https://github.com/opassoca) 用 💙 开发。
