# VALBOT — Handoff entre sessões

**Data**: 2026-05-26 (sessão VM — doc init-upload + plano monorepo)
**Branch**: `main`
**SHA local mais recente**: `5285bd4`
**SHA rodando em prod**: `5285bd4` (container atual)
**IMAGE_TAG no `.env` da VM**: `9c6e62b` ⚠️ divergência — próximo `compose pull && up -d` troca o container

---

## O que foi feito nesta sessão (na VM, antes deste handoff)

### Doc estática do endpoint `POST /api/exams/init-upload` reescrita

Refletindo o Swagger vivo em produção:

- 13 campos no `InitUploadRequest`
- 6 campos no `InitUploadItem`
- Novo schema `TrainingAnnotation` (array de `{timestamp, anotacoes}`)
- Dois shapes do payload documentados
- Convenção `Infração <GRAVIDADE> —` documentada

Arquivos no ar em `https://valbot.com.br`:
- `/docs/init-upload.md`
- `/docs/init-upload.openapi.yaml`

Caddy serve direto do disco (`/opt/valbot-deploy/docs/`) — mudança já visível pros integradores.

### Estado de versionamento (antes desta sessão Mac)

Os 2 arquivos viviam **só** em `/opt/valbot-deploy/docs/` na VM `test-valbot-vm` (`us-central1-a`). VM não tem git. Source canônico mora no Mac.

---

## O que foi feito nesta sessão (Mac)

1. ✅ SCP via `gcloud compute scp --tunnel-through-iap` dos 2 arquivos da VM para `docs/init-upload.{md,openapi.yaml}` no repo local
2. 🚧 (em andamento) Migração de remote: `app1n-ai/valbot` → `lbigor/valbot` (privado)
3. 🚧 (em andamento) Commit + push inicial pro novo remote

---

## Plano combinado

Unificar API + frontend + deploy + site estático num único repo `lbigor/valbot` (privado) no GitHub pessoal.

**Status do plano (revisado no Mac):**

| Item original | Status |
|---|---|
| ~~Criar repo `lbigor/valbot` privado~~ | em andamento (sessão atual) |
| ~~Layout monorepo `api/web/site/deploy`~~ | ❌ obsoleto — repo já é monorepo (`src/`, `frontend/`, `docs/`, `deploy/`, `caddy/`, `migrations/`) |
| Pegar 2 arquivos atualizados da VM | ✅ feito |
| Trazer source da API/frontend pra estrutura | ❌ obsoleto — já está |
| Trazer conteúdo de `/opt/valbot-deploy/` da VM (sem `.env`/`.claude`) | parcial — só docs trazidos; resto continua só na VM |
| Commit + push inicial | em andamento |
| Decidir site estático: Caddy vs GCS+CDN | pendente (você inclinou pra **GCS + Cloud CDN**) |

---

## Achados da VM que precisam atenção

- **IMAGE_TAG vs container rodando**: `.env` da VM diz `9c6e62b`, container está em `5285bd4`. Próximo `docker compose pull && up -d api` vai trocar pra `9c6e62b`. Confirmar qual é o canônico antes do próximo deploy.
- **Imagem do Artifact Registry sem label `org.opencontainers.image.source`** — quando criar o repo no GitHub, adicionar essa label no Dockerfile pra rastreabilidade futura (link de pacote → repo).
- **Conteúdo `/opt/valbot-deploy/`** (compose + caddy + migrations + scripts) **ainda não está versionado**. Próximo passo lógico é trazer pra `deploy/` aqui no repo (já existe a pasta).

---

## API key de teste (criada nesta sessão)

Válida em prod, scope `exams:create`:

```
id   = b4ff1230-001a-4127-b6e8-56160feabfeb
name = test
```

Persistida em `/opt/valbot-deploy/.env` (VM) como `VALBOT_API_KEY_TEST`.
Revogar via `DELETE /api/admin/api-keys/<id>` quando não precisar mais.

---

## Próximos passos (depois desta sessão Mac)

1. Decidir: continuar servindo `docs/init-upload.*` via Caddy ou mover pra GCS + Cloud CDN (inclinação: CDN).
2. Trazer `/opt/valbot-deploy/{docker-compose.yml, Caddyfile, migrations/, scripts/}` da VM pra `deploy/` do repo (sem `.env` nem `.claude/`).
3. Configurar GitHub Actions: build + push Artifact Registry + deploy via SSH em `test-valbot-vm`.
4. Adicionar label OCI source no Dockerfile.
5. Resolver divergência `IMAGE_TAG` antes do próximo deploy.
