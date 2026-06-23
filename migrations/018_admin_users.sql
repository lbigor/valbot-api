-- =============================================================================
-- 017 — Usuários administrativos do painel (/admin) com senha.
-- Login real (email + senha) para a porta de entrada https://valbot.com.br/admin.
-- password_hash = PBKDF2-HMAC-SHA256, formato `pbkdf2_sha256$iters$salt_hex$hash_hex`
--   (stdlib hashlib — sem dependência nativa nova no build de produção).
-- role = papel da sessão (admin | auditor | supervisor); o painel exige admin.
-- revoked_at NULL = ativo. Set NOW() pra revogar sem apagar histórico.
-- =============================================================================

CREATE TABLE IF NOT EXISTS admin_users (
    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email          VARCHAR(255) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    role           VARCHAR(32)  NOT NULL DEFAULT 'admin',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login_at  TIMESTAMPTZ,
    revoked_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(LOWER(email)) WHERE revoked_at IS NULL;

-- Seed do 1º administrador. Senha inicial entregue fora do versionamento
-- (ver descrição do PR); recomenda-se trocá-la após o primeiro acesso.
-- email normalizado em minúsculas; ON CONFLICT mantém idempotência do migration.
INSERT INTO admin_users (email, password_hash, role)
VALUES (
    'rodrigo@valmatech.com.br',
    'pbkdf2_sha256$200000$45a8d017d1b95a89c8134cc33279c6c3$36521f0cbcae03787cb00606389bf527d31afe3d06ea29b4e70a0007d5c9dc10',
    'admin'
)
ON CONFLICT (email) DO NOTHING;
