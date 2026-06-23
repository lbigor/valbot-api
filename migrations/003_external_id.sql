-- =============================================================================
-- 003 — external_id: ID do integrador externo (ex: DETRAN) associado ao exame.
-- BIGINT NULL pra suportar payload {"id": 784562, ...} no init-upload em lote.
-- Não-UNIQUE intencional — `hash` (analysis_id UUID hex) segue sendo a chave.
-- Índice parcial pra acelerar GET /api/exams?external_id=...
-- Forward-compat: NULL default, código antigo segue ignorando a coluna.
-- =============================================================================

ALTER TABLE exams ADD COLUMN IF NOT EXISTS external_id BIGINT NULL;

CREATE INDEX IF NOT EXISTS idx_exams_external_id
    ON exams(external_id)
    WHERE external_id IS NOT NULL;
