-- =============================================================================
-- 002 — API keys p/ autenticar clientes server-to-server.
-- key_hash = SHA-256 hex da key plaintext. Plaintext só é mostrado 1× ao criar.
-- scopes = lista jsonb tipo ["exams:create"]. Verificação por contains.
-- revoked_at NULL = ativa. Set NOW() pra revogar.
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(100) NOT NULL UNIQUE,
    key_hash      VARCHAR(64)  NOT NULL UNIQUE,
    scopes        JSONB        NOT NULL DEFAULT '[]'::jsonb,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_used_at  TIMESTAMPTZ,
    revoked_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash) WHERE revoked_at IS NULL;
