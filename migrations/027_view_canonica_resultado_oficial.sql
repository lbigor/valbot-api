-- 027 — View canônica do resultado oficial.
--
-- Centraliza, UMA ÚNICA VEZ, a derivação do "resultado oficial" e do estágio do
-- lifecycle na v_exams_overview, para que TODAS as telas/endpoints leiam os
-- mesmos campos e nunca mais divirjam (Kanban, listas, detalhes, indicadores).
--
-- Regra do oficial (decisão de produto): o resultado oficial (TechPrático) só é
-- DEFINITIVO quando 'A' (aprovado) ou 'R' (reprovado). "N" (Não Avaliado / ainda
-- não saiu — pode levar horas), vazio e '—' ⇒ oficial PENDENTE; o card não avança.
--
-- Idempotente: DROP ... CASCADE + recriação. Só ADICIONA colunas (retrocompatível).
-- Atômica: tudo numa transação — nunca há janela com a view inexistente.

BEGIN;

DROP VIEW IF EXISTS v_exams_overview CASCADE;

CREATE VIEW v_exams_overview AS
SELECT
  base.*,
  -- Estágio canônico do lifecycle (espelha o antigo stageOf do frontend + o gate
  -- de resultado oficial). Fonte única — o frontend só agrupa por este campo.
  CASE
    WHEN base.gate_rejected                                                   THEN 'fora_escopo'
    WHEN lower(coalesce(base.status, '')) IN ('failed','error','erro')        THEN 'falhou'
    WHEN lower(coalesce(base.status, '')) IN ('queued','pending','novo','uploaded','recebido') THEN 'aguardando'
    WHEN lower(coalesce(base.status, '')) IN ('running','processing','analisando')             THEN 'processando'
    -- processado em diante: sem oficial definitivo ⇒ travado em "aguardando oficial".
    WHEN base.oficial_pendente                                               THEN 'aguardando_oficial'
    WHEN base.comite_concluido                                               THEN 'comite'
    WHEN base.divergente                                                     THEN 'auditoria'
    ELSE 'concluido'
  END AS stage
FROM (
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
    (SELECT COUNT(*) FROM exam_events ev WHERE ev.exam_id = e.id) AS event_count,

    -- ── CORE CANÔNICO: resultado oficial e derivados ──────────────────────
    -- Oficial só vale se 'A'/'R'. Senão NULL (pendente).
    CASE WHEN upper(btrim(coalesce(e.resultado_exame, ''))) IN ('A','R')
         THEN upper(btrim(e.resultado_exame))
         ELSE NULL END                                          AS resultado_oficial,
    -- Pendente = não há oficial definitivo ('N', vazio, '—', etc.).
    (upper(btrim(coalesce(e.resultado_exame, ''))) NOT IN ('A','R')) AS oficial_pendente,
    -- Resultado calculado pela IA a partir do veredito booleano.
    CASE WHEN e.aprovado IS TRUE  THEN 'A'
         WHEN e.aprovado IS FALSE THEN 'R'
         ELSE NULL END                                          AS resultado_calculado,
    -- Divergência só existe COM oficial definitivo (oficial A vs IA R, ou vice-versa).
    ((upper(btrim(coalesce(e.resultado_exame, ''))) = 'A' AND e.aprovado IS FALSE)
     OR (upper(btrim(coalesce(e.resultado_exame, ''))) = 'R' AND e.aprovado IS TRUE)) AS divergente,
    -- Comitê concluído: existe laudo de comitê pro exame.
    EXISTS (SELECT 1 FROM exam_comite_laudos l WHERE l.exam_id = e.id) AS comite_concluido,
    -- Conduta inadequada do examinador (compliance §6/§10).
    EXISTS (SELECT 1 FROM exam_comentarios_compliance cc
            WHERE cc.exam_id = e.id AND cc.tipo = 'examinador_inadequado') AS conduta_inadequada
  FROM exams e
  LEFT JOIN exam_camera_validations cv ON cv.exam_id = e.id
) base;

COMMENT ON VIEW v_exams_overview IS
  'Fonte única do exame. Core canônico: resultado_oficial ({A,R} ou NULL=pendente), '
  'oficial_pendente, resultado_calculado, divergente, comite_concluido, '
  'conduta_inadequada e stage do lifecycle. Todas as telas/endpoints leem daqui.';

-- ── Indicadores: VARIAÇÃO do mesmo core ────────────────────────────────────
-- v_exams_metrics agrega A PARTIR da v_exams_overview, usando os mesmos campos
-- canônicos — garante que os indicadores usem o resultado oficial idêntico ao
-- das demais telas. Mantém as colunas antigas (compat) e adiciona as canônicas.
CREATE OR REPLACE VIEW v_exams_metrics AS
SELECT
  DATE_TRUNC('day', created_at)                       AS dia,
  COUNT(*)                                            AS total_exames,
  COUNT(*) FILTER (WHERE resultado = 'APROVADO')      AS aprovados,
  COUNT(*) FILTER (WHERE resultado = 'INAPTO')        AS inaptos,
  COUNT(*) FILTER (WHERE resultado = 'SEM_AVALIACAO') AS sem_avaliacao,
  COUNT(*) FILTER (WHERE resultado = 'FALHOU')        AS falhos,
  COUNT(*) FILTER (WHERE resultado = 'PROCESSANDO')   AS processando,
  COUNT(*) FILTER (WHERE resultado = 'PENDENTE')      AS pendentes,
  SUM(cost_usd)                                       AS custo_total_usd,
  AVG(gemini_elapsed_s)                               AS gemini_avg_s,
  SUM(size_bytes) / 1073741824.0                      AS gb_processados,
  -- ── canônicas (mesmo core da v_exams_overview) ──
  COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL) AS com_resultado_oficial,
  COUNT(*) FILTER (WHERE oficial_pendente)              AS aguardando_oficial,
  COUNT(*) FILTER (WHERE resultado_oficial = 'A')       AS oficial_aprovado,
  COUNT(*) FILTER (WHERE resultado_oficial = 'R')       AS oficial_reprovado,
  COUNT(*) FILTER (WHERE divergente)                    AS divergentes,
  COUNT(*) FILTER (WHERE stage = 'comite')              AS em_comite,
  COUNT(*) FILTER (WHERE stage = 'auditoria')           AS em_auditoria,
  COUNT(*) FILTER (WHERE stage = 'concluido')           AS concluidos
FROM v_exams_overview
GROUP BY DATE_TRUNC('day', created_at);

COMMENT ON VIEW v_exams_metrics IS
  'Agregado diário (Indicadores). Variação da v_exams_overview — mesmo core '
  'canônico de resultado oficial. Colunas antigas mantidas p/ compat.';

COMMIT;
