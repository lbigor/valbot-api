-- =============================================================================
-- 022 — Tabela ÚNICA de usuários do painel + login: `users`.
--
-- Versiona o schema que já vive em produção (criado fora de migração nas
-- customizations da VM). Unifica autenticação e gestão de usuários numa só
-- tabela: login do SPA e painel de Usuários operam sobre `users`; `admin_users`
-- (migration 018) é aposentada pela 023. `role` define admin/auditor/etc via
-- flag, sem tabela separada.
--
-- senha_hash = PBKDF2-HMAC-SHA256 no formato `pbkdf2_sha256$iters$salt$hash`
--   (salt como STRING hex — ver server._verify_password / db._hash_password_login).
-- senha_temporaria = TRUE após reset do admin: o login confere a senha mas NÃO
--   cria sessão; o front força a troca via /api/auth/change-password.
--
-- Idempotente: CREATE TABLE IF NOT EXISTS. O 1º admin é semeado em runtime por
-- server._seed_admin_from_env (VALBOT_ADMIN_EMAIL / VALBOT_ADMIN_PASSWORD).
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    email              VARCHAR(200) PRIMARY KEY,
    senha_hash         TEXT,
    role               VARCHAR(20)  NOT NULL DEFAULT 'admin',
    nome               VARCHAR(200),
    ativo              BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    telefone           VARCHAR(20),
    pode_enviar_laudos BOOLEAN      NOT NULL DEFAULT FALSE,
    senha_temporaria   BOOLEAN      NOT NULL DEFAULT FALSE,
    id                 UUID         NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    revoked_at         TIMESTAMPTZ,
    last_login_at      TIMESTAMPTZ
);

-- Telefone é login alternativo (único quando informado).
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_telefone ON users (telefone) WHERE telefone IS NOT NULL;
