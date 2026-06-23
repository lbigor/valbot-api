-- 011_eventos_enquadramento_divergencia.sql
-- Materializa as saídas intermediárias dos motores, dando AUDITABILIDADE à
-- cadeia detecção → enquadramento → comparação (spec §6.3, §7.3, §9.4).

-- Eventos BRUTOS detectados (Motor de Detecção — sem julgamento normativo).
CREATE TABLE IF NOT EXISTS exam_eventos (
    id                   BIGSERIAL PRIMARY KEY,
    exam_id              UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    evento_id            VARCHAR(40) NOT NULL,
    categoria            VARCHAR(40),
    descricao            TEXT,
    timestamp_video_seg  NUMERIC(8,2),
    timestamp_audio_seg  NUMERIC(8,2),
    duracao_seg          NUMERIC(6,2),
    confianca            NUMERIC(4,3),
    canal_evidencia      VARCHAR(10),
    quadrante_origem     VARCHAR(4),
    camera_origem        VARCHAR(20),
    transcricao          TEXT,
    classificacao        VARCHAR(60),       -- p/ comentário inadequado do examinador
    contexto             JSONB DEFAULT '{}'::jsonb,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (exam_id, evento_id)
);
CREATE INDEX IF NOT EXISTS idx_eventos_exam ON exam_eventos (exam_id);

-- ENQUADRAMENTOS (Motor Normativo) — evento → regra da Matriz.
CREATE TABLE IF NOT EXISTS exam_enquadramentos (
    id                    BIGSERIAL PRIMARY KEY,
    exam_id               UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    evento_id             VARCHAR(40) NOT NULL,
    enquadrado            BOOLEAN NOT NULL,
    regra_aplicada        VARCHAR(40),
    artigo_ctb            VARCHAR(120),
    ficha_mbedv           VARCHAR(120),
    natureza              VARCHAR(20),
    peso                  INTEGER,
    excecao_aplicada      VARCHAR(80),
    justificativa         TEXT,
    confianca             NUMERIC(4,3),
    requer_revisao_humana BOOLEAN DEFAULT FALSE,
    matriz_versao         VARCHAR(40),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (exam_id, evento_id, regra_aplicada)
);
CREATE INDEX IF NOT EXISTS idx_enquadramentos_exam ON exam_enquadramentos (exam_id);

-- DIVERGÊNCIA (Motor de Comparação) — 1 por exame.
CREATE TABLE IF NOT EXISTS exam_divergencias (
    exam_id              UUID PRIMARY KEY REFERENCES exams(id) ON DELETE CASCADE,
    tipo_divergencia     VARCHAR(40) NOT NULL,
    subtipos_associados  JSONB DEFAULT '[]'::jsonb,
    resultado_oficial    VARCHAR(16),
    resultado_calculado  VARCHAR(16),
    pontuacao_oficial    INTEGER,
    pontuacao_calculada  INTEGER,
    concorda_resultado   BOOLEAN,
    concorda_pontuacao   BOOLEAN,
    concorda_infracoes   BOOLEAN,
    evidencia_suficiente BOOLEAN DEFAULT TRUE,
    encaminhamento       VARCHAR(20),
    detalhes             JSONB DEFAULT '{}'::jsonb,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_divergencias_tipo ON exam_divergencias (tipo_divergencia);
