# Plano Técnico — fila-auditor

> Consome `spec.md`. Constitution check: §I (IA consultiva — Comitê read-only, Aprovar/Reprovar é ação humana) ✓; §III (explicabilidade — CTB+MBEDV em toda infração) ✓; §V (pontuação fiel) ✓. Sem violações.

## Arquitetura
- **Frontend** React 19 + Vite + wouter + TanStack Query + Tailwind v4, em `frontend/artifacts/valbot`. Design system mesclado (ThemeContext, `ui/valbot/*`, `styles/{design-tokens,base,painel,screens}.css`).
- **Tela**: `src/pages/FilaAuditor.tsx` (default export) — componentes internos: Viewer (+StatStrip, FrameAnno), Transport, Timeline (Ruler + 3 MarkerTrack + playhead + região divergência/interrupção + drag de marcador), Inspector (Comparison + ComiteLaudo + laudo/FaultRow + FaultPicker + RuleFicha + confirmação de parecer), DetailModal, SupervisorModal, HowItWorks. Toggle de tema via `data-dir` (claro/grafite).
- **Lógica/dados**: `src/lib/painel.ts` — tipos, 16 condutas MBEDV (chaveadas por `Art. XXX`), `clipMarks`/`initLaudo`, `ptsOf`/`verdictOf` (pesos 1/2/4/6, reprovado se gravíssima OU >4), `fmtDur`, `gravColor`, 5 exames reais mock.
- **Rota**: `src/App.tsx` → `<Route path="/fila-auditor" component={FilaAuditor} />` (full-screen, fora do AppLayout).

## Dados
- **v1 (atual)**: mock em `painel.ts` (5 exames). 
- **Contrato-alvo (v2)**: `GET /api/os` (fila), `GET /api/os/{id}` (comparação + laudo do Comitê + infrações oficiais×calculadas), `GET /api/exams/{id}/video` (Range), `GET /api/matriz`, `POST /api/os/{id}/parecer-auditor`. Endpoints já existem no `api_stub` (frente api-os, mock quando `VALBOT_DB_DISABLED=1`).

## Decisões
- Porte fiel do protótipo `design/valbot/project/` reusando o `painel.css` mesclado; sem trilha de vídeo na timeline (decisão dos chats — só TP/VB/Auditor); sem TourOverlay na v1.
- Estado de UI/telemetria em `localStorage` (`vb-painel-v3`); persistência de parecer fica para o wiring v2.

## Cenários de teste
- `tsc --noEmit` verde; `pnpm build` verde.
- Manual (dev local): US1–US5 + edge cases (interrompido/concordância/processando).

## Deploy (resumo — detalhe no plano-mãe)
Imagem all-in-one buildada na `valbot-prod` (config `valbot`/Rodrigo) a partir de `git archive`; `docker compose up -d api`; rollback por `IMAGE_TAG`.
