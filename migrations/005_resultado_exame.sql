-- =============================================================================
-- 005 — resultado_exame: veredito ORIGINAL informado pelo integrador
--        (DETRAN/auto-escola) no momento do init-upload.
--
-- Diferente da coluna `resultado` (calculada pela análise Valbot a partir de
-- aprovado + gate_rejected + status), `resultado_exame` é o que o EXAMINADOR
-- HUMANO marcou no exame presencial — fonte externa, COFRE, imutável após
-- chegar via integração.
--
-- Valores aceitos:
--   'A' — Aprovado pelo examinador presencial
--   'R' — Reprovado pelo examinador presencial
--   NULL — não informado (uploads antigos / clientes que não enviam)
--
-- Use case: cruzar com `resultado` (Valbot) pra medir concordância humano/IA.
-- =============================================================================

ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS resultado_exame CHAR(1)
    CHECK (resultado_exame IS NULL OR resultado_exame IN ('A', 'R'));

-- Index parcial: queries de auditoria/concordância filtram só os com veredito
CREATE INDEX IF NOT EXISTS idx_exams_resultado_exame
  ON exams(resultado_exame)
  WHERE resultado_exame IS NOT NULL;

-- Expõe na view pra consumo no /api/videos e dashboards
DROP VIEW IF EXISTS v_exams_overview CASCADE;
CREATE VIEW v_exams_overview AS
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
  e.resultado,
  e.resultado_exame,             -- NOVO: veredito original do examinador presencial
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
  (SELECT COUNT(*) FROM exam_events ev WHERE ev.exam_id = e.id) AS event_count
FROM exams e
LEFT JOIN exam_camera_validations cv ON cv.exam_id = e.id;

COMMENT ON COLUMN exams.resultado_exame IS
  'Veredito presencial do examinador (DETRAN). A=Aprovado, R=Reprovado, NULL=não informado. COFRE — vem do init-upload, imutável.';
