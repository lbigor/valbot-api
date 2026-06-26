-- 037 — Indicador FUNIL + métricas escopadas em categoria 'B' (v_exams_metrics).
--
-- REGRA DE NEGÓCIO (Igor): o Valbot HOJE analisa SOMENTE categoria 'B'. O
-- indicador deve ABRIR com um FUNIL de 3 métricas, nesta ordem:
--   1. recebidos_total            — COUNT de TODAS as categorias (A/B/C/D/E).
--   2. recebidos_catb             — COUNT só categoria 'B'.
--   3. com_resultado_oficial_catb — COUNT categoria 'B' COM oficial (A/R).
--
-- Os DEMAIS contadores (aprovados, inaptos, divergentes, em_comite, em_auditoria,
-- concluidos, recebidos, etc.) passam a filtrar categoria='B' — somar A/C/D/E é
-- bug (ex.: 13/06 mostrava 839 em vez de 465 cat B).
--
-- ESCOPO: só os AGREGADOS. A view BASE v_exams_overview e a leitura por hash
-- (detalhe/laudo de qualquer exame) NÃO são filtradas.
--
-- CONVERGÊNCIA NO BOOT: esta DDL é a MESMA de tooling/api_stub/db.py
-- (_SQL_V_EXAMS_METRICS, em _SCHEMA_OBJECTS). O CD de prod NÃO roda migrations —
-- ensure_schema_objects() recria a view a cada boot. Esta migration existe p/
-- ambientes que rodam migrate.sh e p/ rastreabilidade. Idempotente
-- (CREATE OR REPLACE VIEW). NÃO altera colunas da v_exams_overview.

BEGIN;

CREATE OR REPLACE VIEW v_exams_metrics AS
SELECT
  DATE_TRUNC('day', created_at)                       AS dia,
  -- ── FUNIL (topo do indicador) ────────────────────────────────────────────
  COUNT(*)                                            AS recebidos_total,
  COUNT(*) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B') AS recebidos_catb,
  COUNT(*) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B'
                     AND resultado_oficial IS NOT NULL)             AS com_resultado_oficial_catb,
  -- ── Demais métricas: SEMPRE escopadas em categoria='B' ────────────────────
  COUNT(*) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B') AS total_exames,
  COUNT(*) FILTER (WHERE resultado = 'APROVADO'      AND upper(btrim(coalesce(categoria,''))) = 'B') AS aprovados,
  COUNT(*) FILTER (WHERE resultado = 'INAPTO'        AND upper(btrim(coalesce(categoria,''))) = 'B') AS inaptos,
  COUNT(*) FILTER (WHERE resultado = 'SEM_AVALIACAO' AND upper(btrim(coalesce(categoria,''))) = 'B') AS sem_avaliacao,
  COUNT(*) FILTER (WHERE resultado = 'FALHOU'        AND upper(btrim(coalesce(categoria,''))) = 'B') AS falhos,
  COUNT(*) FILTER (WHERE resultado = 'PROCESSANDO'   AND upper(btrim(coalesce(categoria,''))) = 'B') AS processando,
  COUNT(*) FILTER (WHERE resultado = 'PENDENTE'      AND upper(btrim(coalesce(categoria,''))) = 'B') AS pendentes,
  SUM(cost_usd) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B')        AS custo_total_usd,
  AVG(gemini_elapsed_s) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B') AS gemini_avg_s,
  SUM(size_bytes) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B') / 1073741824.0 AS gb_processados,
  COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL AND upper(btrim(coalesce(categoria,''))) = 'B') AS com_resultado_oficial,
  COUNT(*) FILTER (WHERE oficial_pendente              AND upper(btrim(coalesce(categoria,''))) = 'B') AS aguardando_oficial,
  COUNT(*) FILTER (WHERE resultado_oficial = 'A'       AND upper(btrim(coalesce(categoria,''))) = 'B') AS oficial_aprovado,
  COUNT(*) FILTER (WHERE resultado_oficial = 'R'       AND upper(btrim(coalesce(categoria,''))) = 'B') AS oficial_reprovado,
  COUNT(*) FILTER (WHERE divergente                    AND upper(btrim(coalesce(categoria,''))) = 'B') AS divergentes,
  COUNT(*) FILTER (WHERE stage = 'comite'              AND upper(btrim(coalesce(categoria,''))) = 'B') AS em_comite,
  COUNT(*) FILTER (WHERE stage = 'auditoria'           AND upper(btrim(coalesce(categoria,''))) = 'B') AS em_auditoria,
  COUNT(*) FILTER (WHERE stage = 'concluido'           AND upper(btrim(coalesce(categoria,''))) = 'B') AS concluidos,
  COUNT(*) FILTER (WHERE stage = 'aguardando' AND oficial_pendente AND upper(btrim(coalesce(categoria,''))) = 'B') AS recebidos,
  COUNT(*) FILTER (WHERE stage = 'aguardando_oficial'  AND upper(btrim(coalesce(categoria,''))) = 'B') AS aguardando_oficial_ciclo,
  COUNT(*) FILTER (WHERE tem_anotacoes                 AND upper(btrim(coalesce(categoria,''))) = 'B') AS com_anotacoes,
  COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL AND tem_anotacoes AND upper(btrim(coalesce(categoria,''))) = 'B') AS completos
FROM v_exams_overview
GROUP BY DATE_TRUNC('day', created_at);

COMMIT;
