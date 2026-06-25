-- 029 — Status canônico "recebido" (aguardando resultado oficial do examinador).
--
-- Regra de negócio (Igor, dura): um exame que ainda NÃO tem resultado oficial do
-- TechPrático (exams.resultado_exame ∉ {'A','R'}) deve ficar no status 'recebido'
-- (aguardando oficial) — NUNCA em queued/running/failed/processed. Só quando o
-- oficial chega (resultado_exame vira 'A' ou 'R') o exame é promovido
-- recebido→queued e entra na fila de análise da IA (② Auditor Val).
--
-- exams.status é TEXT/VARCHAR livre (sem CHECK) — 'recebido' é um VALOR novo, não
-- exige alteração de schema. A v_exams_overview (migration 027) e o Kanban JÁ
-- tratam 'recebido' como bucket "Recebido"/"aguardando". O worker
-- (_claim_next_queued) só reivindica status='queued', portanto NUNCA pega um
-- exame 'recebido'.
--
-- Esta migration é puramente DOCUMENTAL (COMMENT) — idempotente e sem efeito de
-- dados. O realinhamento dos exames legados (sem oficial) para 'recebido' NÃO é
-- executado aqui de propósito: é decisão operacional do Igor (ver bloco
-- comentado abaixo + descrição no PR). NÃO descomente sem autorização.

BEGIN;

COMMENT ON COLUMN exams.status IS
  'Lifecycle do exame. Valores: uploading | recebido | queued | running | '
  'processed | processed_no_pdf | failed. "recebido" = aguardando resultado '
  'oficial do examinador (resultado_exame ∉ {A,R}); o worker só pega "queued". '
  'Promoção recebido→queued ocorre quando o oficial A/R chega (buscar-resultado).';

COMMIT;

-- ----------------------------------------------------------------------------
-- REALINHAMENTO DE LEGADO — NÃO EXECUTAR automaticamente (decisão do Igor).
-- Move os exames CAT B atuais que estão SEM oficial definitivo e que NÃO estão
-- de fato sendo processados agora (queued/failed/processed/processed_no_pdf)
-- para 'recebido'. NÃO toca em 'running' (pode estar em análise neste instante)
-- nem em 'uploading' (download em andamento). NÃO altera nenhuma análise já
-- feita — só o status/fluxo. Rodar manualmente quando o Igor autorizar:
--
--   UPDATE exams
--      SET status = 'recebido', updated_at = NOW()
--    WHERE categoria = 'B'
--      AND gs_video LIKE 'gs://%'
--      AND status IN ('queued','failed','processed','processed_no_pdf')
--      AND (resultado_exame IS NULL
--           OR upper(btrim(resultado_exame)) NOT IN ('A','R'));
--
-- Conferir antes o universo afetado (esperado ~499 exames):
--
--   SELECT status, count(*)
--     FROM exams
--    WHERE categoria = 'B' AND gs_video LIKE 'gs://%'
--      AND status IN ('queued','failed','processed','processed_no_pdf')
--      AND (resultado_exame IS NULL
--           OR upper(btrim(resultado_exame)) NOT IN ('A','R'))
--    GROUP BY status;
-- ----------------------------------------------------------------------------
