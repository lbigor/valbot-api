#!/bin/bash
# Sobe TODA a stack do Valbot:
#   - backend FastAPI (tooling.dev_backend_stub) em :8001
#   - frontend Vite (valbot) em :5173
#   - cloudflared tunnel (se não estiver rodando) → valbot.stillflows.com.br
#
# Uso:
#   bash tooling/valbot_up.sh           # sobe tudo
#   bash tooling/valbot_up.sh --no-cf   # sem cloudflared (modo offline / só LAN)
#   bash tooling/valbot_up.sh --status  # só checa o que está rodando
#
# Logs:
#   /tmp/valbot_backend.log
#   /tmp/valbot_frontend.log
#   /tmp/valbot_cloudflared.log

set -u
cd "$(dirname "$0")/.."  # raiz do projeto

PROJECT_ROOT="$(pwd)"
PY="$PROJECT_ROOT/.venv/bin/python"
FRONTEND_DIR="$PROJECT_ROOT/frontend/artifacts/valbot"

NO_CF=0
STATUS_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --no-cf) NO_CF=1 ;;
    --status) STATUS_ONLY=1 ;;
  esac
done

echo "=== VALBOT UP — $(date '+%H:%M:%S') ==="
echo "raiz: $PROJECT_ROOT"

show_status() {
  echo ""
  echo "--- status ---"
  if lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -q ":8001 "; then
    echo "  ✅ backend  :8001  (http://localhost:8001/api/health)"
  else
    echo "  ❌ backend  :8001  (não está escutando)"
  fi
  if lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -q ":5173 "; then
    echo "  ✅ frontend :5173  (http://localhost:5173)"
  else
    echo "  ❌ frontend :5173  (não está escutando)"
  fi
  if pgrep -f "cloudflared tunnel run" >/dev/null 2>&1; then
    echo "  ✅ cloudflared rodando (https://valbot.stillflows.com.br)"
  else
    echo "  ⚪ cloudflared NÃO rodando — só acesso local/LAN"
  fi
}

if [ "$STATUS_ONLY" = "1" ]; then
  show_status
  exit 0
fi

# 1. Mata instâncias antigas (não toca cloudflared)
echo ""
echo "→ matando processos antigos do Valbot..."
pkill -9 -f "tooling.dev_backend_stub" 2>/dev/null || true
pkill -9 -f "valbot.*vite"             2>/dev/null || true
pkill -9 -f "vite/bin/vite"           2>/dev/null || true
sleep 1

# 2. Backend
echo "→ iniciando backend (uvicorn :8001)..."
nohup "$PY" -u -m tooling.dev_backend_stub > /tmp/valbot_backend.log 2>&1 &
BACKEND_PID=$!
echo "  backend pid=$BACKEND_PID, log=/tmp/valbot_backend.log"

# 3. Frontend
echo "→ iniciando frontend (vite :5173)..."
nohup pnpm --dir "$FRONTEND_DIR" run dev > /tmp/valbot_frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  frontend pid=$FRONTEND_PID, log=/tmp/valbot_frontend.log"

# 4. Cloudflared (opcional)
if [ "$NO_CF" = "0" ]; then
  if pgrep -f "cloudflared tunnel run" >/dev/null 2>&1; then
    echo "→ cloudflared já está rodando, mantendo."
  else
    if [ -f ~/.cloudflared/config.yml ] && command -v cloudflared >/dev/null 2>&1; then
      TUNNEL_NAME=$(grep -E "^tunnel:" ~/.cloudflared/config.yml | awk '{print $2}')
      if [ -n "$TUNNEL_NAME" ]; then
        echo "→ subindo cloudflared tunnel ($TUNNEL_NAME)..."
        nohup cloudflared tunnel run "$TUNNEL_NAME" > /tmp/valbot_cloudflared.log 2>&1 &
        CF_PID=$!
        echo "  cloudflared pid=$CF_PID, log=/tmp/valbot_cloudflared.log"
      else
        echo "⚠️  ~/.cloudflared/config.yml sem campo 'tunnel:'; pulando."
      fi
    else
      echo "⚠️  cloudflared não instalado ou sem config; pulando."
    fi
  fi
else
  echo "→ --no-cf: cloudflared não será iniciado (modo offline)"
fi

# 5. Aguarda portas subirem
echo ""
echo "→ aguardando portas..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  if lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -qE ":8001 |:5173 "; then
    break
  fi
  sleep 1
done

show_status

echo ""
echo "URLs:"
echo "  local:    http://localhost:5173/"
if [ "$NO_CF" = "0" ] && pgrep -f "cloudflared tunnel run" >/dev/null 2>&1; then
  echo "  público:  https://valbot.stillflows.com.br/"
fi
echo ""
echo "Para parar: bash tooling/valbot_down.sh"
