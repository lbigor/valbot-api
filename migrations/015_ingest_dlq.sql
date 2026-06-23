-- 015_ingest_dlq.sql
-- Dead Letter Queue da ingestão (spec §5.6): exames cuja análise falhou de
-- forma persistente (após os retries) são movidos para cá com retenção, em vez
-- de se perderem. Permite reprocessamento manual/automático e alerta.

CREATE TABLE IF NOT EXISTS ingest_dlq (
    id            BIGSERIAL PRIMARY KEY,
    hash          VARCHAR(64),
    numero_os     VARCHAR(80),
    payload       JSONB,
    erro          TEXT,
    tipo_falha    VARCHAR(40),        -- erro_acesso | hash_divergente | payload_incompleto | analise | desconhecido
    tentativas    INTEGER NOT NULL DEFAULT 0,
    criada_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retencao_ate  TIMESTAMPTZ,        -- após esta data pode ser purgada (spec: 7 dias)
    resolvida_em  TIMESTAMPTZ         -- preenchida quando reprocessada com sucesso
);

CREATE INDEX IF NOT EXISTS idx_dlq_pendentes ON ingest_dlq (criada_em) WHERE resolvida_em IS NULL;
CREATE INDEX IF NOT EXISTS idx_dlq_hash ON ingest_dlq (hash);
