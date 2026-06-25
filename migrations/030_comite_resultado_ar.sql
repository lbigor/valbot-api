-- 030_comite_resultado_ar.sql
-- Veredito explícito do Comitê de IA (③) — APROVADO/REPROVADO.
--
-- Regra de negócio (Igor): o Comitê de IA é "máquina fria" (não alucina, decide
-- só pelos pontos do examinador) e DEVE cravar um veredito final A/R. Esse
-- resultado é comparado com:
--   • exams.resultado_exame  (A/R) → veredito do EXAMINADOR ① (TechPrático);
--   • exams.aprovado         (bool) → veredito da IA crua ② (Motor de Detecção).
-- Consenso = (resultado_exame='A' AND aprovado=true)
--          OR (resultado_exame='R' AND aprovado=false).
--
-- Valores: 'A' (APROVADO) | 'R' (REPROVADO). NULL enquanto o Comitê não rodou.

ALTER TABLE exam_comite_laudos
    ADD COLUMN IF NOT EXISTS resultado_comite CHAR(1);  -- 'A' aprovado | 'R' reprovado | NULL = não rodou

COMMENT ON COLUMN exam_comite_laudos.resultado_comite IS
    'Veredito explícito do Comitê de IA (③): A=APROVADO, R=REPROVADO, NULL=não rodou. Máquina fria, decide pelos pontos do examinador.';
