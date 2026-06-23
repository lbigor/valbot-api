-- =============================================================================
-- 008 — Rastreio do envio do laudo pra Unidade Gestora (Techpratico callback).
--
-- O laudo PDF gerado pelo VALBOT é enviado de volta pra Techpratico via
-- POST https://convert.se.techpratico.net/conversao/retorno-analise
-- com header X-API-Key. Estas colunas registram o estado desse envio pra:
--   • bloquear duplicado (botão vira "Enviado ✓" após sucesso)
--   • auditar quando/quem enviou + resposta da Unidade Gestora
--   • permitir reenvio explícito (com confirmação no frontend)
--
-- Idempotente: ADD COLUMN IF NOT EXISTS. Sem NOT NULL (não trava rows
-- existentes — os 106 exames já processados ficam laudo_enviado_em=NULL).
-- =============================================================================

ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS laudo_enviado_em      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS laudo_envio_status    VARCHAR(20),   -- success | failed | sending
  ADD COLUMN IF NOT EXISTS laudo_envio_resultado VARCHAR(1),    -- A/R/N enviado
  ADD COLUMN IF NOT EXISTS laudo_envio_resposta  TEXT,          -- corpo da resposta HTTP (debug)
  ADD COLUMN IF NOT EXISTS laudo_envio_tentativas INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN exams.laudo_enviado_em IS
  'Timestamp do último envio BEM-SUCEDIDO do laudo pra Unidade Gestora (Techpratico). NULL = nunca enviado.';
COMMENT ON COLUMN exams.laudo_envio_status IS
  'Status do último envio: success | failed | sending. NULL = nunca tentado.';
COMMENT ON COLUMN exams.laudo_envio_resultado IS
  'Resultado A/R/N enviado no payload (derivado do veredito VALBOT no momento do envio).';

-- Recria a view pra expor os campos de envio no /api/videos e /api/exams.
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
  e.resultado_exame,
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
  -- NOVO 008: estado do envio do laudo pra Unidade Gestora
  e.laudo_enviado_em,
  e.laudo_envio_status,
  e.laudo_envio_resultado,
  e.laudo_envio_tentativas,
  cv.veredito           AS validator_veredito,
  cv.confianca          AS validator_confianca,
  cv.motivo             AS validator_motivo,
  cv.fabricante         AS validator_fabricante,
  e.created_at,
  e.updated_at,
  (SELECT COUNT(*) FROM exam_events ev WHERE ev.exam_id = e.id) AS event_count
FROM exams e
LEFT JOIN exam_camera_validations cv ON cv.exam_id = e.id;
