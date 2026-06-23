-- =============================================================================
-- 020 — Telemetria de produtividade do Auditor (tela "Medição").
--
-- Cada linha registra UMA sessão de revisão de um exame por um auditor: quanto
-- do vídeo ele de fato assistiu (`assistido_ate_seg`), a duração do vídeo
-- (`dur_seg`), o tempo total que ficou na sessão (`tempo_sessao_s`) e quantas
-- vezes o front bloqueou um "avançar" antes do mínimo assistido
-- (`avancos_bloqueados`).
--
-- Alimenta GET /api/dashboard/auditor-metrics — % assistido médio, exames por
-- auditor, série temporal. As métricas de concordância auditor×IA vêm de
-- `auditor_pareceres` (migration 017), não daqui.
--
-- Idempotente: CREATE TABLE IF NOT EXISTS.
-- =============================================================================

CREATE TABLE IF NOT EXISTS auditor_telemetria (
  id                 BIGSERIAL    PRIMARY KEY,
  auditor            VARCHAR(200),                 -- email/identificacao do auditor
  exam_hash          VARCHAR(64),                  -- exame revisado (denormalizado p/ join leve)
  assistido_ate_seg  NUMERIC,                      -- maior offset do video efetivamente assistido (s)
  dur_seg            NUMERIC,                      -- duracao total do video (s)
  tempo_sessao_s     NUMERIC,                      -- tempo de parede da sessao de revisao (s)
  avancos_bloqueados INTEGER      NOT NULL DEFAULT 0,  -- no de tentativas de avancar bloqueadas
  created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auditor_telemetria_auditor
  ON auditor_telemetria (auditor);
CREATE INDEX IF NOT EXISTS idx_auditor_telemetria_created
  ON auditor_telemetria (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auditor_telemetria_exam
  ON auditor_telemetria (exam_hash);

COMMENT ON TABLE auditor_telemetria IS
  'Telemetria por sessao de revisao do Auditor - base da tela Medicao.';
COMMENT ON COLUMN auditor_telemetria.assistido_ate_seg IS
  'Maior offset (s) do video que o auditor de fato assistiu. pct assistido = assistido_ate_seg / dur_seg.';
