#!/usr/bin/env bash
# Entrypoint do container `valbot-api`.
# Sobe nginx (frontend estático + reverse proxy /api → 8001) e uvicorn em paralelo.
# Encerra ambos limpos em SIGTERM (graceful shutdown).

set -euo pipefail

cleanup() {
    echo "[start.sh] shutting down…"
    [[ -n "${UVICORN_PID:-}" ]] && kill -TERM "$UVICORN_PID" 2>/dev/null || true
    [[ -n "${NGINX_PID:-}"   ]] && kill -TERM "$NGINX_PID"   2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup TERM INT

echo "[start.sh] starting nginx (front) + uvicorn (api)…"

# Nginx em foreground (daemon off) — depois trazemos para background.
nginx -g 'daemon off;' &
NGINX_PID=$!

# FastAPI escuta apenas em loopback; nginx faz o proxy.
exec uvicorn tooling.api_stub.server:app \
    --host 127.0.0.1 \
    --port 8001 \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --log-level info &
UVICORN_PID=$!

wait -n "$NGINX_PID" "$UVICORN_PID"
EXIT_CODE=$?
echo "[start.sh] one of the children exited with code $EXIT_CODE — tearing down"
cleanup
exit "$EXIT_CODE"
