# =============================================================================
# Makefile — comandos do dia-a-dia. Use `make` sem args para listar.
# =============================================================================

GCP_PROJECT  ?= valbot-497920
GCP_REGION   ?= us-central1
GCP_ZONE     ?= us-central1-a
AR_REPO      ?= valbot
IMAGE_NAME   ?= us-central1-docker.pkg.dev/$(GCP_PROJECT)/$(AR_REPO)/api
GIT_SHA      := $(shell git rev-parse --short HEAD 2>/dev/null || echo "dev")
VM_NAME      ?= valbot-prod

.DEFAULT_GOAL := help

.PHONY: help
help: ## lista os comandos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# -----------------------------------------------------------------------------
# Dev local
# -----------------------------------------------------------------------------
.PHONY: dev
dev: ## sobe backend (mock VLM) + frontend Vite localmente
	@echo "→ backend em :8001 (mock=1) | frontend em :5173"
	@VALBOT_USE_MOCK_VLM=1 .venv/bin/python -m tooling.api_stub.server &
	@cd frontend && pnpm --filter @workspace/valbot dev

.PHONY: api
api: ## sobe só o backend FastAPI (mock VLM)
	VALBOT_USE_MOCK_VLM=1 .venv/bin/python -m tooling.api_stub.server

.PHONY: front
front: ## sobe só o frontend Vite
	cd frontend && pnpm --filter @workspace/valbot dev

.PHONY: test
test: ## roda lint + pytest + vitest
	pre-commit run --all-files
	.venv/bin/pytest -q
	cd frontend && pnpm lint && pnpm test

# -----------------------------------------------------------------------------
# Build + push Docker
# -----------------------------------------------------------------------------
.PHONY: docker-auth
docker-auth: ## auth do docker contra Artifact Registry (1× por máquina)
	gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev --quiet

.PHONY: build
build: ## build da imagem Docker localmente (linux/amd64)
	docker buildx build --platform linux/amd64 \
	  --build-arg GIT_SHA=$(GIT_SHA) \
	  --build-arg IMAGE_VERSION=$(GIT_SHA) \
	  -t $(IMAGE_NAME):$(GIT_SHA) \
	  -t $(IMAGE_NAME):latest \
	  --load .

.PHONY: push
push: ## build + push pra Artifact Registry
	docker buildx build --platform linux/amd64 \
	  --build-arg GIT_SHA=$(GIT_SHA) \
	  --build-arg IMAGE_VERSION=$(GIT_SHA) \
	  -t $(IMAGE_NAME):$(GIT_SHA) \
	  -t $(IMAGE_NAME):latest \
	  --push .
	@echo "✅ pushed $(IMAGE_NAME):$(GIT_SHA)"

.PHONY: scan
scan: ## roda Trivy contra a imagem (HIGH/CRITICAL fail)
	trivy image --exit-code 1 --severity HIGH,CRITICAL $(IMAGE_NAME):$(GIT_SHA)

# -----------------------------------------------------------------------------
# Deploy / operação na VM
# -----------------------------------------------------------------------------
.PHONY: deploy
deploy: push ## build + push + roll forward na VM prod
	gcloud compute ssh $(VM_NAME) --zone=$(GCP_ZONE) \
	  --command "cd /opt/valbot-deploy && IMAGE_TAG=$(GIT_SHA) docker compose pull api && IMAGE_TAG=$(GIT_SHA) docker compose up -d api"
	@echo "✅ rolled $(IMAGE_NAME):$(GIT_SHA) on $(VM_NAME)"

.PHONY: ssh
ssh: ## ssh na VM via gcloud
	gcloud compute ssh $(VM_NAME) --zone=$(GCP_ZONE)

.PHONY: logs
logs: ## tail dos logs do api em prod
	gcloud compute ssh $(VM_NAME) --zone=$(GCP_ZONE) \
	  --command "docker compose -f /opt/valbot-deploy/docker-compose.yml logs -f --tail=200 api"

.PHONY: status
status: ## status dos containers em prod
	gcloud compute ssh $(VM_NAME) --zone=$(GCP_ZONE) \
	  --command "docker compose -f /opt/valbot-deploy/docker-compose.yml ps"

# -----------------------------------------------------------------------------
# Provisionamento (idempotente — pode rodar múltiplas vezes)
# -----------------------------------------------------------------------------
.PHONY: provision
provision: ## cria SA + AR repo + GCS bucket + VM (verifica antes de criar)
	./deploy/provision.sh

.PHONY: provision-vm
provision-vm: ## cria/atualiza só a VM
	./deploy/provision.sh --only-vm
