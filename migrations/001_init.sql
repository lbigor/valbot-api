-- =============================================================================
-- valbot — schema inicial (Postgres 16+).
-- Carregado automaticamente pelo docker-entrypoint-initdb.d na primeira boot
-- do container `postgres`. Idempotente via `IF NOT EXISTS`.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS exams (
    id                       UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    hash                     VARCHAR(64)  NOT NULL UNIQUE,

    -- candidato
    candidato_nome           VARCHAR(200),
    candidato_cpf            VARCHAR(20),
    renach                   VARCHAR(50),
    processo                 VARCHAR(50),
    categoria                VARCHAR(5),

    -- exame
    veiculo                  VARCHAR(100),
    local_unidade            VARCHAR(100),
    examinador               VARCHAR(200),
    auto_escola              VARCHAR(200),
    rubrica                  VARCHAR(20)  NOT NULL DEFAULT '1020/2025',
    training_annotations     TEXT,

    -- pipeline
    status                   VARCHAR(20)  NOT NULL DEFAULT 'queued',
    error                    TEXT,
    gs_video                 VARCHAR(500),
    gs_result_json           VARCHAR(500),
    gs_laudo_pdf             VARCHAR(500),

    -- resultado denormalizado (para listagem rápida sem ler GCS)
    layout_detectado         JSONB,
    duracao_s                NUMERIC(10,2),
    pontuacao_total          INTEGER,
    aprovado                 BOOLEAN,
    fabricante_provavel      VARCHAR(20),

    -- engine
    engine_backend           VARCHAR(40)  DEFAULT 'vertex_gemini',
    engine_model             VARCHAR(100) DEFAULT 'gemini-3.1-pro-preview',
    engine_preset            VARCHAR(60)  DEFAULT 'v25/valbot-r1-vip-v25',

    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exams_status     ON exams(status);
CREATE INDEX IF NOT EXISTS idx_exams_created_at ON exams(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_exams_examinador ON exams(examinador);

-- Trigger pra atualizar updated_at automaticamente.
CREATE OR REPLACE FUNCTION trg_set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS exams_set_updated_at ON exams;
CREATE TRIGGER exams_set_updated_at
    BEFORE UPDATE ON exams
    FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();

-- Tabela de eventos (auditoria — quem fez o quê).
CREATE TABLE IF NOT EXISTS exam_events (
    id          BIGSERIAL    PRIMARY KEY,
    exam_id     UUID         NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    actor       VARCHAR(100),
    action      VARCHAR(40)  NOT NULL,    -- uploaded, queued, running, processed, failed, manual_review
    details     JSONB,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_exam_events_exam ON exam_events(exam_id, created_at DESC);
