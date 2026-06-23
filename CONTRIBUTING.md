# Contribuindo com o valbot

## Setup local em 5 minutos

```bash
git clone <repo> && cd valbot
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt google-cloud-aiplatform google-cloud-storage psycopg2-binary
cd frontend && pnpm install && cd ..
pre-commit install
```

## Rodar dev local

```bash
make dev          # backend (mock VLM) + frontend Vite simultâneos
# ou separadamente:
make api          # FastAPI :8001 com VALBOT_USE_MOCK_VLM=1
make front        # Vite :5173
```

Sem créditos GCP, exporte `VALBOT_USE_MOCK_VLM=1` — backend retorna laudo fake (cinto detectado + motor calado) sem chamar Vertex.

## Antes de cada commit

```bash
pre-commit run --all-files   # ruff + mypy + gitleaks + frontend lint
pytest -q                    # testes Python
cd frontend && pnpm test     # testes Vitest
```

CI roda os mesmos hooks; commit só passa se tudo verde.

## Mensagens de commit (Conventional Commits)

```
<tipo>(<escopo>): <descrição imperativa em 1 linha>

[corpo opcional explicando "porquê" e contexto]
```

**Tipos:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`.

**Exemplos:**
- `feat(upload): randomizar dados de exemplo no modal`
- `fix(rubrica): aceitar slug com / e -`
- `chore(docker): adicionar HEALTHCHECK ao Dockerfile`

## Branching

- `main` é protegida — só recebe via PR com squash merge.
- Branches feature: `feat/<slug-curto>`.
- Branches bug: `fix/<slug-curto>`.
- Refactors maiores: `refactor/<slug>`.

## Padrão de código

- **Python:** ruff format + mypy gradual (`pyproject.toml`). Type hints obrigatórios em código novo.
- **TypeScript:** strict mode no `tsconfig.json`. ESLint + Prettier rodam no pre-commit.
- **Comentários:** apenas para o "porquê" não óbvio. Não documentar o "o quê" — código bem nomeado já faz isso.

## Estrutura

```
src/                    # backend Python
  analysis/             # pipeline VLM (Vertex Gemini)
  api/                  # rotas FastAPI (em refactor)
  reporting/            # geração de PDF (Jinja2 + WeasyPrint)
  rubrics/              # taxonomia CONTRAN 1.020/2025
frontend/artifacts/valbot/  # React + Vite (monorepo pnpm)
tooling/                # scripts (bench, render_timeline, api_stub)
manual/extracted/       # textos CONTRAN/MBEDV
deploy/                 # Dockerfile, nginx, provision.sh, CORS, lifecycle
migrations/             # SQL Postgres
docs/                   # ADRs + runbooks
```

## Architecture Decision Records (ADRs)

Decisões arquiteturais ficam em `docs/adr/NNNN-titulo.md`. Antes de propor mudança grande (banco, framework, modelo), abra um ADR descrevendo: **Contexto**, **Decisão**, **Consequências**.

ADRs existentes:
- `0001-vertex-ai.md` — por que Vertex AI ao invés de OpenRouter direto.
- `0002-cloudflare-tunnel.md` — por que Cloudflare Tunnel vs IP estático + certbot.
- `0003-postgres-na-vm.md` — por que Postgres no container vs Cloud SQL managed.

## Reportar bug / pedir feature

Abra issue no GitHub com:
- O que esperava
- O que aconteceu
- Passos pra reproduzir
- Versão (cabeçalho de qualquer response inclui `engine.model` e git SHA via label da imagem)
