-- =============================================================================
-- 037 — Teto de retentativas por exame (processamento overnight cat B).
--
-- `exams.retry_count_non_quota` conta APENAS as falhas REAIS (NÃO-quota) da
-- análise automática (ex.: 400 INVALID_ARGUMENT, vídeo corrompido). Falhas de
-- QUOTA (429 / RESOURCE_EXHAUSTED) NÃO contam — elas re-enfileiram com backoff
-- e devem ser retentadas indefinidamente quando a quota voltar. Ao atingir 5
-- tentativas reais, o exame vira FALHA TERMINAL (status='failed', mantém error)
-- e para de ser re-enfileirado pelo worker / pelo job da madrugada.
--
-- Também converge defensivamente `cron_jobs.categoria` (lida/gravada pelo código
-- desde o filtro de categoria do batch, mas sem migration própria) — necessária
-- para o seed do cron 'processar_catb_madrugada' (categoria='B').
--
-- Idempotente: ADD COLUMN IF NOT EXISTS. Espelhada em db._SCHEMA_COLUMNS (o CD
-- de prod NÃO roda migrate.sh — quem converge o schema no boot é
-- ensure_schema_objects()).
-- =============================================================================

ALTER TABLE exams ADD COLUMN IF NOT EXISTS retry_count_non_quota INTEGER DEFAULT 0;

ALTER TABLE cron_jobs ADD COLUMN IF NOT EXISTS categoria VARCHAR(5);
