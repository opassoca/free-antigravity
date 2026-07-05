#!/usr/bin/env bash
set -e
echo "◈ Free Antigravity - Proxy Installer ◈"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Instalar dependências de Python
echo "[*] Instalando dependências de Python a partir do requirements.txt..."
python3 -m pip install -r "$PROJECT_DIR/requirements.txt"

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
MITM_SCRIPT="/data/data/com.termux/files/home/free-antigravity/mitm_proxy.py"
MITM_PORT=8085
AGY_BIN="/data/data/com.termux/files/usr/bin/agy.va39"
CERT_DIR="/data/data/com.termux/files/home/free-antigravity/data/certs"
LOG_DIR="/data/data/com.termux/files/home/.gemini/antigravity-cli"

check_proxy() {
    curl -s -o /dev/null -w "%{http_code}" "${PROXY_URL}/v1internal/" 2>/dev/null | grep -q "200"
}

check_mitm() {
    # Verificar se o MITM esta escutando na porta
    (echo > /dev/tcp/127.0.0.1/${MITM_PORT}) 2>/dev/null
}

wait_port_free() {
    local port=$1
    for i in {1..20}; do
        if ! (echo > /dev/tcp/127.0.0.1/${port}) 2>/dev/null; then
            return 0
        fi
        sleep 0.05
    done
    return 1
}

# 0. Se o usuario especificou variaveis customizadas sob demanda (ex: MOCK_EMAIL),
# reiniciamos as portas para garantir que a nova configuracao seja carregada.
KILLED_ANY=0
if [ -n "${MOCK_EMAIL}" ] || [ -n "${MOCK_PLAN_NAME}" ] || [ -n "${NIM_MODEL}" ]; then
    fuser -k -n tcp ${PROXY_PORT} 2>/dev/null && KILLED_ANY=1
    fuser -k -n tcp ${MITM_PORT} 2>/dev/null && KILLED_ANY=1
fi

# 1. Limpar processos antigos se nao estiverem respondendo corretamente
if ! check_proxy; then
    fuser -k -n tcp ${PROXY_PORT} 2>/dev/null && KILLED_ANY=1
fi
if ! check_mitm; then
    fuser -k -n tcp ${MITM_PORT} 2>/dev/null && KILLED_ANY=1
fi

# Se matamos algum processo, aguardamos as portas serem liberadas pelo SO
if [ "${KILLED_ANY}" -eq 1 ]; then
    wait_port_free ${PROXY_PORT}
    wait_port_free ${MITM_PORT}
fi

STARTED_PROXY=0
STARTED_MITM=0

# 2. Iniciar proxy FastAPI (backend principal)
if ! check_proxy; then
    echo "Iniciando free-antigravity proxy na porta ${PROXY_PORT}..."
    # Propagar as variaveis de ambiente na chamada do python
    export MOCK_EMAIL="${MOCK_EMAIL}"
    export MOCK_PLAN_NAME="${MOCK_PLAN_NAME}"
    export NIM_MODEL="${NIM_MODEL}"
    python "${PROXY_SCRIPT}" >"${LOG_DIR}/free-antigravity.log" 2>&1 &
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

# 3. Iniciar proxy MITM (intercepta chamadas HTTPS ao googleapis.com)
if ! check_mitm; then
    echo "Iniciando proxy MITM na porta ${MITM_PORT}..."
    python "${MITM_SCRIPT}" >"${LOG_DIR}/mitm-proxy.log" 2>&1 &
    MITM_PID=$!
    STARTED_MITM=1
    for i in {1..10}; do
        if check_mitm; then break; fi
        sleep 0.5
    done
    if ! check_mitm; then
        echo "Aviso: Proxy MITM não iniciou. Eligibility check pode falhar."
    fi
fi

# 4. Configurar variaveis de ambiente para o agy
export CLOUD_CODE_URL="${PROXY_URL}"
export BAICODE_ENDPOINT_URL="${PROXY_URL}"
unset GEMINI_API_KEY
unset GOOGLE_API_KEY

# Proxy HTTPS apenas para interceptar chamadas externas de elegibilidade (googleapis.com)
# Sem proxy HTTP/HTTP_PROXY local para evitar conflito com chamadas para 127.0.0.1:8084
export HTTPS_PROXY="http://127.0.0.1:${MITM_PORT}"
export https_proxy="http://127.0.0.1:${MITM_PORT}"
export NO_PROXY="127.0.0.1,localhost"
export no_proxy="127.0.0.1,localhost"

# Certificados: apontar o Go para confiar no nosso CA local de forma absoluta
export SSL_CERT_FILE="${CERT_DIR}/ca-bundle.crt"

# 5. Executar agy
glibc-runner "${AGY_BIN}" "$@"
EXIT_CODE=$?

# 6. Limpar processos se foram iniciados nesta sessao
if [ "${STARTED_MITM}" -eq 1 ]; then
    MITM_PIDS=$(pgrep -f "${MITM_SCRIPT}")
    [ -n "${MITM_PIDS}" ] && kill ${MITM_PIDS} 2>/dev/null
fi

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
