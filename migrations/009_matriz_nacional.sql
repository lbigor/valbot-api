-- 009_matriz_nacional.sql
-- Matriz Nacional de Regras (spec §4) — o ativo central do produto.
-- Vincula cada conduta observável a artigo CTB + ficha MBEDV + natureza + peso
-- + exceções, com versionamento por regra (spec §4.4). Editável sem retreinar
-- a IA: o Motor Normativo lê daqui (fallback p/ taxonomia.py quando vazio).

CREATE TABLE IF NOT EXISTS exam_rules (
    codigo_val              VARCHAR(40) PRIMARY KEY,         -- ex: VAL-CTB-185-I / R1020-G-a
    artigo_ctb              VARCHAR(120),
    ficha_mbedv             VARCHAR(120),
    fonte_normativa         VARCHAR(120) DEFAULT 'Res. CONTRAN 1.020/2025',
    natureza                VARCHAR(20)  NOT NULL CHECK (natureza IN ('leve','media','grave','gravissima','variavel')),
    -- peso NULL quando a gravidade varia por inciso (ex: Art. 181) — peso_variavel=true.
    peso                    INTEGER      CHECK (peso IS NULL OR peso IN (1,2,4,6)),
    peso_variavel           BOOLEAN      NOT NULL DEFAULT FALSE,
    categorias_aplicaveis   JSONB        NOT NULL DEFAULT '["ACC","A","B","C","D","E"]'::jsonb,
    conduta_observavel      TEXT         NOT NULL,
    evidencia_necessaria    TEXT,
    constatacao             TEXT,                            -- "Constatação da infração" (ficha MBEDV)
    informacoes_complementares TEXT,
    quando_pontuar          TEXT,
    quando_nao_pontuar      TEXT,
    tipo_deteccao           VARCHAR(80),                     -- visao_computacional | audio | trajetoria | ...
    confiabilidade_deteccao VARCHAR(10)  DEFAULT 'media' CHECK (confiabilidade_deteccao IN ('alta','media','baixa')),
    requer_revisao_humana   BOOLEAN      NOT NULL DEFAULT FALSE,
    comentario_juridico     TEXT,
    versao_regra            VARCHAR(20)  NOT NULL DEFAULT 'v1.0',
    vigencia_inicio         DATE         NOT NULL DEFAULT '2026-02-01',
    vigencia_fim            DATE,                            -- NULL = vigente
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exam_rules_vigentes ON exam_rules (codigo_val) WHERE vigencia_fim IS NULL;
CREATE INDEX IF NOT EXISTS idx_exam_rules_natureza ON exam_rules (natureza);

-- Snapshot consolidado da Matriz (versão completa — spec §4.4).
CREATE TABLE IF NOT EXISTS matriz_versoes (
    versao      VARCHAR(40) PRIMARY KEY,                     -- matriz-nacional-v1.2
    descricao   TEXT,
    snapshot    JSONB,                                       -- cópia das regras vigentes no momento
    vigente     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
