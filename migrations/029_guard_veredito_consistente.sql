-- 029_guard_veredito_consistente.sql
-- GUARD-RAIL de consistência interna do veredito (pedido do produto, 2026-06-29).
--
-- REGRA PÉTREA (Res. CONTRAN 1.020/2025): o veredito é derivado ÚNICA e
-- exclusivamente da pontuação — `aprovado <=> pontuacao_total <= 10`. Um
-- resultado em que o veredito CONTRADIZ a pontuação (ex.: pontuacao_total > 10
-- mas aprovado=TRUE, ou <=10 mas reprovado sem gate) é INVÁLIDO e NUNCA pode
-- persistir como resultado bom — ele deve ir para ERRO e ser reprocessado.
--
-- Causa de origem possível: o motor confia em raw["aprovado"] do modelo, que
-- pode discordar da soma de infrações (gemini_analyzer.py:1528-1531). Este
-- trigger é DEFESA EM PROFUNDIDADE no banco: mesmo que o código regrida, o
-- resultado inconsistente não vira veredito válido.
--
-- COMPORTAMENTO (BEFORE INSERT OR UPDATE, fail-safe — NUNCA lança exceção que
-- abortaria o INSERT do init-upload):
--   • Só age quando HÁ resultado de análise (pontuacao_total E aprovado != NULL)
--     e não é gate_rejected (rejeição de admissibilidade é caso à parte).
--   • Se o veredito contradiz a pontuação: INVALIDA o resultado (zera
--     aprovado/pontuacao_total) e manda para reprocessamento usando o MESMO teto
--     de 5 do worker (retry_count_non_quota, migration 037):
--       - tentativas < 5 → status='queued' (fallback: worker re-analisa) e +1 retry
--       - tentativas >= 5 → status='failed' (terminal, fora dos indicadores)
--   • Registra o motivo em `error` para auditoria.
--
-- Idempotente: CREATE OR REPLACE + DROP/CREATE TRIGGER.

CREATE OR REPLACE FUNCTION trg_guard_veredito_consistente() RETURNS TRIGGER AS $$
DECLARE
    v_pont INTEGER := NEW.pontuacao_total;
    v_aprov BOOLEAN := NEW.aprovado;
BEGIN
    -- Sem resultado ainda (init-upload, fila): nada a validar.
    IF v_pont IS NULL OR v_aprov IS NULL THEN
        RETURN NEW;
    END IF;
    -- Rejeição de admissibilidade (gate) não segue a regra de pontuação.
    IF COALESCE(NEW.gate_rejected, FALSE) THEN
        RETURN NEW;
    END IF;
    -- Veredito consistente com a regra pétrea: deixa passar.
    IF v_aprov = (v_pont <= 10) THEN
        RETURN NEW;
    END IF;

    -- INCONSISTENTE → invalida e manda para erro/fallback.
    NEW.aprovado := NULL;
    NEW.pontuacao_total := NULL;
    IF COALESCE(NEW.retry_count_non_quota, 0) < 5 THEN
        NEW.status := 'queued';                              -- fallback: re-análise
        NEW.retry_count_non_quota := COALESCE(NEW.retry_count_non_quota, 0) + 1;
    ELSE
        NEW.status := 'failed';                              -- teto atingido
    END IF;
    NEW.error := left(
        COALESCE(NEW.error || ' | ', '') ||
        'guard029:veredito_inconsistente (pont=' || v_pont || ' aprovado=' || v_aprov ||
        ' -> esperado aprovado=' || (v_pont <= 10) || '); status=' || NEW.status,
        2000
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS exams_guard_veredito ON exams;
-- Dispara DEPOIS do exams_set_updated_at? A ordem entre BEFORE triggers é
-- alfabética pelo nome; 'exams_guard_veredito' < 'exams_set_updated_at', então
-- roda antes — ok, ambos só mexem em NEW.
CREATE TRIGGER exams_guard_veredito
    BEFORE INSERT OR UPDATE ON exams
    FOR EACH ROW EXECUTE FUNCTION trg_guard_veredito_consistente();
