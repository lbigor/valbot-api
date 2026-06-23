-- =============================================================================
-- 024 — Decisão do supervisor: homologação da apuração de conduta.
--
-- O painel de decisão do supervisor tem a ação "Homologar apuração de conduta"
-- (mantém o encaminhamento do Bloco 9 / conduta da examinadora ao DETRAN). É
-- uma AÇÃO do supervisor que precisa ser gravada (não só reflete o auditor) —
-- registra se o supervisor manteve (true) ou cancelou (false) o encaminhamento.
--
-- Default FALSE: decisões antigas não homologaram explicitamente. O server
-- grava o valor real a cada decisão (POST /api/os/{id}/decisao).
--
-- Idempotente: ADD COLUMN IF NOT EXISTS.
-- =============================================================================

ALTER TABLE supervisor_decisoes
    ADD COLUMN IF NOT EXISTS homologar_conduta BOOLEAN NOT NULL DEFAULT FALSE;
