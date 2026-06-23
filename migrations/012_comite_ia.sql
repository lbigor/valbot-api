-- 012_comite_ia.sql
-- Laudo do Comitê de IA (spec §10). O Comitê é uma 2ª passada do Gemini focada
-- APENAS nas infrações encontradas no vídeo (prompt restrito às condutas que
-- "devem acontecer"), para aprofundar a divergência antes do humano. Nunca
-- decide — só explica e fundamenta (spec §10.1).

CREATE TABLE IF NOT EXISTS exam_comite_laudos (
    id                          BIGSERIAL PRIMARY KEY,
    exam_id                     UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    comite_versao               VARCHAR(40) NOT NULL,
    tipo_divergencia_analisada  VARCHAR(40),
    causas_identificadas        JSONB DEFAULT '[]'::jsonb,
    verificacoes_executadas     JSONB DEFAULT '[]'::jsonb,
    comentarios_examinador      JSONB DEFAULT '[]'::jsonb,
    recomendacao_para_auditor   TEXT,
    conclusao_comite            VARCHAR(60),
    tempo_processamento_seg     NUMERIC(8,2),
    cost_usd                    NUMERIC(8,4),
    raw                         JSONB,                 -- resposta crua do Gemini (debug)
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comite_exam ON exam_comite_laudos (exam_id, created_at DESC);
