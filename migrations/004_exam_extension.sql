-- =============================================================================
-- 004 — extensão pra cobrir gate de admissibilidade, métricas, custo,
--        infrações filhas, ground truth Gemini e anotações do usuário.
--
-- Objetivo: tornar o Postgres a FONTE DE VERDADE da fila operacional.
-- Hoje, ~70% dos campos (gate, infrações, custo, validação independente)
-- vivem apenas em arquivos JSON no filesystem; isso impede query, dashboards,
-- triggers de consistência e auditoria SQL.
--
-- Estratégia (faseada):
--   F1 (este script): só DDL — extende `exams` + cria tabelas filhas + view +
--                     trigger de auditoria. NÃO toca em nenhuma row existente.
--   F2: dual-write no pipeline (file + DB)
--   F3: backfill retroativo dos 39 registros legados
--   F4: GET /api/videos lê do DB (com fallback file via toggle env)
--   F5: remove leitura file no caminho quente; arquivos viram backup/replay
--   F6: UI consome o `resultado` computed direto
--
-- Idempotente: usa IF NOT EXISTS em tudo. ALTER ADD COLUMN IF NOT EXISTS.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. exams — colunas novas pra gate, métricas, custo
-- -----------------------------------------------------------------------------
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS size_bytes        BIGINT,
  ADD COLUMN IF NOT EXISTS duration_s        NUMERIC(8,2),
  -- Gate de admissibilidade (PASSO 0 do preset v25): NULL = não-avaliado ainda;
  -- TRUE = vídeo não passou (não é Cat B / layout incompleto / fab desconhecido);
  -- FALSE = passou, partiu pra análise de infrações.
  ADD COLUMN IF NOT EXISTS gate_rejected     BOOLEAN,
  ADD COLUMN IF NOT EXISTS gate_motivo       VARCHAR(40),
  ADD COLUMN IF NOT EXISTS gate_detalhes     TEXT,
  -- Custo da chamada Gemini — usado pra dashboards de $$
  ADD COLUMN IF NOT EXISTS cost_usd          NUMERIC(8,4),
  ADD COLUMN IF NOT EXISTS cost_tokens_in    INTEGER,
  ADD COLUMN IF NOT EXISTS cost_tokens_out   INTEGER,
  ADD COLUMN IF NOT EXISTS gemini_elapsed_s  NUMERIC(6,2),
  -- Engine info movida pra colunas próprias (antes spread em outros lugares)
  ADD COLUMN IF NOT EXISTS num_infracoes     INTEGER,
  -- Fabricante de câmera detectado pelo layout
  ADD COLUMN IF NOT EXISTS layout_confianca  NUMERIC(4,3),
  -- Path do PDF gerado (alias de gs_laudo_pdf — file local na verdade)
  ADD COLUMN IF NOT EXISTS pdf_path          VARCHAR(500);

-- -----------------------------------------------------------------------------
-- 2. Coluna computed `resultado` — fonte única da verdade da UI
-- -----------------------------------------------------------------------------
-- 6 estados possíveis:
--   PENDENTE       — ainda na fila / fazendo upload / streaming
--   PROCESSANDO    — Gemini rodando
--   FALHOU         — erro no pipeline
--   SEM_AVALIACAO  — gate rejeitou (não é exame Cat B válido)
--   APROVADO       — passou, pontuação ≤ limite
--   INAPTO         — passou no gate mas reprovado por pontuação
-- Sem coluna computed, essa lógica vivia espalhada no frontend (errada,
-- mostrava "INAPTO" pra gate-rejected — ver bug Cat A reportado).
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS resultado VARCHAR(16) GENERATED ALWAYS AS (
    CASE
      WHEN status IN ('queued','uploading','streaming_s3','pending') THEN 'PENDENTE'
      WHEN status IN ('running','processing')                        THEN 'PROCESSANDO'
      WHEN status = 'failed'                                         THEN 'FALHOU'
      WHEN gate_rejected = TRUE                                      THEN 'SEM_AVALIACAO'
      WHEN aprovado = TRUE                                           THEN 'APROVADO'
      WHEN aprovado = FALSE                                          THEN 'INAPTO'
      ELSE 'INDEFINIDO'
    END
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_exams_resultado ON exams(resultado);
CREATE INDEX IF NOT EXISTS idx_exams_categoria ON exams(categoria);
CREATE INDEX IF NOT EXISTS idx_exams_gate_rejected
  ON exams(gate_rejected) WHERE gate_rejected IS NOT NULL;

-- -----------------------------------------------------------------------------
-- 3. exam_infractions — infrações detectadas (filha 1:N de exams)
--    Hoje vive como array em `result.infracoes_detectadas`. Promover pra
--    tabela permite filtrar por regra, contar por gravidade, joinar com
--    rubrica (futura), gerar relatórios SQL.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exam_infractions (
  id              BIGSERIAL    PRIMARY KEY,
  exam_id         UUID         NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
  regra_id        VARCHAR(20)  NOT NULL,        -- ex: R1020-G-5
  gravidade       VARCHAR(20)  NOT NULL,        -- leve, media, grave, gravissima, eliminatoria, etica
  pontos          INTEGER      NOT NULL,
  descricao       TEXT,
  timestamp_s     NUMERIC(8,2),
  duracao_s       NUMERIC(6,2),
  cameras         JSONB,                        -- array de strings: ["frontal","interna"]
  confianca       NUMERIC(4,3),                 -- 0.000 - 1.000
  evidence        TEXT,
  base_legal      TEXT,
  status          VARCHAR(20)  DEFAULT 'detectada',  -- detectada, confirmada, descartada
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_infractions_exam     ON exam_infractions(exam_id);
CREATE INDEX IF NOT EXISTS idx_infractions_regra    ON exam_infractions(regra_id);
CREATE INDEX IF NOT EXISTS idx_infractions_grav     ON exam_infractions(gravidade);
-- Idempotência: evita duplicar infrações de uma mesma re-análise.
-- Combinação exam+regra+timestamp é única (mesma infração no mesmo segundo).
CREATE UNIQUE INDEX IF NOT EXISTS uq_infractions_exam_regra_ts
  ON exam_infractions(exam_id, regra_id, COALESCE(timestamp_s, 0));

-- -----------------------------------------------------------------------------
-- 4. exam_camera_validations — ground truth Gemini independente
--    Hoje em /opt/valbot/storage/camera_validation/_summary.json — single file
--    sem schema. Vira tabela pra cruzar com gate v25 em SQL e medir FN/FP.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exam_camera_validations (
  exam_id           UUID         PRIMARY KEY REFERENCES exams(id) ON DELETE CASCADE,
  validador         VARCHAR(40)  NOT NULL,        -- ex: "gemini-3.1-pro-preview"
  veredito          VARCHAR(20)  NOT NULL,        -- HOMO / NAO_HOMO
  fabricante        VARCHAR(20),                  -- HIK / VIP / desconhecido
  confianca         NUMERIC(4,3),
  motivo            TEXT,
  cost_usd          NUMERIC(6,4),
  validated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_camera_val_veredito ON exam_camera_validations(veredito);

-- -----------------------------------------------------------------------------
-- 5. exam_annotations — comentários do usuário sobre infrações/laudos
--    Hoje em localStorage do browser — perde se trocar de máquina. Move pra
--    DB pra permitir multi-usuário e histórico.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exam_annotations (
  id            BIGSERIAL    PRIMARY KEY,
  exam_id       UUID         NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
  infraction_id BIGINT       REFERENCES exam_infractions(id) ON DELETE SET NULL,
  user_email    VARCHAR(200) NOT NULL,
  timestamp_s   NUMERIC(8,2),                    -- onde no vídeo o comentário se ancora
  body          TEXT         NOT NULL,
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_annotations_exam ON exam_annotations(exam_id, created_at DESC);

DROP TRIGGER IF EXISTS annotations_set_updated_at ON exam_annotations;
CREATE TRIGGER annotations_set_updated_at
  BEFORE UPDATE ON exam_annotations
  FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();

-- -----------------------------------------------------------------------------
-- 6. Trigger: status mudou → loga em exam_events
--    Hoje exam_events só recebe inserts manuais via log_event() do db.py
--    (chamado em poucos lugares). Trigger garante que TODA mudança de status
--    fica auditada sem depender de chamada manual.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_exams_log_status_change() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.status IS DISTINCT FROM OLD.status THEN
    INSERT INTO exam_events (exam_id, action, details)
    VALUES (
      NEW.id,
      NEW.status,
      jsonb_build_object(
        'from',      OLD.status,
        'to',        NEW.status,
        'aprovado',  NEW.aprovado,
        'resultado', NEW.resultado
      )
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS exams_log_status_change ON exams;
CREATE TRIGGER exams_log_status_change
  AFTER UPDATE OF status ON exams
  FOR EACH ROW EXECUTE FUNCTION trg_exams_log_status_change();

-- -----------------------------------------------------------------------------
-- 7. VIEW v_exams_overview — feed pra GET /api/videos (substitui file-walking)
--    Materializa o JOIN exams + última camera_validation + count de infrações.
--    Frontend não precisa mais derivar status/resultado.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_exams_overview AS
SELECT
  e.id,
  e.hash,
  e.external_id,
  e.candidato_nome,
  e.candidato_cpf,
  e.renach,
  e.examinador,
  e.local_unidade,
  e.auto_escola,
  e.categoria,
  e.veiculo,
  e.status,
  e.resultado,                              -- computed STORED column
  e.aprovado,
  e.pontuacao_total,
  e.gate_rejected,
  e.gate_motivo,
  e.gate_detalhes,
  e.size_bytes,
  CASE WHEN e.size_bytes IS NOT NULL
       THEN ROUND(e.size_bytes::numeric / 1048576, 2)
       ELSE NULL END                        AS size_mb,
  e.duration_s,
  e.num_infracoes,
  e.layout_confianca,
  e.fabricante_provavel,
  e.cost_usd,
  e.cost_tokens_in,
  e.cost_tokens_out,
  e.gemini_elapsed_s,
  e.engine_backend,
  e.engine_model,
  e.engine_preset,
  e.gs_video,
  e.gs_result_json,
  e.gs_laudo_pdf,
  e.pdf_path,
  cv.veredito           AS validator_veredito,
  cv.confianca          AS validator_confianca,
  cv.motivo             AS validator_motivo,
  cv.fabricante         AS validator_fabricante,
  e.created_at,
  e.updated_at,
  -- Quantas vezes o status mudou (vindo da auditoria — proxy de "atividade")
  (SELECT COUNT(*) FROM exam_events ev WHERE ev.exam_id = e.id) AS event_count
FROM exams e
LEFT JOIN exam_camera_validations cv ON cv.exam_id = e.id;

COMMENT ON VIEW v_exams_overview IS
  'Feed da UI/api de fila. Substitui leitura de upload.json+result.json+status.json. F4 migra GET /api/videos pra ler daqui.';

-- -----------------------------------------------------------------------------
-- 8. VIEW v_exams_metrics — dashboard agregado (custo total, taxa REJ, etc)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_exams_metrics AS
SELECT
  DATE_TRUNC('day', created_at)              AS dia,
  COUNT(*)                                   AS total_exames,
  COUNT(*) FILTER (WHERE resultado='APROVADO')     AS aprovados,
  COUNT(*) FILTER (WHERE resultado='INAPTO')       AS inaptos,
  COUNT(*) FILTER (WHERE resultado='SEM_AVALIACAO') AS sem_avaliacao,
  COUNT(*) FILTER (WHERE resultado='FALHOU')        AS falhos,
  COUNT(*) FILTER (WHERE resultado='PROCESSANDO')   AS processando,
  COUNT(*) FILTER (WHERE resultado='PENDENTE')      AS pendentes,
  SUM(cost_usd)                                     AS custo_total_usd,
  AVG(gemini_elapsed_s)                             AS gemini_avg_s,
  SUM(size_bytes) / 1073741824.0                    AS gb_processados
FROM exams
GROUP BY DATE_TRUNC('day', created_at);

COMMENT ON VIEW v_exams_metrics IS
  'Agregado diário. Alimenta Dashboard.tsx no lugar das métricas mock.';
