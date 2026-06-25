-- 033 — Cadeia do Resultado: 5 níveis A/R + fix de stage da divergência.
--
-- Regra de negócio (Igor, dura): a "Cadeia do Resultado" tem 5 NÍVEIS e CADA UM
-- produz SOMENTE Aprovado (A) ou Reprovado (R). Não existe outro veredito. Os
-- rótulos de relação ("concorda c/ examinador", "mantém divergência") NÃO são
-- campos próprios — são DERIVADOS da comparação dos A/R entre níveis.
--
-- Esta migration RECRIA v_exams_overview garantindo a CASE de stage CORRETA na
-- divergência (③ Comitê = 2ª opinião; ④ Auditor = decisor):
--   • Divergente AND NOT comite_concluido ⇒ 'comite'    (aguarda o Comitê;
--                                                         NÃO vai ao auditor).
--   • Divergente AND comite_concluido     ⇒ 'auditoria' (vai ao Auditor, decisor,
--                                                         INDEPENDENTE do parecer
--                                                         do comitê).
--   • Consenso (não divergente)           ⇒ 'concluido'.
--
-- A migration 032 já trazia essa CASE corretamente; esta 033 a fixa como contrato
-- de registro (idempotente, DROP ... IF EXISTS) e fica como o ponto canônico do
-- comportamento de stage para a frente dos 5 níveis A/R. TODO o restante é
-- PRESERVADO sem regressão: o core canônico (027), os sinalizadores (028), o
-- contador de ciclos do oficial (031: aguardando=buscas=0 / aguardando_oficial>=1),
-- processando, falhou, fora_escopo, concluido, e a v_exams_metrics (recriada pelo
-- CASCADE).
--
-- Definições (mantidas, vindas do core canônico 027):
--   • divergente       = oficial (resultado_exame A/R) difere da IA (aprovado).
--   • comite_concluido = existe exam_comite_laudos para o exame.
--
-- Atômica + idempotente (DROP VIEW IF EXISTS).

BEGIN;

DROP VIEW IF EXISTS v_exams_overview CASCADE;

CREATE VIEW v_exams_overview AS
SELECT
  base.*,
  CASE
    WHEN base.gate_rejected                                                   THEN 'fora_escopo'
    WHEN lower(coalesce(base.status, '')) IN ('failed','error','erro')        THEN 'falhou'
    -- ── Sem oficial definitivo: RECEBIDO vs AGUARDANDO OFICIAL pelo nº de ciclos ──
    -- (mantido da 031 — NÃO regredir.)
    WHEN base.oficial_pendente AND coalesce(base.buscas_oficial, 0) = 0       THEN 'aguardando'
    WHEN base.oficial_pendente                                               THEN 'aguardando_oficial'
    WHEN lower(coalesce(base.status, '')) IN ('queued','pending','novo','uploaded','recebido') THEN 'aguardando'
    WHEN lower(coalesce(base.status, '')) IN ('running','processing','analisando')             THEN 'processando'
    -- ── Comitê = SEGUNDA OPINIÃO; Auditor = decisor (032/033) ──────────────────
    -- Divergência SEM comitê → fica no comitê (2ª opinião pendente); NÃO vai ao
    -- auditor. Divergência COM comitê → vai ao Auditor (decisor), INDEPENDENTE do
    -- parecer do comitê. Consenso (não divergente) não passa por comitê/auditor.
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

    -- ── CORE CANÔNICO: resultado oficial e derivados (mantido da 027) ──────
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

    -- ── CONTADOR DE CICLOS DE BUSCA DO OFICIAL (031) ──────────────────────
    -- 0 = RECEBIDO (nunca buscado); >=1 = AGUARDANDO RESULTADO OFICIAL.
    coalesce(e.buscas_oficial, 0)                              AS buscas_oficial,
    e.ultima_busca_oficial                                     AS ultima_busca_oficial,

    -- ── SINALIZADORES OFICIAIS (028) ──────────────────────────────────────
    -- Qualidade de câmera/vídeo: veredito do validador, senão confiança ≥ 0.7
    -- (espelha o antigo _derive_video_ok do /api/os). NULL = sem dado.
    CASE
      WHEN upper(btrim(coalesce(cv.veredito, ''))) = 'HOMO'     THEN true
      WHEN upper(btrim(coalesce(cv.veredito, ''))) = 'NAO_HOMO' THEN false
      WHEN coalesce(e.layout_confianca, cv.confianca) IS NOT NULL
           THEN (coalesce(e.layout_confianca, cv.confianca) >= 0.7)
      ELSE NULL
    END                                                        AS video_ok,
    -- Já tem anotações (training_annotations não vazio).
    (jsonb_array_length(coalesce(e.training_annotations, '[]'::jsonb)) > 0) AS tem_anotacoes
  FROM exams e
  LEFT JOIN exam_camera_validations cv ON cv.exam_id = e.id
) base;

COMMENT ON VIEW v_exams_overview IS
  'Fonte única do exame. Core canônico (resultado_oficial/oficial_pendente/'
  'resultado_calculado/divergente/comite_concluido/conduta_inadequada/buscas_oficial/'
  'stage) + sinalizadores oficiais (video_ok, tem_anotacoes). Stage: divergência '
  'SEM comitê = ''comite'' (2ª opinião pendente, NÃO vai ao auditor); divergência '
  'COM comitê = ''auditoria'' (vai ao Auditor, decisor, INDEPENDENTE do parecer do '
  'comitê); consenso = ''concluido''. Distingue RECEBIDO (buscas_oficial=0) de '
  'AGUARDANDO OFICIAL (>=1). Todas as telas leem daqui.';

-- ── Indicadores: variação do mesmo core (recriada pelo CASCADE acima) ───────
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
  COUNT(*) FILTER (WHERE stage = 'concluido')           AS concluidos,
  -- ── buckets do Kanban: recebido (nunca buscado) × aguardando oficial (>=1) ──
  COUNT(*) FILTER (WHERE stage = 'aguardando' AND oficial_pendente)  AS recebidos,
  COUNT(*) FILTER (WHERE stage = 'aguardando_oficial')               AS aguardando_oficial_ciclo,
  -- ── indicador de anotações (028) ──
  COUNT(*) FILTER (WHERE tem_anotacoes)                                       AS com_anotacoes,
  COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL AND tem_anotacoes)     AS completos
FROM v_exams_overview
GROUP BY DATE_TRUNC('day', created_at);

COMMENT ON VIEW v_exams_metrics IS
  'Agregado diário (Indicadores). Variação da v_exams_overview — mesmo core. '
  'Recebidos × aguardando oficial × resultado oficial (A/R) × anotações.';

COMMIT;
