#!/usr/bin/env bash
set -e
echo "◈ Free Antigravity - Proxy Installer ◈"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Instalar dependências de Python
echo "[*] Instalando dependências de Python a partir do requirements.txt..."
python -m pip install -r "$PROJECT_DIR/requirements.txt"

# 2. Validar diretório binário local
BIN_DIR="/data/data/com.termux/files/home/bin"
mkdir -p "$BIN_DIR"

# 3. Criar ou atualizar o executável free-antigravity
echo "[*] Configurando wrapper free-antigravity..."
cat << 'EOF' > "$BIN_DIR/free-antigravity"
#!/data/data/com.termux/files/usr/bin/bash
PROXY_PORT=8084
PROXY_URL="http://127.0.0.1:${PROXY_PORT}"
PROXY_SCRIPT="/data/data/com.termux/files/home/free-antigravity/free-antigravity.py"
AGY_BIN="/data/data/com.termux/files/usr/bin/agy.va39"

check_proxy() {
    curl -s -o /dev/null -w "%{http_code}" "${PROXY_URL}/v1internal/" 2>/dev/null | grep -q "200"
}

STARTED_PROXY=0
if ! check_proxy; then
    echo "Iniciando free-antigravity proxy na porta ${PROXY_PORT}..."
    python "${PROXY_SCRIPT}" >/data/data/com.termux/files/home/.gemini/antigravity-cli/free-antigravity.log 2>&1 &
    PROXY_PID=$!
    STARTED_PROXY=1
    for i in {1..10}; do
        if check_proxy; then break; fi
        sleep 0.5
    done
    if ! check_proxy; then
        echo "Erro: Não foi possível iniciar o proxy free-antigravity."
        [ -n "${PROXY_PID}" ] && kill -9 "${PROXY_PID}" 2>/dev/null
        exit 1
    fi
fi

export CLOUD_CODE_URL="${PROXY_URL}"
export BAICODE_ENDPOINT_URL="${PROXY_URL}"
unset GEMINI_API_KEY
unset GOOGLE_API_KEY

glibc-runner "${AGY_BIN}" "$@"
EXIT_CODE=$?

if [ "${STARTED_PROXY}" -eq 1 ]; then
    PIDS=$(pgrep -f "${PROXY_SCRIPT}")
    [ -n "${PIDS}" ] && kill ${PIDS} 2>/dev/null
fi
exit ${EXIT_CODE}
EOF

chmod +x "$BIN_DIR/free-antigravity"

echo ""
echo "✨ Free Antigravity instalado e configurado com sucesso!"
echo "◈ Comando global disponível: ~/bin/free-antigravity"
echo "------------------------------------------------"
