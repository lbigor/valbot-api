-- 013_ordens_servico.sql
-- Gestão de Ordens de Serviço (spec §12) + fluxo humano de 4 níveis (spec §11).
-- Toda divergência vira uma OS que percorre Auditor → Supervisor. Trilha de
-- auditoria imutável em os_eventos (append-only).

CREATE TABLE IF NOT EXISTS ordens_servico (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id          UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    tipo_divergencia VARCHAR(40) NOT NULL,
    status           VARCHAR(30) NOT NULL DEFAULT 'criada',
    auditor_email    VARCHAR(200),
    supervisor_email VARCHAR(200),
    prioridade       SMALLINT DEFAULT 3,        -- 1=alta (div. resultado) .. 5=baixa
    criada_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizada_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    encerrada_em     TIMESTAMPTZ,
    UNIQUE (exam_id)                            -- 1 OS por exame
);
CREATE INDEX IF NOT EXISTS idx_os_status ON ordens_servico (status);
CREATE INDEX IF NOT EXISTS idx_os_auditor ON ordens_servico (auditor_email) WHERE auditor_email IS NOT NULL;

-- Trilha de auditoria da OS (append-only — spec §17.2).
CREATE TABLE IF NOT EXISTS os_eventos (
    id          BIGSERIAL PRIMARY KEY,
    os_id       UUID NOT NULL REFERENCES ordens_servico(id) ON DELETE CASCADE,
    nivel       VARCHAR(20),                    -- 1_ia_principal | 2_comite | 3_auditor | 4_supervisor
    actor       VARCHAR(200),
    action      VARCHAR(60) NOT NULL,
    details     JSONB DEFAULT '{}'::jsonb,
    ip          VARCHAR(64),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_os_eventos_os ON os_eventos (os_id, created_at);

-- Parecer do Auditor (nível 3).
CREATE TABLE IF NOT EXISTS auditor_pareceres (
    id               BIGSERIAL PRIMARY KEY,
    os_id            UUID NOT NULL REFERENCES ordens_servico(id) ON DELETE CASCADE,
    auditor_email    VARCHAR(200) NOT NULL,
    decisao          VARCHAR(30) NOT NULL,      -- concorda_ia | discorda_ia | inconclusivo
    justificativa    TEXT NOT NULL,
    referencia_mbedv VARCHAR(120),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_parecer_os ON auditor_pareceres (os_id);

-- Decisão do Supervisor (nível 4 — analisa TODA divergência).
CREATE TABLE IF NOT EXISTS supervisor_decisoes (
    id                BIGSERIAL PRIMARY KEY,
    os_id             UUID NOT NULL REFERENCES ordens_servico(id) ON DELETE CASCADE,
    supervisor_email  VARCHAR(200) NOT NULL,
    decisao_final     VARCHAR(30) NOT NULL,
    concorda_auditor  BOOLEAN NOT NULL,
    justificativa     TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_decisao_os ON supervisor_decisoes (os_id);
