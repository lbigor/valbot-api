-- 034 — LOG append-only das tentativas de busca do resultado oficial (TechPrático).
--
-- Regra de negócio (Igor, dura): CADA vez que o sistema busca o resultado oficial
-- de um exame (single, lote ou agendado), isso é UMA tentativa e gera UM registro
-- nesta tabela. A tabela é APPEND-ONLY — nunca se faz UPDATE/DELETE; o histórico
-- de tentativas é a fonte da verdade da classificação do Kanban:
--
--   • RECEBIDO                    = exame SEM oficial definitivo (resultado_exame
--                                   ∉ {A,R}) e SEM nenhuma tentativa (0 registros
--                                   no log).
--   • AGUARDANDO RESULTADO OFICIAL = exame SEM oficial definitivo e COM >=1
--                                   tentativa (EXISTS registro no log).
--
-- Invariante: um vídeo que JÁ teve o resultado buscado NUNCA volta para Recebido.
--
-- POR QUE O LOG (e não o contador exams.buscas_oficial)?
-- O contador `buscas_oficial` (migration 031) é frágil: ele só é incrementado
-- DENTRO do UPDATE de sucesso de _buscar_resultado_techpratico — uma busca que
-- falha no HTTP (erro_http/erro) retorna ANTES do incremento, então a tentativa
-- real não conta. Além disso a re-ingestão (insert_exam ON CONFLICT) reescreve
-- status='recebido', e a CASE da view tratava `oficial_pendente AND buscas=0`
-- antes do log, derrubando exames já buscados de volta para "Recebido". O LOG
-- resolve: registra TODA tentativa (sucesso OU falha), e a view passa a
-- classificar por EXISTS no log — não por contador nem por status.
--
-- Esta migration:
--   (1) CRIA a tabela append-only exam_busca_oficial_log + índice por exam_id.
--   (2) BACKFILL conservador: para exames com buscas_oficial>=1 e ainda sem
--       linha no log, semeia UMA linha (origem='backfill') para não perder o
--       histórico do contador que já existia — assim os 206 exames já buscados
--       saem de "Recebido" imediatamente, sem esperar o próximo ciclo.
--   (3) RECRIA v_exams_overview (DROP+CREATE, NÃO CREATE OR REPLACE — foi por
--       isso que a 033 "não pegou" a regra desejada) com a CASE de stage
--       classificando o oficial pendente pelo LOG (EXISTS), com PRIORIDADE sobre
--       o status do exame. PRESERVA o resto da CASE correta (gate/falhou/
--       processando/comite/auditoria/concluido) e TODAS as colunas (incl.
--       buscas_oficial, mantido por compatibilidade).
--   (4) RECRIA v_exams_metrics via CASCADE.
--
-- Atômica + idempotente (DROP VIEW IF EXISTS / CREATE TABLE IF NOT EXISTS).

BEGIN;

-- ── (1) Tabela append-only das tentativas ──────────────────────────────────
CREATE TABLE IF NOT EXISTS exam_busca_oficial_log (
    id                  BIGSERIAL    PRIMARY KEY,
    exam_id             UUID         NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    tentativa_em        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    origem              TEXT         NOT NULL DEFAULT 'manual',   -- manual | agendado | lote | backfill
    resultado_recebido  TEXT,        -- A/R/N/vazio que o TechPrático devolveu (NULL se erro)
    detalhe             TEXT         -- status/erro/observação da tentativa
);

CREATE INDEX IF NOT EXISTS idx_busca_oficial_log_exam
    ON exam_busca_oficial_log (exam_id);

COMMENT ON TABLE exam_busca_oficial_log IS
  'Log APPEND-ONLY das tentativas de busca do resultado oficial (TechPrático). '
  'Cada chamada (single/lote/agendado) grava 1 linha, com sucesso OU falha. '
  'Nunca UPDATE/DELETE. Fonte da classificação RECEBIDO (0 linhas) vs AGUARDANDO '
  'RESULTADO OFICIAL (>=1 linha) na v_exams_overview.';

-- ── (2) Backfill conservador do contador existente ─────────────────────────
-- Exames que já tinham buscas_oficial>=1 mas ainda sem linha no log recebem UMA
-- linha-semente (origem='backfill') para preservar o histórico do contador.
INSERT INTO exam_busca_oficial_log (exam_id, tentativa_em, origem, resultado_recebido, detalhe)
SELECT e.id,
       COALESCE(e.ultima_busca_oficial, e.updated_at, NOW()),
       'backfill',
       e.resultado_exame,
       'backfill da migration 034 — preserva histórico do contador buscas_oficial'
  FROM exams e
 WHERE COALESCE(e.buscas_oficial, 0) >= 1
   AND NOT EXISTS (
       SELECT 1 FROM exam_busca_oficial_log l WHERE l.exam_id = e.id
   );

-- ── (3) Recria v_exams_overview com classificação por LOG ──────────────────
DROP VIEW IF EXISTS v_exams_overview CASCADE;

CREATE VIEW v_exams_overview AS
SELECT
  base.*,
  CASE
    WHEN base.gate_rejected                                                   THEN 'fora_escopo'
    WHEN lower(coalesce(base.status, '')) IN ('failed','error','erro')        THEN 'falhou'
    -- ── Sem oficial definitivo: RECEBIDO vs AGUARDANDO OFICIAL pelo LOG ──────
    -- PRIORIDADE sobre o status: um exame sem oficial é classificado pelo
    -- histórico de tentativas (EXISTS no log), NUNCA pelo status='recebido' nem
    -- pelo contador buscas_oficial. >=1 tentativa ⇒ 'aguardando_oficial';
    -- 0 tentativas ⇒ 'aguardando' (Recebido). Um exame já buscado NUNCA volta
    -- a Recebido.
    WHEN base.oficial_pendente AND base.tem_busca_oficial                     THEN 'aguardando_oficial'
    WHEN base.oficial_pendente                                               THEN 'aguardando'
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

    -- ── FONTE DA CLASSIFICAÇÃO DO OFICIAL: o LOG append-only (034) ────────
    -- tem_busca_oficial = JÁ houve >=1 tentativa de busca registrada no log.
    -- É o que distingue RECEBIDO (false) de AGUARDANDO OFICIAL (true).
    EXISTS (SELECT 1 FROM exam_busca_oficial_log l WHERE l.exam_id = e.id) AS tem_busca_oficial,

    -- ── CONTADOR DE CICLOS DE BUSCA DO OFICIAL (031 — compatibilidade) ────
    -- Mantido na view por compatibilidade; a classificação NÃO depende mais
    -- dele (passou a usar tem_busca_oficial). 0 = nunca buscado; >=1 = buscado.
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
  'tem_busca_oficial/stage) + sinalizadores oficiais (video_ok, tem_anotacoes). '
  'Stage do oficial pendente classifica pelo LOG append-only (034): EXISTS '
  'tentativa = ''aguardando_oficial'' (Aguardando Resultado Oficial), senão '
  '''aguardando'' (Recebido) — com PRIORIDADE sobre o status. Um exame já '
  'buscado NUNCA volta a Recebido. Stage da divergência: SEM comitê = ''comite'' '
  '(2ª opinião pendente, NÃO vai ao auditor); COM comitê = ''auditoria'' (Auditor, '
  'decisor, INDEPENDENTE do parecer do comitê); consenso = ''concluido''. Todas '
  'as telas leem daqui.';

-- ── (4) Indicadores: variação do mesmo core (recriada pelo CASCADE acima) ───
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
