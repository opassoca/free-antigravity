# 🌌 Free Antigravity — 统一失重人工智能代理 (AI Proxy)

🌎 **选择语言:**
[English](README.md) | [Português](README.pt-BR.md) | [Español](README.es.md) | [Русский](README.ru.md) | [中文](README.zh.md)

---

一个高性能统一代理 (Proxy)，旨在将 **Antigravity CLI (agy)** 和 **Claude Code** 连接到任何 AI 提供商 (Nvidia NIM, OpenRouter, DeepSeek, Mistral, Groq, Ollama)，具有动态密钥解析和交互式失重物理控制面板。

---


## 🧠 模型路由工作原理

1. **动态模型发现**: 代理会自动查询您 `.env` 文件中配置的活动提供商 (Nvidia NIM, OpenRouter 等)，使用基于 TTL 的机制缓存其模型目录，并将其统一整合至 `agy -model` 选择菜单中 (动态提供 140+ 种选项)。
2. **扁平化 ID 解析**: 为 CLI 菜单生成的扁平化 ID (例如 `nvidia-deepseek-ai-deepseek-v4-pro`) 在启动对话时，会被透明地映射回原始的提供商 ID (例如 `nvidia/deepseek-ai/deepseek-v4-pro`)。
3. **手动覆盖**: 您仍然可以通过在 `.env` 中配置 `MODEL_MAP_*` 变量，或者通过传入格式为 `YOUR_KEY:PROVIDER/MODEL` 的密钥，来动态路由到特定的后端。

## 📊 Token 使用量与配额跟踪

*   **实际消耗跟踪**: 代理拦截器提取流式响应分块 (stream response chunks) 中返回的官方 Token 指标 (`prompt_tokens` 和 `completion_tokens`)。
*   **持久化统计**: 使用数据本地存储在 `data/usage_stats.json` 中。
*   **真实配额扣除**: `/v1internal:retrieveUserQuotaSummary` 接口會动态读取您的累计消耗，并在 `agy` CLI 标题中无缝报告剩余配额。
*   **实时配额 API**：查询 `/v1internal/quota` 端点以实时检查所有活动提供商和模型的当前实时额度比例、剩余 Token 以及消耗摘要。

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


## ⌨️ 自动代理别名 (可选)

要在任何目录下直接运行原始命令而无需手动启动代理，请将这些函数追加到您的 `~/.bashrc` 或 `~/.zshrc` 中：

```bash
# Claude Code 自动启动代理
claude() {
    if ! curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8084/v1internal/" 2>/dev/null | grep -q "200"; then
        python ~/free-antigravity/free-antigravity.py >/dev/null 2>&1 &
        sleep 1
    fi
    CLAUDE_CODE_URL="http://127.0.0.1:8084" command claude "$@"
}

# 使用封装器的 Gemini CLI 别名
alias agy="~/bin/free-antigravity"
```

运行 `source ~/.bashrc` 以应用更改。

## 👨‍💻 贡献者
由 [Paçoca (@opassoca)](https://github.com/opassoca) 用 💙 开发。
