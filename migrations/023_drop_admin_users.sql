-- =============================================================================
-- 023 — Aposenta a tabela `admin_users` (migration 018).
--
-- O login e o painel de Usuários foram unificados na tabela `users` (022). A
-- `admin_users` virou backup redundante — os mesmos usuários já existem em
-- `users`. Removida para não haver DUAS fontes de usuário. Nenhum código
-- referencia mais `admin_users` a partir deste ponto.
--
-- Idempotente: DROP TABLE IF EXISTS.
-- =============================================================================

DROP TABLE IF EXISTS admin_users;
