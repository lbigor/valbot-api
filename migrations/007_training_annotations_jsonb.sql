-- =============================================================================
-- 007 — training_annotations: TEXT (texto livre) → JSONB (lista de anotações
--       ancoradas em timestamps do vídeo).
--
-- Formato novo:
--   [{"timestamp": "HH:MM:SS", "anotacoes": "texto"}]
--
-- Backfill: linhas TEXT existentes viram array de 1 item com timestamp
-- placeholder "00:00:00" (não temos como inferir o momento real). Conteúdo
-- da anotação é preservado.
--
-- Validação de schema (HH:MM:SS, anotacoes não-vazio) fica na API (Pydantic
-- TrainingAnnotation). DB confia no payload.
-- =============================================================================

-- 1. Preserva valor antigo numa coluna temporária
ALTER TABLE exams RENAME COLUMN training_annotations TO training_annotations_legacy;

-- 2. Cria coluna nova JSONB. NOT NULL + default '[]' espelha a semântica
--    do código (campo sempre presente; array vazio = sem anotações).
ALTER TABLE exams
  ADD COLUMN training_annotations JSONB NOT NULL DEFAULT '[]'::jsonb;

-- 3. Backfill: texto legado vira array com 1 item; timestamp placeholder.
UPDATE exams
SET training_annotations = jsonb_build_array(
  jsonb_build_object(
    'timestamp', '00:00:00',
    'anotacoes', training_annotations_legacy
  )
)
WHERE training_annotations_legacy IS NOT NULL
  AND length(trim(training_annotations_legacy)) > 0;

-- 4. Remove coluna legada
ALTER TABLE exams DROP COLUMN training_annotations_legacy;

COMMENT ON COLUMN exams.training_annotations IS
  'Lista de anotações humanas ancoradas em timestamps do vídeo. Formato: [{"timestamp": "HH:MM:SS", "anotacoes": "..."}]. Default array vazio. Schema validado na API (Pydantic TrainingAnnotation).';
