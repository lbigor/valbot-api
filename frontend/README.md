# VALBOT — Frontend

React 19 + Vite + TypeScript + Tailwind + Radix UI + TanStack Query + Wouter.
Portado de `valbot_old/v2/frontend/` (v2 era o frontend ativo em produção no LaudoAI).

## Rodar em dev

```bash
pnpm install
pnpm --filter @workspace/valbot dev
```

Sobe em `http://localhost:5173` (`PORT` env muda a porta; `BASE_PATH` muda o prefixo). O proxy `/api/*`, `/static/*` e `/v2/*` aponta para `BACKEND_URL` (default `http://localhost:8001`).

## Status

**WIP — aguarda backend.** O app consome ~10 endpoints FastAPI (`/api/auth/*`, `/api/videos`, `/api/exams`, `/api/analyses/:hash/*`, `/api/dashboard/kpis`, `/api/rubricas/:slug`, `/api/alertas`). O backend ainda não existe neste projeto. Em dev, as telas carregam visualmente, mas as chamadas fetch vão falhar até a API estar no ar.

## Estrutura

Monorepo pnpm com workspace único em `artifacts/valbot/`:

```
frontend/
├── package.json
├── pnpm-workspace.yaml
├── tsconfig.base.json
└── artifacts/valbot/
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    ├── src/
    │   ├── components/    # shadcn/ui + Radix
    │   ├── pages/         # Dashboard, FilaOperacional, Videos, AnaliseExame, ...
    │   ├── contexts/      # AuthContext, DemoContext
    │   └── types/laudo.ts # contrato com backend
    └── public/
```

## Build

```bash
pnpm --filter @workspace/valbot build   # gera artifacts/valbot/dist/
pnpm --filter @workspace/valbot serve   # preview do build
```
