-- =============================================================================
-- 021 — Agendamento de processamento em lote (tela "Cron / Batch").
--
-- `cron_jobs` define UM agendamento de processamento de exames pendentes:
-- quando rodar (`schedule_kind` + `horario`/`cron_expr`), quantos exames por
-- disparo (`batch_limit`), quantas retentativas (`retry`) e o escopo de exames
-- (`escopo` -> pending|queued|failed|all). `enabled` liga/desliga sem apagar.
--
-- `cron_job_runs` e a trilha de cada disparo (manual via /trigger ou agendado
-- pelo APScheduler): quando comecou/terminou, quantos processados/falharam,
-- custo agregado e status final.
--
-- Idempotente: CREATE TABLE IF NOT EXISTS.
-- =============================================================================

CREATE TABLE IF NOT EXISTS cron_jobs (
  id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  nome          VARCHAR(120) NOT NULL,
  enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
  schedule_kind VARCHAR(20)  NOT NULL DEFAULT 'daily',  -- daily | hourly | cron | interval
  horario       VARCHAR(20),                            -- 'HH:MM' p/ schedule_kind=daily
  cron_expr     VARCHAR(120),                           -- expressao cron p/ schedule_kind=cron
  batch_limit   INTEGER      NOT NULL DEFAULT 50,        -- max de exames por disparo
  retry         INTEGER      NOT NULL DEFAULT 0,         -- retentativas por exame
  escopo        VARCHAR(40)  NOT NULL DEFAULT 'pending', -- pending | queued | failed | all
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cron_jobs_enabled ON cron_jobs (enabled) WHERE enabled IS TRUE;

CREATE TABLE IF NOT EXISTS cron_job_runs (
  id             BIGSERIAL    PRIMARY KEY,
  cron_job_id    UUID         REFERENCES cron_jobs(id) ON DELETE CASCADE,
  iniciado_em    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  finalizado_em  TIMESTAMPTZ,
  n_processados  INTEGER      NOT NULL DEFAULT 0,
  n_falhas       INTEGER      NOT NULL DEFAULT 0,
  custo_usd      NUMERIC      NOT NULL DEFAULT 0,
  status         VARCHAR(20)  NOT NULL DEFAULT 'running',  -- running | success | failed
  created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cron_job_runs_job
  ON cron_job_runs (cron_job_id, iniciado_em DESC);

COMMENT ON TABLE cron_jobs IS
  'Agendamentos de processamento em lote de exames pendentes (tela Cron/Batch).';
COMMENT ON TABLE cron_job_runs IS
  'Historico de execucoes de um cron_job (manual ou agendada).';
