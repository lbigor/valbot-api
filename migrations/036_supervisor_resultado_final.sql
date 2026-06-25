-- 036 — Veredito final do Supervisor materializado como COLUNA em supervisor_decisoes.
--
-- BUG (QA tela do Supervisor): num "reformar" (o supervisor SOBREPÕE o auditor), o
-- A/R escolhido pelo supervisor (`resultado_final`) só era gravado no jsonb de
-- os_eventos.details — supervisor_decisoes NÃO tinha a coluna. O laudo (laudo_dossie
-- → _laudo_blocos_14_2 / _laudo_pdf_v2_html) tentava ler decisao.resultado_final,
-- não encontrava, e caía na DERIVAÇÃO por inversão binária do parecer do auditor
-- (frágil: quebra para INAPTO e desalinha do que o supervisor de fato decidiu).
-- Resultado: o LAUDO OFICIAL publicado não refletia o novo veredito do supervisor.
--
-- FIX: persistir o veredito explícito do supervisor numa coluna dedicada
-- (valores canônicos APROVADO/REPROVADO). O laudo passa a LER esse valor e
-- publicá-lo como veredito final (precedência Supervisor > Auditor > Comitê/consenso).
--
-- A tabela REAL de prod nasce da migration 013 (PK BIGSERIAL, sem UNIQUE(os_id),
-- colunas supervisor_email/decisao_final/concorda_auditor) — a definição de 017 é
-- no-op (CREATE TABLE IF NOT EXISTS sobre tabela já existente). Por isso a coluna
-- resultado_final NUNCA existiu em prod e precisa ser adicionada aqui.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS. Linhas antigas ficam com NULL (compat — o
-- laudo cai no fallback legado de derivação só quando a coluna é nula).

BEGIN;

ALTER TABLE supervisor_decisoes
    ADD COLUMN IF NOT EXISTS resultado_final VARCHAR(16);  -- APROVADO | REPROVADO | NULL (legado)

COMMENT ON COLUMN supervisor_decisoes.resultado_final IS
  'Veredito final EXPLÍCITO escolhido pelo supervisor (APROVADO | REPROVADO). '
  'Fonte canônica do veredito publicado no laudo (precede auditor/comitê). '
  'NULL = decisão antiga sem o A/R materializado (laudo deriva como fallback).';

-- Backfill best-effort das decisões antigas a partir do que ficou gravado no
-- evento de auditoria (os_eventos.details->>'resultado_final'). Normaliza para os
-- valores canônicos. Mantém NULL quando o evento não carregava o A/R.
UPDATE supervisor_decisoes sd
   SET resultado_final = CASE
         WHEN lower(btrim(ev.rf)) LIKE 'aprov%' THEN 'APROVADO'
         WHEN lower(btrim(ev.rf)) LIKE 'reprov%' OR lower(btrim(ev.rf)) LIKE 'repr%' THEN 'REPROVADO'
         WHEN upper(btrim(ev.rf)) = 'A' THEN 'APROVADO'
         WHEN upper(btrim(ev.rf)) = 'R' THEN 'REPROVADO'
         ELSE NULL
       END
  FROM (
        SELECT DISTINCT ON (e.os_id)
               e.os_id, (e.details->>'resultado_final') AS rf
          FROM os_eventos e
         WHERE e.action = 'decisao_supervisor'
           AND e.details->>'resultado_final' IS NOT NULL
         ORDER BY e.os_id, e.created_at DESC
       ) ev
 WHERE sd.os_id = ev.os_id
   AND sd.resultado_final IS NULL;

COMMIT;
