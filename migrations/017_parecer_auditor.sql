-- =============================================================================
-- 017 — Ordens de Serviço (OS), Comitê, Parecer do Auditor e Matriz de Regras.
--
-- A esteira de auditoria humana do VALBOT tem três atores em sequência:
--
--   IA (Comitê) → Auditor → Supervisor
--
-- 1. Quando a IA fecha um laudo que DIVERGE do veredito presencial do
--    examinador (ou tem baixa confiança), o sistema abre uma Ordem de Serviço
--    (`ordens_servico`) e anexa o laudo consolidado do "Comitê" de modelos
--    (`exam_comite_laudos`) — causas, verificações executadas, recomendação.
-- 2. O Auditor analisa a OS e grava um parecer (`auditor_pareceres`):
--    concorda/discorda do resultado, lista as infrações que mantém, justifica.
--    A OS passa a `aguardando_supervisor`.
-- 3. O Supervisor toma a decisão final (`supervisor_decisoes`), encerrando a OS.
--
-- Toda transição de estado é auditada em `os_eventos` (espelho de exam_events,
-- mas com escopo de OS). A Matriz de regras vigentes vive em `exam_rules`
-- (snapshot editável da taxonomia 1.020/2025) e seus snapshots versionados
-- em `matriz_versoes`.
--
-- Idempotente: CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS.
-- Estados da OS: criada | aguardando_auditor | em_analise |
--                aguardando_supervisor | decisao_final | encerrada
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Ordem de Serviço — uma fila de trabalho por exame divergente.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ordens_servico (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  numero_os        VARCHAR(32) UNIQUE NOT NULL,            -- ex: OS-2026-000123
  exam_id          UUID REFERENCES exams(id) ON DELETE CASCADE,
  exam_hash        VARCHAR(64),                            -- denormalizado p/ lookup rápido
  tipo_divergencia VARCHAR(40),                            -- resultado | pontuacao | infracoes | confianca
  status           VARCHAR(32) NOT NULL DEFAULT 'criada',
  -- Snapshot do veredito oficial (presencial) x calculado (IA) no momento da abertura.
  resultado_oficial   VARCHAR(1),                          -- A | R | N
  resultado_calculado VARCHAR(1),                          -- A | R | N
  pontuacao_oficial   INTEGER,
  pontuacao_calculada INTEGER,
  sla_due_at       TIMESTAMPTZ,                            -- prazo de atendimento
  aberta_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  encerrada_em     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_os_status      ON ordens_servico(status);
CREATE INDEX IF NOT EXISTS idx_os_exam        ON ordens_servico(exam_id);
CREATE INDEX IF NOT EXISTS idx_os_tipo        ON ordens_servico(tipo_divergencia);

COMMENT ON TABLE ordens_servico IS
  'Fila de trabalho do Auditor. Uma OS por exame com divergência IA x examinador.';
COMMENT ON COLUMN ordens_servico.status IS
  'criada | aguardando_auditor | em_analise | aguardando_supervisor | decisao_final | encerrada';

-- -----------------------------------------------------------------------------
-- Eventos da OS — trilha de auditoria das transições de estado.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS os_eventos (
  id         BIGSERIAL PRIMARY KEY,
  os_id      UUID REFERENCES ordens_servico(id) ON DELETE CASCADE,
  ator       VARCHAR(120),                                 -- email/role de quem agiu
  action     VARCHAR(60) NOT NULL,                         -- aberta | parecer_auditor | decisao_supervisor | encerrada
  de_status  VARCHAR(32),
  para_status VARCHAR(32),
  details    JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_os_eventos_os ON os_eventos(os_id);

-- -----------------------------------------------------------------------------
-- Laudo do Comitê — consolidação da IA anexada à OS.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exam_comite_laudos (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  os_id     UUID REFERENCES ordens_servico(id) ON DELETE CASCADE,
  exam_id   UUID REFERENCES exams(id) ON DELETE CASCADE,
  causas_identificadas              JSONB NOT NULL DEFAULT '[]'::jsonb,
  verificacoes_executadas           JSONB NOT NULL DEFAULT '[]'::jsonb,
  comentarios_examinador_detectados JSONB NOT NULL DEFAULT '[]'::jsonb,
  recomendacao_para_auditor         TEXT,
  conclusao_comite                  TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_comite_os ON exam_comite_laudos(os_id);

-- -----------------------------------------------------------------------------
-- Parecer do Auditor — decisão humana de 1ª instância sobre a OS.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS auditor_pareceres (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  os_id            UUID REFERENCES ordens_servico(id) ON DELETE CASCADE,
  exam_id          UUID REFERENCES exams(id) ON DELETE CASCADE,
  auditor          VARCHAR(120),                           -- email/identificação do auditor
  decisao          VARCHAR(16) NOT NULL,                   -- concorda | discorda
  resultado_final  VARCHAR(16),                            -- aprovado | reprovado
  infracoes        JSONB NOT NULL DEFAULT '[]'::jsonb,     -- infrações mantidas pelo auditor
  justificativa    TEXT,
  referencia_mbedv VARCHAR(120),                           -- ficha/seção do MBEDV citada
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (os_id)                                           -- um parecer ativo por OS (upsert)
);
CREATE INDEX IF NOT EXISTS idx_parecer_exam ON auditor_pareceres(exam_id);

COMMENT ON TABLE auditor_pareceres IS
  'Parecer do Auditor sobre uma OS. UNIQUE(os_id) → upsert sobrescreve rascunho.';

-- -----------------------------------------------------------------------------
-- Decisão do Supervisor — instância final (encerra a OS).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS supervisor_decisoes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  os_id           UUID REFERENCES ordens_servico(id) ON DELETE CASCADE,
  supervisor      VARCHAR(120),
  decisao         VARCHAR(16) NOT NULL,                    -- homologa | reforma
  resultado_final VARCHAR(16),                             -- aprovado | reprovado
  justificativa   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (os_id)
);

-- -----------------------------------------------------------------------------
-- Matriz de regras vigentes — snapshot editável da taxonomia 1.020/2025.
-- Quando vazia, a API cai no parser de /api/rubricas (CATALOGO em código).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exam_rules (
  codigo_val    VARCHAR(40) PRIMARY KEY,                   -- ex: R1020-G-a
  rubrica       VARCHAR(20) NOT NULL DEFAULT '1020/2025',
  gravidade     VARCHAR(16) NOT NULL,                      -- leve | media | grave | gravissima
  pontos        INTEGER NOT NULL,                          -- 1 | 2 | 4 | 6
  descricao     TEXT,
  base_legal    TEXT,
  cameras       JSONB NOT NULL DEFAULT '[]'::jsonb,
  ativo         BOOLEAN NOT NULL DEFAULT TRUE,
  vlm_prompt_hint TEXT,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- Versões da Matriz — snapshots imutáveis pra auditoria/rollback.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS matriz_versoes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  versao      VARCHAR(40) NOT NULL,                        -- ex: 2026-06-14T12:00 ou v1
  autor       VARCHAR(120),
  nota        TEXT,
  snapshot    JSONB NOT NULL DEFAULT '[]'::jsonb,          -- cópia das regras no momento
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_matriz_versoes_created ON matriz_versoes(created_at DESC);
