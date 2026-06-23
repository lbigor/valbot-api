-- =============================================================================
-- 006 — resultado_exame ganha valor 'N' (Não Avaliado)
--
-- Casos onde o examinador presencial não chegou a emitir veredito:
--   - Exame interrompido (motor falha técnica, ambiente perigoso)
--   - Candidato desistiu antes da prova começar
--   - Vídeo enviado pra revisão sem fechamento humano oficial
--
-- 'N' ≠ NULL:
--   'N' — examinador SABE e DECLAROU que não vai avaliar (estado explícito)
--   NULL — campo não foi informado pelo integrador (valor não enviado)
-- =============================================================================

ALTER TABLE exams
  DROP CONSTRAINT IF EXISTS exams_resultado_exame_check;

ALTER TABLE exams
  ADD CONSTRAINT exams_resultado_exame_check
  CHECK (resultado_exame IS NULL OR resultado_exame IN ('A', 'R', 'N'));

COMMENT ON COLUMN exams.resultado_exame IS
  'Veredito presencial do examinador (DETRAN). A=Aprovado, R=Reprovado, N=Não Avaliado (exame interrompido/desistência), NULL=não informado. COFRE — vem do init-upload, imutável.';
