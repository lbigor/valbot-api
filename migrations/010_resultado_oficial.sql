-- 010_resultado_oficial.sql
-- Expande `exams` com os campos do payload de evidências (spec §5.4) que faltavam
-- e cria a lista discreta de infrações apontadas oficialmente pela Comissão —
-- pré-requisito para as divergências 2/3/4 (spec §9).

ALTER TABLE exams ADD COLUMN IF NOT EXISTS unidade                VARCHAR(120);
ALTER TABLE exams ADD COLUMN IF NOT EXISTS tipo_exame             VARCHAR(40);
ALTER TABLE exams ADD COLUMN IF NOT EXISTS examinador_matricula   VARCHAR(60);
ALTER TABLE exams ADD COLUMN IF NOT EXISTS examinador_eh_preposto BOOLEAN DEFAULT FALSE;
ALTER TABLE exams ADD COLUMN IF NOT EXISTS data_hora_exame        TIMESTAMPTZ;

-- Resultado OFICIAL detalhado (vem da Comissão via integração).
ALTER TABLE exams ADD COLUMN IF NOT EXISTS pontuacao_oficial      INTEGER;
ALTER TABLE exams ADD COLUMN IF NOT EXISTS houve_interrupcao      BOOLEAN DEFAULT FALSE;
ALTER TABLE exams ADD COLUMN IF NOT EXISTS motivo_interrupcao     TEXT;

-- Resultado CALCULADO pelo Val (Motor de Pontuação) — derivado, re-gerável.
ALTER TABLE exams ADD COLUMN IF NOT EXISTS resultado_calculado    VARCHAR(16);
ALTER TABLE exams ADD COLUMN IF NOT EXISTS pontuacao_calculada    INTEGER;
ALTER TABLE exams ADD COLUMN IF NOT EXISTS matriz_versao          VARCHAR(40);

-- Infrações apontadas OFICIALMENTE (lista discreta de artigos CTB).
CREATE TABLE IF NOT EXISTS exam_infracoes_oficiais (
    id          BIGSERIAL PRIMARY KEY,
    exam_id     UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    artigo_ctb  VARCHAR(120) NOT NULL,
    natureza    VARCHAR(20),
    peso        INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (exam_id, artigo_ctb)
);

CREATE INDEX IF NOT EXISTS idx_infracoes_oficiais_exam ON exam_infracoes_oficiais (exam_id);
