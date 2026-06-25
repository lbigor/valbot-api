-- 035 — Stage 'concluido' refletido pela DECISÃO DO SUPERVISOR (encerramento da OS).
--
-- BUG (lente A): a decisão do supervisor (save_supervisor_decisao) setava
-- ordens_servico.status='decisao_final' + encerrada_em, mas a v_exams_overview NÃO
-- consultava ordens_servico — derivava `stage` só de exams + comitê. Resultado: ao
-- "Homologar e encerrar", o exame continuava em 'auditoria' (nunca migrava pra
-- 'concluido') e não saía da fila do supervisor, mesmo com a decisão persistida.
--
-- FIX: a view passa a fazer LEFT JOIN ordens_servico (1:1 — UNIQUE(exam_id)) e
-- expoe os_status/os_encerrada_em. A CASE de `stage` ganha, com PRIORIDADE sobre
-- comite/auditoria, a regra:
--   - OS encerrada (encerrada_em IS NOT NULL) => 'concluido' (a cadeia terminou,
--     INDEPENDENTE de divergencia — o supervisor e o nivel final).
-- O restante da CASE e PRESERVADO sem regressao (gate/falhou/oficial pelo LOG 034/
-- comite/auditoria/concluido). v_exams_metrics recriada via CASCADE (mesmo core).
--
-- Materializa tambem (idempotente) as OS faltantes dos exames ja em 'auditoria'
-- (divergencia pos-comite) que nunca tiveram ordens_servico — o caminho do
-- supervisor agora resolve hash->os_id via GET-OR-CREATE, mas o backfill garante a
-- camada ja populada (espelha o shape de db.os_id_por_hash).
--
-- ATENCAO: a FONTE DA VERDADE da view em prod e db.py (_SQL_V_EXAMS_OVERVIEW,
-- recriada no startup do app a cada boot). Esta migration mantem o registro
-- versionado/initdb em sincronia. Atomica + idempotente (DROP VIEW IF EXISTS /
-- ON CONFLICT DO NOTHING).

BEGIN;

-- (1) Backfill: materializa a OS dos exames em 'auditoria' sem ordens_servico.
-- 'auditoria' = divergente (oficial A/R difere da IA) E comite concluido. Idempotente.
INSERT INTO ordens_servico (exam_id, tipo_divergencia, status, numero_os)
SELECT e.id, 'resultado', 'aguardando_supervisor',
       'OS-' || upper(substr(e.hash, 1, 8))
  FROM exams e
 WHERE ((upper(btrim(coalesce(e.resultado_exame, ''))) = 'A' AND e.aprovado IS FALSE)
     OR (upper(btrim(coalesce(e.resultado_exame, ''))) = 'R' AND e.aprovado IS TRUE))
   AND EXISTS (SELECT 1 FROM exam_comite_laudos l WHERE l.exam_id = e.id)
ON CONFLICT (exam_id) DO NOTHING;

-- (2) Recria v_exams_overview com o desfecho do supervisor refletido no stage.
DROP VIEW IF EXISTS v_exams_overview CASCADE;

CREATE VIEW v_exams_overview AS
SELECT
  base.*,
  CASE
    WHEN base.gate_rejected                                                   THEN 'fora_escopo'
    WHEN lower(coalesce(base.status, '')) IN ('failed','error','erro')        THEN 'falhou'
    WHEN base.oficial_pendente AND base.tem_busca_oficial                     THEN 'aguardando_oficial'
    WHEN base.oficial_pendente                                               THEN 'aguardando'
    WHEN lower(coalesce(base.status, '')) IN ('queued','pending','novo','uploaded','recebido') THEN 'aguardando'
    WHEN lower(coalesce(base.status, '')) IN ('running','processing','analisando')             THEN 'processando'
    -- Desfecho do Supervisor: OS encerrada (decisao final) => CONCLUIDO.
    -- Tem precedencia sobre comite/auditoria: a cadeia (5 niveis) ja terminou.
    WHEN base.os_encerrada_em IS NOT NULL                                     THEN 'concluido'
    WHEN base.divergente AND NOT base.comite_concluido                       THEN 'comite'
    WHEN base.divergente AND base.comite_concluido                           THEN 'auditoria'
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

    CASE WHEN upper(btrim(coalesce(e.resultado_exame, ''))) IN ('A','R')
         THEN upper(btrim(e.resultado_exame))
         ELSE NULL END                                          AS resultado_oficial,
    (upper(btrim(coalesce(e.resultado_exame, ''))) NOT IN ('A','R')) AS oficial_pendente,
    CASE WHEN e.aprovado IS TRUE  THEN 'A'
         WHEN e.aprovado IS FALSE THEN 'R'
         ELSE NULL END                                          AS resultado_calculado,
    ((upper(btrim(coalesce(e.resultado_exame, ''))) = 'A' AND e.aprovado IS FALSE)
     OR (upper(btrim(coalesce(e.resultado_exame, ''))) = 'R' AND e.aprovado IS TRUE)) AS divergente,
    EXISTS (SELECT 1 FROM exam_comite_laudos l WHERE l.exam_id = e.id) AS comite_concluido,
    EXISTS (SELECT 1 FROM exam_comentarios_compliance cc
            WHERE cc.exam_id = e.id AND cc.tipo = 'examinador_inadequado') AS conduta_inadequada,

    EXISTS (SELECT 1 FROM exam_busca_oficial_log l WHERE l.exam_id = e.id) AS tem_busca_oficial,

    coalesce(e.buscas_oficial, 0)                              AS buscas_oficial,
    e.ultima_busca_oficial                                     AS ultima_busca_oficial,

    CASE
      WHEN upper(btrim(coalesce(cv.veredito, ''))) = 'HOMO'     THEN true
      WHEN upper(btrim(coalesce(cv.veredito, ''))) = 'NAO_HOMO' THEN false
      WHEN coalesce(e.layout_confianca, cv.confianca) IS NOT NULL
           THEN (coalesce(e.layout_confianca, cv.confianca) >= 0.7)
      ELSE NULL
    END                                                        AS video_ok,
    (jsonb_array_length(coalesce(e.training_annotations, '[]'::jsonb)) > 0) AS tem_anotacoes,

    -- Desfecho da OS (decisao do supervisor) — fonte do stage 'concluido'.
    -- 1 OS por exame (UNIQUE exam_id), entao o LEFT JOIN e 1:1. encerrada_em e
    -- setado por save_supervisor_decisao ao homologar/reformar a decisao final.
    os_ord.status        AS os_status,
    os_ord.encerrada_em  AS os_encerrada_em
  FROM exams e
  LEFT JOIN exam_camera_validations cv ON cv.exam_id = e.id
  LEFT JOIN ordens_servico os_ord ON os_ord.exam_id = e.id
) base;

COMMENT ON VIEW v_exams_overview IS
  'Fonte unica do exame. Core canonico + sinalizadores + desfecho da OS '
  '(os_status/os_encerrada_em). Stage: OS encerrada (decisao do supervisor) = '
  'concluido (precede comite/auditoria); oficial pendente pelo LOG (034); '
  'divergencia SEM comite = comite, COM comite = auditoria; consenso = concluido. '
  'Todas as telas leem daqui.';

-- (3) Indicadores: variacao do mesmo core (recriada pelo CASCADE acima).
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
  COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL) AS com_resultado_oficial,
  COUNT(*) FILTER (WHERE oficial_pendente)              AS aguardando_oficial,
  COUNT(*) FILTER (WHERE resultado_oficial = 'A')       AS oficial_aprovado,
  COUNT(*) FILTER (WHERE resultado_oficial = 'R')       AS oficial_reprovado,
  COUNT(*) FILTER (WHERE divergente)                    AS divergentes,
  COUNT(*) FILTER (WHERE stage = 'comite')              AS em_comite,
  COUNT(*) FILTER (WHERE stage = 'auditoria')           AS em_auditoria,
  COUNT(*) FILTER (WHERE stage = 'concluido')           AS concluidos,
  COUNT(*) FILTER (WHERE stage = 'aguardando' AND oficial_pendente)  AS recebidos,
  COUNT(*) FILTER (WHERE stage = 'aguardando_oficial')               AS aguardando_oficial_ciclo,
  COUNT(*) FILTER (WHERE tem_anotacoes)                                       AS com_anotacoes,
  COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL AND tem_anotacoes)     AS completos
FROM v_exams_overview
GROUP BY DATE_TRUNC('day', created_at);

COMMENT ON VIEW v_exams_metrics IS
  'Agregado diario (Indicadores). Variacao da v_exams_overview — mesmo core. '
  'Recebidos x aguardando oficial x resultado oficial (A/R) x anotacoes x concluidos.';

COMMIT;
