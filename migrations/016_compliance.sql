-- 016_compliance.sql
-- Camada de Compliance: sinais NÃO-pontuáveis que exigem análise humana numa tela
-- dedicada. Reúne conduta inadequada do examinador (§6/§10), conduta do candidato
-- do MBEDV §4-5 (fraude/desacato) e condutas detectadas fora do escopo pontuável
-- do MBEDV (cinto, baliza, técnicas de exame). NUNCA somam pontos no exame.

CREATE TABLE IF NOT EXISTS exam_comentarios_compliance (
    id            BIGSERIAL PRIMARY KEY,
    exam_id       UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    tipo          VARCHAR(30) NOT NULL
                  CHECK (tipo IN ('examinador_inadequado','conduta_candidato','conduta_sem_ficha')),
    origem_codigo VARCHAR(40),                 -- ex: R1020-GR-f (cinto), Art. CTB de origem
    descricao     TEXT,
    timestamp_s   NUMERIC(8,2),
    transcricao   TEXT,
    classificacao VARCHAR(60),
    severidade    VARCHAR(20),                 -- informativo | atencao | grave (compliance, não pontua)
    status        VARCHAR(20) NOT NULL DEFAULT 'pendente'
                  CHECK (status IN ('pendente','analisado','arquivado')),
    analisado_por VARCHAR(200),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_compliance_exam ON exam_comentarios_compliance (exam_id);
CREATE INDEX IF NOT EXISTS idx_compliance_fila ON exam_comentarios_compliance (status, created_at)
    WHERE status = 'pendente';
CREATE INDEX IF NOT EXISTS idx_compliance_tipo ON exam_comentarios_compliance (tipo);
