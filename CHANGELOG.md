# Changelog

Todas as mudanças notáveis nesse projeto serão documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
versionamento [SemVer](https://semver.org/lang/pt-BR/).
Mensagens de commit seguem [Conventional Commits](https://www.conventionalcommits.org/pt-br/).

## [Unreleased]

### Added
- `frontend/artifacts/valbot/src/utils/mockExam.ts` — gerador de defaults aleatórios pro modal de upload (20 nomes, 15 examinadores, 8 veículos, 10 cidades SP, 10 escolas).
- `GET /api/rubricas/{slug}` em `tooling/api_stub/server.py` — devolve a rubrica 1.020/2025 com 30 infrações enriquecidas com `vlm_prompt_hint` extraído do preset v25.
- `src/analysis/openrouter_gemini.py` — backend Vertex AI (`gemini-3.1-pro-preview`) com prompt explícito de layout dinâmico (4 câmeras VIP/HIK/outro), análise simultânea de áudio + vídeo e schema `tier_a/0.1`.
- `POST /api/exams` reescrito: hash SHA256, `BackgroundTasks` em thread real, status real (queued/running/processed/failed), upload em `storage/analyses/<hash>/`.
- `GET /api/laudo/{hash}/pdf` — serve o laudo gerado pelo `src/reporting/pdf.py`.
- `POST /api/exams/{id}/reanalyze` — re-roda análise sem novo upload.
- `VALBOT_USE_MOCK_VLM=1` — modo fake pra dev sem GCP configurado.
- `Dockerfile` multi-stage (frontend build + Python + nginx, non-root, HEALTHCHECK).
- `docker-compose.yml` com 4 serviços: api, postgres 16-alpine, cloudflared, code-server.
- `migrations/001_init.sql` — schema Postgres com `exams`, `exam_events`, índices, trigger updated_at.
- `deploy/provision.sh` — script idempotente que cria SA + Artifact Registry + GCS bucket + VM no GCP.
- `Makefile` — `dev`, `test`, `build`, `push`, `deploy`, `logs`, `ssh`, `provision`.
- `pyproject.toml` — config consolidada de ruff, mypy, pytest, coverage.
- `.pre-commit-config.yaml` — ruff + mypy + gitleaks + frontend-lint.
- `.gitignore`, `.gitattributes`, `.editorconfig`, `LICENSE` (MIT), `CONTRIBUTING.md`, `.env.example`, `.dockerignore`.

### Changed
- `frontend/artifacts/valbot/src/components/UploadVideoModal.tsx`: removido `<FlowSelector>` e campo `analysis_flow` — sempre Gemini 3.1 (hardcoded no backend). Defaults sorteiam a cada `open=true` via `useEffect`.
- `tooling/api_stub/server.py:list_videos` — combina uploads novos (`storage/analyses/`) + vídeos legados (`storage/videos/`).

### Fixed
- Página Regras (`/regras`) ficava presa em "Carregando rubrica…" porque o stub ativo não tinha `/api/rubricas/{slug}`.
