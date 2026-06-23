# Roadmap — Valbot como SaaS completo

Gap-analysis (o que já existe vs o que falta) para transformar o Valbot num SaaS cobrável e multi-tenant. Estimativas em dias de eng.

## Estado atual (✅ feito)
- Pipeline IA: 5 motores + Comitê de IA (reavalia com prompt MBEDV).
- **Comitê→Fila**: só exames que ainda divergem pós-comitê entram na Fila do Auditor.
- Fluxo OS (Ordem de Serviço) Auditor→Supervisor: **backend completo** (modelos, migrations 013/017, endpoints `/api/v2/os/*`).
- Auth: login-piloto (email+cargo) + AdminLogin `/admin` (senha PBKDF2, `admin_users`), sessão httpOnly.
- Custos: `cost_usd`/`cost_tokens_in/out` por exame + **dashboard `/custos`** (agregação dia/unidade/categoria).

## Fase 1 — Quick wins (10–16 dias)
1. **Custos** ✅ parcial (dashboard feito) — falta: export CSV/PDF, custo por motor, alertas de threshold.
2. **Tela de Supervisor** (3–5d): backend pronto; falta UI (listar OS `aguardando_supervisor`, ver parecer do auditor, registrar decisão homologa/reforma).
3. **Endpoint custos no backend de prod** (1–2d): reconciliar `customizations/server.py` ↔ repo e deployar.

## Fase 2 — Tenant & Billing (22–28 dias)
4. **Multi-tenant soft** (4–5d): coluna `tenant_id` em todas as tabelas + RLS Postgres + middleware.
5. **Billing schema** (3–4d): `tenants`, `subscriptions`, `pricing_plans`, `invoices`, `usage`.
6. **Dashboard admin de tenants** (7–10d) + **self-service billing** (4–5d).
7. **Faturamento mensal automático** (3–4d) + **Stripe** (5–7d).

## Fase 3 — Gestão de usuários (13–18 dias)
8. **CRUD de usuários** `/admin/usuarios` (5–7d): listar/criar/editar/revogar papéis (auditor/supervisor/admin).
9. **Invite flow** (token+email, 4–5d) + **reset de senha self-service** (2–3d) + **audit de logins** (2–3d).

## Fase 4 — Observabilidade (7–11 dias)
10. Structured logging (trace_id/tenant_id), métricas Prometheus, alerting, OpenAPI.

**Total estimado: ~64–90 dias (2 devs fullstack, ~3–4 meses).**

> Detalhe completo do gap-analysis por arquivo:linha gerado na sessão de 2026-06-15.
