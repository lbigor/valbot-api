# HANDOFF — Valbot · Fila do Auditor + Deploy em Produção

> Última atualização: 2026-06-15. Resumo executável para retomar o trabalho sem reler a conversa.

## 1. O que é / objetivo
**Fila do Auditor** = tela imersiva (estilo Final Cut) onde o Auditor revisa exames de direção com divergência IA×Examinador e emite parecer. Substitui a antiga "Fila Operacional". Base: spec funcional v2 (§13.2) + Res. CONTRAN 1.020/2025 + MBEDV. IA é **consultiva**; decisão é humana.

## 2. Repositórios / GitHub (IMPORTANTE)
- **Repo de trabalho: `lbigor/valbot`** (privado), **default branch = `v2`**.
- Conta gh: o ambiente tem `GH_TOKEN=app1n-ai` que **NÃO acessa** `lbigor/valbot`. Para git push/gh/cstk session pr use **sempre `env -u GH_TOKEN`** (cai no keyring do `lbigor`). Credential helper já configurado (`gh auth setup-git`).
- `app1n-ai/valbot` é o repo antigo (PR #20 foi fechado lá).
- Tudo passa por **cstk** (sessões + SDD). PR via `env -u GH_TOKEN cstk session pr <name>` (abre contra `v2`).

## 3. Estado das PRs (base v2, draft)
| PR | Branch | Conteúdo |
|----|--------|----------|
| #22 | frente/backend-v2 | backend v2 (motores+Comitê+OS+Matriz, migrations 009-016, 38 testes) |
| #24 | sdd-foundation | briefing + constitution |
| #25 | api-os | endpoints OS/Comitê/parecer/Matriz no api_stub + migration 017 |
| #26 | design-system | design system (2 temas claro/grafite, tokens, ValbotLogo, TweaksPanel, ui kit) |
| #27 | fila-auditor | **Fila do Auditor imersiva** + limpeza de 9 telas legadas + SDD |
| #28 | hotfix-fila-label | rename "Fila Operacional"→"Fila do Auditor" + rota /fila→/fila-auditor |

SDD da feature: `docs/specs/fila-auditor/{spec,plan,tasks}.md`.

## 4. Frontend — onde está
- App: `frontend/artifacts/valbot` (React 19 + Vite + **wouter** + Tailwind v4; workspace pnpm em `frontend/`, `node_modules` içado para `frontend/node_modules`; typecheck: `pnpm exec tsc -p tsconfig.json --noEmit`; build: `pnpm exec vite build`).
- Tela: `src/pages/FilaAuditor.tsx` (default export, rota `/fila-auditor`, full-screen fora do AppLayout).
- Dados/API: `src/lib/painel.ts` — **v2 real** (fetch `/api/videos`, `/api/analyses/hash/{hash}/result`, `/api/rubricas/1020-2025`; vídeo `/api/exams/{hash}/video`). Contrato em `src/types/laudo.ts` (VideoItem, LaudoResult/Infracao, RubricaFull).
- Telas mantidas (requisito): Fila do Auditor, Dashboard, Regras, Login. Removidas: Videos, Galeria, Debug, Alertas, Relatorios, Auditoria, Configuracoes, AnaliseExame, FilaOperacional + UploadVideoModal/FlowSelector.
- Design bundle (protótipo-fonte) estável em `~/Desktop/valbot-design-bundle/project/` (painel-*.jsx, painel.css, logo.png).

## 5. PRODUÇÃO — como deploya (CRÍTICO, não óbvio)
- VM **`valbot-prod`** no GCP do Rodrigo: **config gcloud `valbot`** (projeto `valbot-497920`, conta `rodrigo@valmatech.com.br`), zona `us-central1-a`, IP `35.192.101.80`, domínio **valbot.com.br**. RUNNING. **NÃO** é a VM do projeto do Igor (308f1fa8 — aquela é a antiga, TERMINATED; não tocar).
- SSH: `CLOUDSDK_ACTIVE_CONFIG_NAME=valbot gcloud compute ssh valbot-prod --zone=us-central1-a` (IP público, **sem** `--tunnel-through-iap`).
- Roda via `/opt/valbot-deploy/docker-compose.yml` + **`docker-compose.override.yml`** + `.env` (secrets). Containers: `valbot-api` (nginx+FastAPI+frontend), `valbot-postgres`, `valbot-caddy` (TLS).
- ⚠️ **O override.yml monta CUSTOMIZAÇÕES por cima da imagem** (read-only):
  - `customizations/frontend-dist/public` → `/opt/valbot/frontend-dist/public` (o **frontend servido vem daqui**, não do dist da imagem!).
  - `customizations/server.py` → server.py (backend de prod é este, não o da imagem); idem db.py, gemini_analyzer.py, layout_discovery.py, process_pending_s3.py.
  - env: `VERTEX_PROJECT=valbot-497920`, `VERTEX_MODEL=gemini-2.5-pro`, `GCS_BUCKET=valbot-prod-data`, `VALBOT_USE_MODULAR_V26=1`.
- **Artifact Registry BLOQUEADO**: API off em valbot-497920; billing off no AR legado 308f1fa8 → não dá pra `docker push`/`pull`. `ci.yml` aponta pra 308f1fa8 (desatualizado, não usar).

### Deploy do FRONTEND (o que o usuário vê) — passo a passo
1. Build da imagem na própria VM (sem AR): `git archive HEAD` na worktree → `gcloud compute scp` o tarball → `docker build -t us-central1-docker.pkg.dev/project-308f1fa8-a301-49e6-a69/valbot/api:<tag> /tmp/vb` na VM.
2. **Atualizar o frontend servido** (senão NÃO muda nada): extrair `/opt/valbot/frontend-dist/public` da imagem nova e copiar para `customizations/frontend-dist/public` (com backup); `cd /opt/valbot-deploy && docker compose up -d --force-recreate api`.
3. Verificar: `curl https://valbot.com.br/api/health`; baixar o bundle de `https://valbot.com.br/<assets/index-*.js>` e `grep "Fila do Auditor"`.
- **Rollback**: `IMAGE_TAG` anterior era `43fd5f0` (sed no .env + `docker compose up -d api`). Backups do public ficam em `customizations/frontend-dist/public.bak.predeploy-*`.

## 6. Dados reais (prod)
- Exames reais no Postgres `valbot-postgres` (view `v_exams_overview`). Ex.: hash `c13e5bb065304baf9f0871496a74e7c9` (2 infrações, 5 pts, APROVADO, resultado_exame A). Vídeos reais via `/api/exams/{hash}/video`. Resultados Gemini via `/api/analyses/hash/{hash}/result`.

## 7. ESTADO ATUAL / próximos passos
- ✅ v1 (mock) deployado e visível em `valbot.com.br/fila-auditor`.
- 🔧 **EM ANDAMENTO**: rewrite v2 (dados/vídeo REAIS) — `painel.ts` + `FilaAuditor.tsx` reescritos para a API real. **FALTA**: `pnpm exec tsc --noEmit` + `pnpm exec vite build` (verde) → rebuild da imagem na VM → atualizar `customizations/frontend-dist/public` → `compose up -d --force-recreate api` → verificar vídeo+Gemini.
- Bugs reportados a fechar com o v2 real: (a) sem vídeo → vídeo real; (b) dados mock → reais; (c) ficha não abria ao clicar (codes mock ≠ reais) → ficha vem da própria infração; (d) overlap "2ª tela no topo" no chrome → revisar `.pchrome`/exam-picker (validar visualmente).
- Pendências de produto: examinador não traz infrações oficiais no result.json (comparação mostra só resultado); wiring de `parecer-auditor` (persistência) é v2.5; aplicar migrations 009-017 no Postgres + Comitê real.

## 8. Gotchas rápidos
- Auto mode bloqueia: self-edit de permissões (`update-config`) e "mandar fonte/buildar em prod" — precisa de regra Bash no settings do usuário.
- `rtk` (proxy) corrompe `git push`/binário em pipe → usar git nativo (`$(command which git)`) ou `rtk proxy`.
- Subagentes (Agent tool) ficam **sandbox** (sem git/gh/pnpm/write em ~/Desktop) — fazer o trabalho de deploy/PR na **sessão principal**.
