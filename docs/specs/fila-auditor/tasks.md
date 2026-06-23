# Tasks — fila-auditor

> Criticidade: 🔴 bloqueante · 🟡 importante · 🟢 incremental. `[x]` feito nesta sessão.

## FASE 1 — Fundação de dados/lógica
- [x] T1.1 🔴 `src/lib/painel.ts`: tipos + 16 condutas MBEDV (Art. CTB) + scoring (1/2/4/6, reprovado se gravíssima OU >4) + `clipMarks`/`initLaudo` + 5 exames mock. (FR-08, FR-09)
- [x] T1.2 🔴 `gravColor`/`fmtDur`/`ptsOf`/`verdictOf` puros e testáveis (constitution §VII — determinismo). (FR-08)

## FASE 2 — Tela imersiva
- [x] T2.1 🔴 `FilaAuditor.tsx`: shell (chrome, dropdown de OS, toggle tema claro/grafite, atalhos). (FR-01, FR-10)
- [x] T2.2 🔴 Viewer + StatStrip + Transport + FrameAnno + gating de 1ª revisão. (FR-02)
- [x] T2.3 🔴 Timeline: Ruler + 3 trilhas (TP/VB/Auditor) + playhead + região divergência/interrupção + drag de marcador. (FR-03)
- [x] T2.4 🔴 Inspector: Comparison + ComiteLaudo (read-only) + laudo/FaultRow + parecer Aprovar/Reprovar com validação de coerência. (FR-04, FR-05, FR-07, FR-08)
- [x] T2.5 🟡 FaultPicker (Matriz MBEDV: busca/filtro/sugestões) + RuleFicha + DetailModal + SupervisorModal. (FR-06, FR-09)

## FASE 3 — Integração no app
- [ ] T3.1 🔴 `src/App.tsx`: rota `/fila-auditor` (default export). (SC-05)
- [ ] T3.2 🔴 `tsc --noEmit` + `pnpm build` verdes na Mac (dev machine). (SC-05)
- [ ] T3.3 🟡 Verificação manual dev local (US1–US5 + edge cases).

## FASE 4 — Entrega
- [ ] T4.1 🔴 Commit + `cstk session pr fila-auditor` (base v2).
- [ ] T4.2 🔴 Deploy `valbot-prod` (build na VM + `docker compose up -d api`) + verificação `/api/health` e `/fila-auditor`.

## FASE 5 — v2 (fora do escopo desta entrega)
- [ ] T5.1 🟢 Wiring à API real (`/api/os`, `/api/os/{id}`, `parecer-auditor`, vídeo Range).
- [ ] T5.2 🟢 Aplicar migrations 009–017 + dados reais de OS.
