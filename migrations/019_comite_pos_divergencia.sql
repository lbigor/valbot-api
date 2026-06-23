-- =============================================================================
-- 019 — Divergência PÓS-Comitê de IA.
-- Após o Comitê reavaliar com o prompt MBEDV vigente, registra se a divergência
-- foi RESOLVIDA (comitê concorda com examinador → não entra na fila do Auditor)
-- ou MANTIDA (segue ao Auditor humano). NULL = comitê ainda não avaliou.
-- =============================================================================
ALTER TABLE exam_comite_laudos
  ADD COLUMN IF NOT EXISTS tipo_divergencia_pos_comite VARCHAR(40) NULL;
