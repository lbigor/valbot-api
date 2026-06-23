#!/bin/bash
# run_pending_s3.sh — wrapper pra rodar o backfill S3→GCS→Gemini periodicamente.
#
# Pensado pra ser chamado via cron a cada 2-5 min:
#
#     */3 * * * * /opt/valbot-deploy/scripts/run_pending_s3.sh >> /var/log/valbot/pending_s3.log 2>&1
#
# Carrega .env (credenciais AWS + admin tokens), entra no container valbot-api e
# dispara o script standalone. Usa flock pra evitar dois runs paralelos brigando
# pela mesma quota Vertex AI.

set -euo pipefail

DEPLOY_DIR="/opt/valbot-deploy"
ENV_FILE="$DEPLOY_DIR/.env"
LOCK_FILE="/tmp/run_pending_s3.lock"

[ -f "$ENV_FILE" ] || { echo "[$(date -Iseconds)] missing $ENV_FILE"; exit 2; }

# Carrega .env de forma segura (só os pares chave=valor).
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID ausente em .env}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY ausente em .env}"
: "${AWS_REGION:=us-east-1}"

# Lock — se outra run ainda está em curso, sai limpo (não acumula).
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "[$(date -Iseconds)] already running, skipping"; exit 0; }

echo "[$(date -Iseconds)] starting pending_s3 sweep"

docker exec \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e AWS_REGION="$AWS_REGION" \
  -e VALBOT_PRESET="${VALBOT_PRESET:-v25/valbot-r1-vip-v25}" \
  -e VALBOT_MAX_OUTPUT_TOKENS="${VALBOT_MAX_OUTPUT_TOKENS:-16384}" \
  -e PYTHONPATH=/opt/valbot \
  valbot-api python /opt/valbot/tooling/process_pending_s3.py

echo "[$(date -Iseconds)] sweep done"
