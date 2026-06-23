#!/usr/bin/env bash
# =============================================================================
# deploy/provision.sh — provisiona infra GCP do valbot de forma idempotente.
#
# O que cria (cada item checa se existe antes):
#   1. Service Account `valbot-vm` com 3 roles (Vertex, GCS, AR-reader).
#   2. Repositório Docker no Artifact Registry (`valbot`).
#   3. Bucket GCS `valbot-prod` (CORS + lifecycle).
#   4. VM e2-standard-2 (`valbot-prod`) com SA atrelada — ÚNICO recurso que
#      gera custo recorrente. Pede confirmação antes de criar.
#
# Pré-reqs: gcloud autenticado (`gcloud auth login`) e projeto correto setado
# (`gcloud config set project ...`). Não toca DNS — Cloudflare Tunnel é setup
# manual no painel Zero Trust.
#
# Uso:
#   ./deploy/provision.sh                # tudo
#   ./deploy/provision.sh --only-vm      # só a VM
#   ./deploy/provision.sh --dry-run      # mostra o que faria, sem criar
# =============================================================================
set -euo pipefail

PROJECT="${GCP_PROJECT:-valbot-497920}"
REGION="${GCP_REGION:-us-central1}"
ZONE="${GCP_ZONE:-us-central1-a}"
SA_NAME="valbot-vm"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
AR_REPO="valbot"
BUCKET="valbot-prod"
VM_NAME="valbot-prod"
VM_TYPE="e2-standard-2"
DISK_SIZE="30GB"

DRY_RUN=0
ONLY=""
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=1 ;;
    --only-sa)    ONLY="sa" ;;
    --only-ar)    ONLY="ar" ;;
    --only-gcs)   ONLY="gcs" ;;
    --only-vm)    ONLY="vm" ;;
    -h|--help)
      sed -n '2,/^# ===/p' "$0" | sed 's/^# //; s/^#$//; s/^# *//'
      exit 0 ;;
    *) echo "arg desconhecido: $arg"; exit 2 ;;
  esac
done

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
log()    { printf "\n\033[1;36m▶ %s\033[0m\n" "$*"; }
ok()     { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn()   { printf "  \033[33m!\033[0m %s\n" "$*"; }
err()    { printf "  \033[31m✗\033[0m %s\n" "$*"; }

run() {
  if (( DRY_RUN )); then
    printf "  \033[2m[dry-run] %s\033[0m\n" "$*"
  else
    "$@"
  fi
}

confirm() {
  local prompt="$1"
  read -rp "$prompt [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]]
}

require_gcloud() {
  command -v gcloud >/dev/null || { err "gcloud não encontrado. Instale o Cloud SDK."; exit 1; }
  command -v gsutil >/dev/null || { err "gsutil não encontrado."; exit 1; }
  if ! gcloud auth list --filter='status:ACTIVE' --format='value(account)' | grep -q .; then
    err "Não há conta gcloud ativa. Rode: gcloud auth login"; exit 1
  fi
  CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || true)
  if [[ "$CURRENT_PROJECT" != "$PROJECT" ]]; then
    warn "gcloud project atual = '$CURRENT_PROJECT', esperado '$PROJECT'"
    confirm "Setar projeto $PROJECT agora?" || exit 1
    run gcloud config set project "$PROJECT"
  fi
  ok "gcloud autenticado como $(gcloud config get-value account 2>/dev/null) no projeto $PROJECT"
}

# ----------------------------------------------------------------------------
# 1. Service Account
# ----------------------------------------------------------------------------
provision_sa() {
  log "Service Account ${SA_EMAIL}"
  if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT" >/dev/null 2>&1; then
    ok "SA já existe — pulando criação"
  else
    run gcloud iam service-accounts create "$SA_NAME" \
      --project="$PROJECT" \
      --display-name="Valbot VM (Vertex + GCS + AR)" \
      --description="Service Account atrelada à VM valbot-prod"
    ok "SA criada"
  fi

  for role in roles/aiplatform.user roles/storage.objectAdmin roles/artifactregistry.reader; do
    if gcloud projects get-iam-policy "$PROJECT" \
        --flatten="bindings[].members" \
        --format="value(bindings.role)" \
        --filter="bindings.members:serviceAccount:${SA_EMAIL} AND bindings.role:${role}" \
        2>/dev/null | grep -q .; then
      ok "binding já existe: $role"
    else
      run gcloud projects add-iam-policy-binding "$PROJECT" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="$role" \
        --condition=None \
        --quiet >/dev/null
      ok "concedido: $role"
    fi
  done
}

# ----------------------------------------------------------------------------
# 2. Artifact Registry
# ----------------------------------------------------------------------------
provision_ar() {
  log "Artifact Registry ${REGION}/${AR_REPO}"
  if gcloud artifacts repositories describe "$AR_REPO" \
      --location="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
    ok "repo já existe — pulando"
  else
    run gcloud artifacts repositories create "$AR_REPO" \
      --location="$REGION" \
      --project="$PROJECT" \
      --repository-format=docker \
      --description="Imagens Docker do valbot"
    ok "repo criado"
  fi
  run gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
  ok "docker auth configurado"
}

# ----------------------------------------------------------------------------
# 3. GCS bucket
# ----------------------------------------------------------------------------
provision_gcs() {
  log "GCS bucket gs://${BUCKET}"
  if gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1; then
    ok "bucket já existe — pulando criação"
  else
    run gsutil mb -p "$PROJECT" -l "$REGION" "gs://${BUCKET}/"
    ok "bucket criado em ${REGION}"
  fi
  log "  CORS"
  run gsutil cors set deploy/cors.json "gs://${BUCKET}"
  log "  Lifecycle (uploads/ → 30d, analyses/ → NEARLINE 90d)"
  run gsutil lifecycle set deploy/lifecycle.json "gs://${BUCKET}"
  ok "policies aplicadas"
}

# ----------------------------------------------------------------------------
# 4. VM (recurso pago — pede confirmação)
# ----------------------------------------------------------------------------
provision_vm() {
  log "VM ${VM_NAME} (${VM_TYPE} em ${ZONE})"
  if gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1; then
    ok "VM já existe — pulando"
    return
  fi
  warn "Vou criar uma VM ${VM_TYPE} em ${ZONE} — custo ~\$48/mês (cobrado dos créditos GCP)."
  confirm "Criar a VM agora?" || { warn "VM não criada"; return; }

  run gcloud compute instances create "$VM_NAME" \
    --project="$PROJECT" \
    --zone="$ZONE" \
    --machine-type="$VM_TYPE" \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size="$DISK_SIZE" \
    --boot-disk-type=pd-balanced \
    --service-account="$SA_EMAIL" \
    --scopes=cloud-platform \
    --metadata=enable-oslogin=TRUE \
    --tags=valbot-prod \
    --labels=app=valbot,env=prod
  ok "VM criada"

  log "  aguardando SSH ficar disponível…"
  for i in {1..30}; do
    if gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command='echo ok' >/dev/null 2>&1; then
      ok "SSH OK"
      break
    fi
    sleep 5
  done

  log "  instalando Docker + utils via SSH"
  run gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command='
    set -e
    sudo apt-get update -qq
    sudo apt-get install -y -qq ca-certificates curl gnupg git
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    sudo gcloud auth configure-docker '"$REGION"'-docker.pkg.dev --quiet 2>/dev/null || true
    sudo mkdir -p /opt/valbot-deploy
    sudo chown -R $USER:$USER /opt/valbot-deploy
  '
  ok "Docker instalado"
}

# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
require_gcloud

case "$ONLY" in
  sa)  provision_sa ;;
  ar)  provision_ar ;;
  gcs) provision_gcs ;;
  vm)  provision_vm ;;
  "")
    provision_sa
    provision_ar
    provision_gcs
    provision_vm
    ;;
esac

log "Próximos passos manuais"
cat <<EOF
  1. Build + push da primeira imagem:
       make push

  2. Copiar artefatos pra VM:
       gcloud compute scp docker-compose.yml deploy/.env.example \\
         migrations/ ${VM_NAME}:/opt/valbot-deploy/ --zone=${ZONE} --recurse

  3. Na VM, criar .env e subir stack:
       gcloud compute ssh ${VM_NAME} --zone=${ZONE}
       cd /opt/valbot-deploy
       cp .env.example .env  # editar com senhas + tunnel token
       docker compose up -d

  4. Cloudflare Tunnel — no painel Zero Trust:
       Networks → Tunnels → Create → "valbot-vm" → copia TUNNEL_TOKEN para .env
       Public hostnames:
         valbot.stillflows.com.br        → http://api:80
         ssh.valbot.stillflows.com.br    → ssh://host.docker.internal:22

  5. Cloudflare Access policies:
       valbot.stillflows.com.br/code  → email = lbigor@icloud.com
       ssh.valbot.stillflows.com.br   → email + service token (Termius/Blink)
EOF
