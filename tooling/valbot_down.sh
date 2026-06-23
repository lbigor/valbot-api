#!/bin/bash
# Para a stack do Valbot (backend, frontend; cloudflared opcionalmente).
#
# Uso:
#   bash tooling/valbot_down.sh         # mata backend + frontend (mantém cloudflared)
#   bash tooling/valbot_down.sh --all   # também mata cloudflared

KILL_CF=0
for arg in "$@"; do
  [ "$arg" = "--all" ] && KILL_CF=1
done

echo "=== VALBOT DOWN — $(date '+%H:%M:%S') ==="
pkill -9 -f "tooling.dev_backend_stub" 2>/dev/null && echo "  backend morto" || echo "  backend não estava rodando"
pkill -9 -f "valbot.*vite"             2>/dev/null
pkill -9 -f "vite/bin/vite"           2>/dev/null && echo "  frontend morto" || echo "  frontend não estava rodando"

if [ "$KILL_CF" = "1" ]; then
  pkill -9 -f "cloudflared tunnel run" 2>/dev/null && echo "  cloudflared morto" || echo "  cloudflared não estava rodando"
else
  echo "  cloudflared mantido (use --all pra matar também)"
fi
