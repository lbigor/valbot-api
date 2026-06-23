-- 014_os_no_upload_sla.sql
-- Redefine a OS conforme a regra de negócio: CADA VÍDEO É UMA OS, aberta já no
-- init_upload. O número da OS é o ID gerado no init_upload e o relógio do SLA
-- começa a contar nesse instante (não quando surge a divergência).

-- Número de negócio da OS = ID do init_upload (analysis_id/hash ou external_id).
ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS numero_os VARCHAR(80);
-- Início do SLA = momento do init_upload (default = criada_em).
ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS sla_inicio TIMESTAMPTZ;
ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS sla_prazo_auditor_h    INTEGER DEFAULT 24;
ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS sla_prazo_supervisor_h INTEGER DEFAULT 48;

-- numero_os é o identificador de negócio mostrado ao operador (UNIQUE).
CREATE UNIQUE INDEX IF NOT EXISTS uq_os_numero ON ordens_servico (numero_os) WHERE numero_os IS NOT NULL;

-- Backfill para OS já existentes (criadas antes desta migration): usa o exam_id
-- como número e o criada_em como início do SLA.
UPDATE ordens_servico
   SET numero_os  = COALESCE(numero_os, exam_id::text),
       sla_inicio = COALESCE(sla_inicio, criada_em)
 WHERE numero_os IS NULL OR sla_inicio IS NULL;
