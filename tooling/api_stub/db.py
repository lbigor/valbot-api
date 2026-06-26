"""Postgres helper p/ persistir exames (URL+renach).

Schema: migrations/001_init.sql (tabelas exams, exam_events).

Em dev local sem Postgres, define VALBOT_DB_DISABLED=1 — funções viram no-op.
Em prod, DATABASE_URL é obrigatório.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from datetime import UTC
from typing import Any

log = logging.getLogger("valbot.db")


def _mask_renach(renach: Any) -> str:
    """Mascara RENACH para logs (LGPD §17): mantém 2 primeiros + 2 últimos."""
    if not renach:
        return ""
    s = str(renach).strip()
    if len(s) <= 4:
        return "*" * len(s)
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


_DISABLED = os.environ.get("VALBOT_DB_DISABLED") == "1"
_DSN = os.environ.get("DATABASE_URL", "")

if not _DISABLED and not _DSN:
    log.warning("DATABASE_URL vazio e VALBOT_DB_DISABLED!=1 — DB writes vão falhar")

try:
    import psycopg
    from psycopg.types.json import Jsonb
except ImportError:
    psycopg = None
    Jsonb = None  # type: ignore[assignment]
    if not _DISABLED:
        log.warning("psycopg não instalado — instale `psycopg[binary]`")


@contextmanager
def _conn():
    if _DISABLED or psycopg is None or not _DSN:
        yield None
        return
    with psycopg.connect(_DSN, autocommit=True) as c:
        yield c


# ════════════════════════════════════════════════════════════════════════════
# Objetos de schema derivados — FONTE DA VERDADE no CÓDIGO (não em migrations).
#
# A view v_exams_overview era (re)criada só por migrations montadas em
# /docker-entrypoint-initdb.d (1º boot do Postgres) e pelo migrate.sh com
# auto-baseline — que faz BASELINE-SKIP de migrations cujo objeto já existe. Em
# prod o migrate.sh nem roda no CD (schema_migrations sequer existe lá), e o CD
# só copia server.py + db.py (NÃO db_views.py nem outros módulos). Resultado: a
# view ficava presa numa versão ANTIGA/INVERTIDA (comite_concluido→'comite';
# divergente→'auditoria') e correções manuais eram revertidas no deploy seguinte.
#
# Solução: a definição CORRETA vive AQUI (db.py, arquivo sincronizado pelo CD) e
# é recriada no STARTUP do app a cada boot, idempotente. Assim a view SEMPRE
# converge para a versão correta após qualquer deploy/restart.
#
# Definição EXATA da migration 034 (034_log_tentativas_busca_oficial.sql): a
# última migration boa, com a CASE de stage correta (classificação por LOG
# append-only) e todas as colunas.
# ════════════════════════════════════════════════════════════════════════════

# (1) Tabela append-only das tentativas de busca do oficial (igual à 034).
_SQL_EXAM_BUSCA_OFICIAL_LOG = """
CREATE TABLE IF NOT EXISTS exam_busca_oficial_log (
    id                  BIGSERIAL    PRIMARY KEY,
    exam_id             UUID         NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    tentativa_em        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    origem              TEXT         NOT NULL DEFAULT 'manual',
    resultado_recebido  TEXT,
    detalhe             TEXT
);

CREATE INDEX IF NOT EXISTS idx_busca_oficial_log_exam
    ON exam_busca_oficial_log (exam_id);
"""

# (2) v_exams_overview — fonte única do exame. DROP+CREATE (não REPLACE) porque a
# lista de colunas pode mudar entre versões e o Postgres recusa REPLACE que
# altere colunas. CASE de stage por LOG (EXISTS) com prioridade sobre o status.
_SQL_V_EXAMS_OVERVIEW = """
DROP VIEW IF EXISTS v_exams_overview CASCADE;

CREATE VIEW v_exams_overview AS
SELECT
  base.*,
  CASE
    WHEN base.gate_rejected                                                   THEN 'fora_escopo'
    WHEN lower(coalesce(base.status, '')) IN ('failed','error','erro')        THEN 'falhou'
    WHEN base.oficial_pendente AND base.tem_busca_oficial                     THEN 'aguardando_oficial'
    WHEN base.oficial_pendente                                               THEN 'aguardando'
    WHEN lower(coalesce(base.status, '')) IN ('queued','pending','novo','uploaded','recebido') THEN 'aguardando'
    WHEN lower(coalesce(base.status, '')) IN ('running','processing','analisando')             THEN 'processando'
    -- ── Desfecho do Supervisor: OS encerrada (decisão final) ⇒ CONCLUÍDO ──────
    -- A decisão do supervisor (save_supervisor_decisao) seta ordens_servico
    -- .encerrada_em; o exame sai da auditoria e vira 'concluido', INDEPENDENTE da
    -- divergência. Tem precedência sobre comitê/auditoria (a cadeia já terminou).
    WHEN base.os_encerrada_em IS NOT NULL                                     THEN 'concluido'
    WHEN base.divergente AND NOT base.comite_concluido                       THEN 'comite'
    WHEN base.divergente AND base.comite_concluido                           THEN 'auditoria'
    ELSE 'concluido'
  END AS stage
FROM (
  SELECT
    e.id,
    e.hash,
    e.external_id,
    e.candidato_nome,
    e.candidato_cpf,
    e.renach,
    e.examinador,
    e.local_unidade,
    e.auto_escola,
    e.categoria,
    e.veiculo,
    e.status,
    e.resultado,
    e.resultado_exame,
    e.aprovado,
    e.pontuacao_total,
    e.gate_rejected,
    e.gate_motivo,
    e.gate_detalhes,
    e.size_bytes,
    CASE WHEN e.size_bytes IS NOT NULL
         THEN ROUND(e.size_bytes::numeric / 1048576, 2)
         ELSE NULL END                        AS size_mb,
    e.duration_s,
    e.num_infracoes,
    e.layout_confianca,
    e.fabricante_provavel,
    e.cost_usd,
    e.cost_tokens_in,
    e.cost_tokens_out,
    e.gemini_elapsed_s,
    e.engine_backend,
    e.engine_model,
    e.engine_preset,
    e.gs_video,
    e.gs_result_json,
    e.gs_laudo_pdf,
    e.pdf_path,
    e.laudo_enviado_em,
    e.laudo_envio_status,
    e.laudo_envio_resultado,
    e.laudo_envio_tentativas,
    cv.veredito           AS validator_veredito,
    cv.confianca          AS validator_confianca,
    cv.motivo             AS validator_motivo,
    cv.fabricante         AS validator_fabricante,
    e.created_at,
    e.updated_at,
    (SELECT COUNT(*) FROM exam_events ev WHERE ev.exam_id = e.id) AS event_count,

    CASE WHEN upper(btrim(coalesce(e.resultado_exame, ''))) IN ('A','R')
         THEN upper(btrim(e.resultado_exame))
         ELSE NULL END                                          AS resultado_oficial,
    (upper(btrim(coalesce(e.resultado_exame, ''))) NOT IN ('A','R')) AS oficial_pendente,
    CASE WHEN e.aprovado IS TRUE  THEN 'A'
         WHEN e.aprovado IS FALSE THEN 'R'
         ELSE NULL END                                          AS resultado_calculado,
    ((upper(btrim(coalesce(e.resultado_exame, ''))) = 'A' AND e.aprovado IS FALSE)
     OR (upper(btrim(coalesce(e.resultado_exame, ''))) = 'R' AND e.aprovado IS TRUE)) AS divergente,
    EXISTS (SELECT 1 FROM exam_comite_laudos l WHERE l.exam_id = e.id) AS comite_concluido,
    EXISTS (SELECT 1 FROM exam_comentarios_compliance cc
            WHERE cc.exam_id = e.id AND cc.tipo = 'examinador_inadequado') AS conduta_inadequada,

    EXISTS (SELECT 1 FROM exam_busca_oficial_log l WHERE l.exam_id = e.id) AS tem_busca_oficial,

    coalesce(e.buscas_oficial, 0)                              AS buscas_oficial,
    e.ultima_busca_oficial                                     AS ultima_busca_oficial,

    CASE
      WHEN upper(btrim(coalesce(cv.veredito, ''))) = 'HOMO'     THEN true
      WHEN upper(btrim(coalesce(cv.veredito, ''))) = 'NAO_HOMO' THEN false
      WHEN coalesce(e.layout_confianca, cv.confianca) IS NOT NULL
           THEN (coalesce(e.layout_confianca, cv.confianca) >= 0.7)
      ELSE NULL
    END                                                        AS video_ok,
    (jsonb_array_length(coalesce(e.training_annotations, '[]'::jsonb)) > 0) AS tem_anotacoes,

    -- ── Desfecho da OS (decisão do supervisor) — fonte do stage 'concluido' ────
    -- 1 OS por exame (UNIQUE exam_id), então o LEFT JOIN é 1:1. encerrada_em é
    -- setado por save_supervisor_decisao ao homologar/reformar a decisão final.
    os_ord.status        AS os_status,
    os_ord.encerrada_em  AS os_encerrada_em
  FROM exams e
  LEFT JOIN exam_camera_validations cv ON cv.exam_id = e.id
  LEFT JOIN ordens_servico os_ord ON os_ord.exam_id = e.id
) base;
"""

# (3) v_exams_metrics — agregado diário, variação do mesmo core. CREATE OR
# REPLACE: a overview acima foi DROP+CREATE com CASCADE, derrubando esta junto.
#
# REGRA DE NEGÓCIO (Igor): o Valbot HOJE analisa SOMENTE categoria 'B'. O
# indicador abre com um FUNIL de 3 métricas (nesta ordem):
#   1. recebidos_total            — TODAS as categorias (A/B/C/D/E).
#   2. recebidos_catb             — só categoria 'B'.
#   3. com_resultado_oficial_catb — categoria 'B' COM oficial (A/R).
# Os DEMAIS contadores (aprovados, inaptos, divergentes, em_comite, em_auditoria,
# concluidos, recebidos, etc.) passam a filtrar categoria='B' — somar A/C/D/E é
# bug (ex.: 13/06 mostrava 839 em vez de 465 cat B). A view BASE (v_exams_overview)
# e a leitura por hash NÃO são filtradas — só estes AGREGADOS.
_SQL_V_EXAMS_METRICS = """
CREATE OR REPLACE VIEW v_exams_metrics AS
SELECT
  DATE_TRUNC('day', created_at)                       AS dia,
  -- ── FUNIL (topo do indicador) ────────────────────────────────────────────
  COUNT(*)                                            AS recebidos_total,
  COUNT(*) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B') AS recebidos_catb,
  COUNT(*) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B'
                     AND resultado_oficial IS NOT NULL)             AS com_resultado_oficial_catb,
  -- ── Demais métricas: SEMPRE escopadas em categoria='B' ────────────────────
  COUNT(*) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B') AS total_exames,
  COUNT(*) FILTER (WHERE resultado = 'APROVADO'      AND upper(btrim(coalesce(categoria,''))) = 'B') AS aprovados,
  COUNT(*) FILTER (WHERE resultado = 'INAPTO'        AND upper(btrim(coalesce(categoria,''))) = 'B') AS inaptos,
  COUNT(*) FILTER (WHERE resultado = 'SEM_AVALIACAO' AND upper(btrim(coalesce(categoria,''))) = 'B') AS sem_avaliacao,
  COUNT(*) FILTER (WHERE resultado = 'FALHOU'        AND upper(btrim(coalesce(categoria,''))) = 'B') AS falhos,
  COUNT(*) FILTER (WHERE resultado = 'PROCESSANDO'   AND upper(btrim(coalesce(categoria,''))) = 'B') AS processando,
  COUNT(*) FILTER (WHERE resultado = 'PENDENTE'      AND upper(btrim(coalesce(categoria,''))) = 'B') AS pendentes,
  SUM(cost_usd) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B')        AS custo_total_usd,
  AVG(gemini_elapsed_s) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B') AS gemini_avg_s,
  SUM(size_bytes) FILTER (WHERE upper(btrim(coalesce(categoria,''))) = 'B') / 1073741824.0 AS gb_processados,
  COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL AND upper(btrim(coalesce(categoria,''))) = 'B') AS com_resultado_oficial,
  COUNT(*) FILTER (WHERE oficial_pendente              AND upper(btrim(coalesce(categoria,''))) = 'B') AS aguardando_oficial,
  COUNT(*) FILTER (WHERE resultado_oficial = 'A'       AND upper(btrim(coalesce(categoria,''))) = 'B') AS oficial_aprovado,
  COUNT(*) FILTER (WHERE resultado_oficial = 'R'       AND upper(btrim(coalesce(categoria,''))) = 'B') AS oficial_reprovado,
  COUNT(*) FILTER (WHERE divergente                    AND upper(btrim(coalesce(categoria,''))) = 'B') AS divergentes,
  COUNT(*) FILTER (WHERE stage = 'comite'              AND upper(btrim(coalesce(categoria,''))) = 'B') AS em_comite,
  COUNT(*) FILTER (WHERE stage = 'auditoria'           AND upper(btrim(coalesce(categoria,''))) = 'B') AS em_auditoria,
  COUNT(*) FILTER (WHERE stage = 'concluido'           AND upper(btrim(coalesce(categoria,''))) = 'B') AS concluidos,
  COUNT(*) FILTER (WHERE stage = 'aguardando' AND oficial_pendente AND upper(btrim(coalesce(categoria,''))) = 'B') AS recebidos,
  COUNT(*) FILTER (WHERE stage = 'aguardando_oficial'  AND upper(btrim(coalesce(categoria,''))) = 'B') AS aguardando_oficial_ciclo,
  COUNT(*) FILTER (WHERE tem_anotacoes                 AND upper(btrim(coalesce(categoria,''))) = 'B') AS com_anotacoes,
  COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL AND tem_anotacoes AND upper(btrim(coalesce(categoria,''))) = 'B') AS completos
FROM v_exams_overview
GROUP BY DATE_TRUNC('day', created_at);
"""

# Ordem importa: log antes da overview (a view referencia o log); overview antes
# de metrics (metrics lê de overview).
_SCHEMA_OBJECTS = (
    ("exam_busca_oficial_log", _SQL_EXAM_BUSCA_OFICIAL_LOG),
    ("v_exams_overview", _SQL_V_EXAMS_OVERVIEW),
    ("v_exams_metrics", _SQL_V_EXAMS_METRICS),
)

# Migrações LEVES de coluna garantidas no boot (mesmo gancho das views).
# Motivo: o CD de prod NÃO roda migrations (migrate.sh não roda no deploy) — só o
# ensure_schema_objects() converge o schema a cada boot. Colunas novas que o código
# passou a LER/GRAVAR e que não existem na CREATE TABLE base (013) precisam entrar
# aqui, senão o primeiro INSERT estoura em prod. Estritamente `ADD COLUMN IF NOT
# EXISTS` (idempotente + best-effort; no-op quando a coluna já existe via migration).
#   - supervisor_decisoes.resultado_final (036) — veredito final publicado no laudo.
#   - supervisor_decisoes.homologar_conduta (024) — gravada no mesmo INSERT.
_SCHEMA_COLUMNS = (
    (
        "supervisor_decisoes.resultado_final",
        "ALTER TABLE supervisor_decisoes ADD COLUMN IF NOT EXISTS resultado_final VARCHAR(16)",
    ),
    (
        "supervisor_decisoes.homologar_conduta",
        "ALTER TABLE supervisor_decisoes ADD COLUMN IF NOT EXISTS homologar_conduta BOOLEAN NOT NULL DEFAULT FALSE",
    ),
)


def ensure_schema_objects() -> bool:
    """(Re)cria os objetos derivados de schema (views + log) de forma IDEMPOTENTE.

    FONTE DA VERDADE no código (constantes _SQL_* acima, neste mesmo db.py — que é
    o arquivo sincronizado pelo CD). Chamado no startup do app
    (server.py @app.on_event("startup")) — roda a CADA boot, então a
    v_exams_overview SEMPRE converge para a versão correta após qualquer deploy/
    restart, sem depender de migrate.sh / baseline / ordem de montagem em
    /docker-entrypoint-initdb.d.

    À PROVA DE FALHA: nunca propaga exceção (jamais derruba o boot). Cada objeto é
    aplicado num bloco isolado; falha num objeto não impede os demais. Retorna
    True se todos aplicaram, False se algum falhou (ou DB indisponível).

    Idempotente: CREATE TABLE/INDEX IF NOT EXISTS; DROP VIEW IF EXISTS CASCADE +
    CREATE VIEW; CREATE OR REPLACE VIEW.
    """
    if _DISABLED:
        log.info("db.ensure_schema_objects: VALBOT_DB_DISABLED=1 — skip")
        return False
    if psycopg is None or not _DSN:
        log.warning("db.ensure_schema_objects: psycopg/DSN indisponível — skip")
        return False

    ok = True
    try:
        with _conn() as c:
            if c is None:
                log.warning("db.ensure_schema_objects: sem conexão — skip")
                return False
            # 1) Colunas novas (ADD COLUMN IF NOT EXISTS) ANTES das views — garante
            # que o schema das tabelas converge no boot mesmo sem migrate.sh no CD.
            # Cada ALTER é isolado/best-effort (mesma política das views): falha numa
            # coluna não derruba o boot nem impede as demais.
            for nome, sql in _SCHEMA_COLUMNS:
                try:
                    c.execute(sql)
                    log.info("db.ensure_schema_objects: coluna %s OK", nome)
                except Exception as e:
                    ok = False
                    log.exception(
                        "db.ensure_schema_objects: FALHA na coluna %s (boot segue): %s", nome, e
                    )
            # 2) Objetos derivados (log + views).
            for nome, sql in _SCHEMA_OBJECTS:
                try:
                    c.execute(sql)
                    log.info("db.ensure_schema_objects: %s OK", nome)
                except Exception as e:
                    ok = False
                    log.exception("db.ensure_schema_objects: FALHA em %s (boot segue): %s", nome, e)
    except Exception as e:
        log.exception("db.ensure_schema_objects: falha geral (boot segue): %s", e)
        return False
    if ok:
        log.info("db.ensure_schema_objects: todos os objetos recriados (views=fonte=código)")
    return ok


def insert_exam(
    analysis_id: str,
    hash_: str,
    upload_meta: dict,
    gs_path: str,
    *,
    external_id: int | None = None,
    initial_status: str = "queued",
) -> None:
    """INSERT em exams. Idempotente via ON CONFLICT(hash) — re-init com mesmo hash atualiza gs_video.

    `external_id` (opcional) é o ID do integrador (ex: DETRAN) — coluna BIGINT
    indexada (migration 003). `initial_status` permite gravar `"uploading"` quando
    o download pro GCS ainda está em background; default `"queued"` mantém compat.

    `resultado_exame` (do upload_meta, se presente) é o veredito presencial do
    examinador ('A'/'R'). Cofre — preservado em re-inserts via COALESCE.
    """
    if _DISABLED:
        return
    cand = upload_meta.get("candidato", {})
    exam = upload_meta.get("exame", {})
    resultado_exame = upload_meta.get("resultado_exame")  # 'A' | 'R' | None
    try:
        with _conn() as c:
            if c is None:
                return
            c.execute(
                """
                INSERT INTO exams (
                    hash, external_id, candidato_nome, candidato_cpf, renach, processo, categoria,
                    veiculo, local_unidade, examinador, auto_escola, rubrica,
                    training_annotations, status, gs_video, resultado_exame
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (hash) DO UPDATE SET
                    gs_video        = EXCLUDED.gs_video,
                    renach          = COALESCE(EXCLUDED.renach, exams.renach),
                    external_id     = COALESCE(EXCLUDED.external_id, exams.external_id),
                    -- Campos do candidato/exame: só preencher se vier valor novo
                    -- (COALESCE preserva valor existente quando EXCLUDED é NULL).
                    candidato_nome  = COALESCE(NULLIF(EXCLUDED.candidato_nome, ''),  exams.candidato_nome),
                    candidato_cpf   = COALESCE(NULLIF(EXCLUDED.candidato_cpf, ''),   exams.candidato_cpf),
                    processo        = COALESCE(NULLIF(EXCLUDED.processo, ''),       exams.processo),
                    categoria       = COALESCE(NULLIF(EXCLUDED.categoria, ''),      exams.categoria),
                    veiculo         = COALESCE(NULLIF(EXCLUDED.veiculo, ''),        exams.veiculo),
                    local_unidade   = COALESCE(NULLIF(EXCLUDED.local_unidade, ''),  exams.local_unidade),
                    examinador      = COALESCE(NULLIF(EXCLUDED.examinador, ''),     exams.examinador),
                    auto_escola     = COALESCE(NULLIF(EXCLUDED.auto_escola, ''),    exams.auto_escola),
                    -- resultado_exame é COFRE: só grava se vier valor novo, NUNCA apaga.
                    resultado_exame = COALESCE(EXCLUDED.resultado_exame, exams.resultado_exame),
                    status          = EXCLUDED.status,
                    updated_at      = NOW()
                """,
                (
                    hash_,
                    external_id,
                    cand.get("nome"),
                    cand.get("cpf"),
                    cand.get("renach"),
                    cand.get("processo"),
                    cand.get("categoria"),
                    exam.get("veiculo"),
                    exam.get("local"),
                    exam.get("examinador"),
                    exam.get("auto_escola"),
                    exam.get("rubrica", "1020/2025"),
                    Jsonb(upload_meta.get("training_annotations") or []),
                    initial_status,
                    gs_path,
                    resultado_exame,
                ),
            )
            log_event(
                c,
                hash_,
                "uploaded",
                {
                    "analysis_id": analysis_id,
                    "gs_path": gs_path,
                    "external_id": external_id,
                    "resultado_exame": resultado_exame,
                },
            )
        log.info(
            "db.insert_exam ok hash=%s renach=%s ext=%s status=%s resultado_exame=%s",
            hash_[:12],
            _mask_renach(cand.get("renach")),
            external_id,
            initial_status,
            resultado_exame,
        )
    except Exception as e:
        log.exception("db.insert_exam falhou hash=%s: %s", hash_[:12], e)


def update_status(hash_: str, status: str, **kw: Any) -> None:
    """UPDATE em exams por hash. kw vira SET col=val (ex: gs_result_json=..., aprovado=...)."""
    if _DISABLED:
        return
    sets = ["status = %s"]
    vals: list[Any] = [status]
    for k, v in kw.items():
        sets.append(f"{k} = %s")
        vals.append(v)
    vals.append(hash_)
    try:
        with _conn() as c:
            if c is None:
                return
            c.execute(f"UPDATE exams SET {', '.join(sets)} WHERE hash = %s", vals)
            log_event(c, hash_, status, kw)
        log.info("db.update_status hash=%s status=%s", hash_[:12], status)
    except Exception as e:
        log.exception("db.update_status falhou hash=%s: %s", hash_[:12], e)


def create_api_key(name: str, scopes: list[str]) -> tuple[str, str]:
    """Cria nova API key. Retorna (id_uuid, raw_key) — raw_key mostrada 1× e nunca recuperável.

    Formato raw_key: `vbk_live_<32-hex>` (prefixo permite detectar accidental commit em git).
    """
    import hashlib
    import secrets

    if _DISABLED:
        raise RuntimeError("DB desabilitado — não dá pra criar api_key")
    raw = f"vbk_live_{secrets.token_hex(32)}"
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    import json as _json

    with _conn() as c:
        if c is None:
            raise RuntimeError("conexão Postgres não disponível")
        row = c.execute(
            """
            INSERT INTO api_keys (name, key_hash, scopes)
            VALUES (%s, %s, %s::jsonb)
            RETURNING id::text
            """,
            (name, key_hash, _json.dumps(scopes)),
        ).fetchone()
        key_id = row[0]
    log.info("api_key criada name=%s id=%s scopes=%s", name, key_id, scopes)
    return key_id, raw


def validate_api_key(raw_key: str, required_scope: str) -> dict | None:
    """Valida key e checa scope. Retorna {id, name, scopes} se ok, None se inválida.

    Atualiza last_used_at em sucesso.
    """
    import hashlib

    if _DISABLED or not raw_key:
        return None
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    try:
        with _conn() as c:
            if c is None:
                return None
            row = c.execute(
                """
                SELECT id::text, name, scopes
                FROM api_keys
                WHERE key_hash = %s AND revoked_at IS NULL
                """,
                (key_hash,),
            ).fetchone()
            if not row:
                return None
            key_id, name, scopes = row
            if required_scope not in (scopes or []):
                return None
            c.execute("UPDATE api_keys SET last_used_at = NOW() WHERE id = %s", (key_id,))
            return {"id": key_id, "name": name, "scopes": scopes}
    except Exception as e:
        log.exception("validate_api_key falhou: %s", e)
        return None


def update_result(
    hash_: str,
    result: dict,
    cost: dict | None = None,
    upload_meta: dict | None = None,
) -> None:
    """Popula colunas de resultado em `exams` a partir do result.json gerado.

    Chamado pelo pipeline (F2) imediatamente após write_text(result.json).
    Idempotente — re-rodar com mesmo result sobrescreve as colunas (esperado
    em re-análises).

    Extrai do result:
      - aprovado, pontuacao_total, num_infracoes
      - gate_rejected, gate_motivo, gate_detalhes (de result.rejected / .rejection_*)
      - duration_s, layout_confianca, fabricante_provavel (de result.video.*)
      - categoria (de result.candidato.categoria → result.video.layout.categoria →
        upload_meta.video.source_url no path S3 oficial techpratico)
      - cost_usd, cost_tokens_in/out, gemini_elapsed_s (do dict `cost` separado)

    `upload_meta` (opcional) habilita o fallback de categoria via parse do path
    S3 — necessário porque a integração batch DETRAN não envia categoria no
    init_upload, e o gate-reject pode terminar sem o analyzer LLM preencher
    `result.candidato.categoria`. Sem ele, categoria só persiste se vier
    explícita no result.
    """
    if _DISABLED:
        return
    video = result.get("video") or {}
    layout = video.get("layout") or {}
    cost = cost or (result.get("cost") or {})

    # Categoria CNH — 3 fontes em ordem decrescente de confiança.
    # 1. Analyzer LLM explicitou (result.candidato.categoria) — fonte definitiva.
    # 2. Layout detection encheu categoria — fonte derivada do fingerprinting.
    # 3. Fallback do path da source_url S3 (techpratico) — só quando upload_meta
    #    foi passado pelo caller. Padrão: /YYYYMMDD/HHMM/<CAT>/<RENACH>_*
    categoria = (result.get("candidato") or {}).get("categoria") or layout.get("categoria") or ""
    if not categoria and upload_meta is not None:
        source_url = (upload_meta.get("video") or {}).get("source_url") or ""
        # Padrão S3 oficial: amazonaws.com/.../<DATA>/<HORA>/<CAT>/<RENACH>_*
        # Categorias longas (ACC, AB) precedem curtas no regex pra match correto.
        import re as _re

        m = _re.search(r"/(ACC|AB|AC|AD|AE|A|B|C|D|E)/[A-Z0-9]+_", source_url)
        if m:
            categoria = m.group(1)

    sets: dict[str, Any] = {
        "aprovado": result.get("aprovado"),
        "pontuacao_total": result.get("pontuacao_total"),
        "num_infracoes": len(result.get("infracoes_detectadas") or []),
        "gate_rejected": result.get("rejected"),
        "gate_motivo": result.get("rejection_reason"),
        "gate_detalhes": result.get("rejection_details"),
        "duration_s": video.get("duration_s"),
        "layout_confianca": layout.get("confianca_layout"),
        "fabricante_provavel": layout.get("fabricante_provavel"),
        "categoria": categoria or None,  # None pra não sobrescrever via filtro abaixo
        "cost_usd": cost.get("usd"),
        "cost_tokens_in": cost.get("prompt_tokens"),
        "cost_tokens_out": cost.get("output_tokens"),
        "gemini_elapsed_s": cost.get("elapsed_s"),
        # Rubrica usada: v26 (CTB + MBEDV) pros novos, v25 fica no histórico.
        "catalog_version": result.get("catalog_version"),
    }
    # Remove chaves None pra não sobrescrever valor existente sem motivo
    sets = {k: v for k, v in sets.items() if v is not None}
    if not sets:
        return

    cols = ", ".join(f"{k} = %s" for k in sets)
    vals = list(sets.values()) + [hash_]
    try:
        with _conn() as c:
            if c is None:
                return
            c.execute(f"UPDATE exams SET {cols} WHERE hash = %s", vals)
            log_event(c, hash_, "result_updated", {"keys": list(sets.keys())})
        log.info("db.update_result hash=%s cols=%d", hash_[:12], len(sets))
    except Exception as e:
        log.exception("db.update_result falhou hash=%s: %s", hash_[:12], e)


def update_size_and_paths(
    hash_: str,
    *,
    size_bytes: int | None = None,
    pdf_path: str | None = None,
    gs_result_json: str | None = None,
    gs_laudo_pdf: str | None = None,
) -> None:
    """Atualiza paths/tamanhos sem mexer no resto. Usado por enrich+warm."""
    if _DISABLED:
        return
    sets: dict[str, Any] = {}
    if size_bytes is not None and size_bytes > 0:
        sets["size_bytes"] = size_bytes
    if pdf_path:
        sets["pdf_path"] = pdf_path
    if gs_result_json:
        sets["gs_result_json"] = gs_result_json
    if gs_laudo_pdf:
        sets["gs_laudo_pdf"] = gs_laudo_pdf
    if not sets:
        return
    cols = ", ".join(f"{k} = %s" for k in sets)
    vals = list(sets.values()) + [hash_]
    try:
        with _conn() as c:
            if c is None:
                return
            c.execute(f"UPDATE exams SET {cols} WHERE hash = %s", vals)
        log.info("db.update_size_and_paths hash=%s cols=%s", hash_[:12], list(sets.keys()))
    except Exception as e:
        log.exception("db.update_size_and_paths falhou hash=%s: %s", hash_[:12], e)


def upsert_infractions(hash_: str, infracoes: list[dict]) -> int:
    """Bulk insert de infrações filhas. Idempotente via UNIQUE(exam_id, regra_id, ts).

    Devolve o número de rows inseridas (já-existentes são puladas pelo ON CONFLICT).
    """
    if _DISABLED or not infracoes:
        return 0
    import json as _json

    inserted = 0
    try:
        with _conn() as c:
            if c is None:
                return 0
            # Pega exam_id (UUID) a partir do hash
            row = c.execute("SELECT id FROM exams WHERE hash = %s", (hash_,)).fetchone()
            if not row:
                log.warning("upsert_infractions: exam não encontrado hash=%s", hash_[:12])
                return 0
            exam_id = row[0]
            for inf in infracoes:
                if not isinstance(inf, dict):
                    continue
                cameras = inf.get("cameras_relevantes") or (
                    [inf["camera_origem"]] if inf.get("camera_origem") else []
                )
                try:
                    res = c.execute(
                        """
                        INSERT INTO exam_infractions (
                            exam_id, regra_id, gravidade, pontos, descricao,
                            timestamp_s, duracao_s, cameras, confianca,
                            evidence, base_legal, status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                        ON CONFLICT (exam_id, regra_id, COALESCE(timestamp_s, 0)) DO NOTHING
                        """,
                        (
                            exam_id,
                            inf.get("id") or inf.get("codigo") or "R1020-?",
                            (inf.get("severidade") or inf.get("gravidade") or "leve").lower(),
                            int(inf.get("pontos") or 0),
                            inf.get("descricao"),
                            inf.get("timestamp_s") or inf.get("ts_seconds"),
                            inf.get("duracao_s") or inf.get("duracao_seg"),
                            _json.dumps(cameras),
                            inf.get("confidence"),
                            inf.get("evidence"),
                            inf.get("base_legal"),
                            (inf.get("status") or "detectada"),
                        ),
                    )
                    inserted += res.rowcount or 0
                except Exception as e:
                    log.warning(
                        "infracao falhou hash=%s regra=%s: %s", hash_[:12], inf.get("id"), e
                    )
        log.info(
            "db.upsert_infractions hash=%s inserted=%d total=%d",
            hash_[:12],
            inserted,
            len(infracoes),
        )
        return inserted
    except Exception as e:
        log.exception("db.upsert_infractions falhou hash=%s: %s", hash_[:12], e)
        return 0


def upsert_camera_validation(
    hash_: str,
    validador: str,
    veredito: str,
    *,
    fabricante: str | None = None,
    confianca: float | None = None,
    motivo: str | None = None,
    cost_usd: float | None = None,
) -> None:
    """Insere/atualiza validação independente (ground truth Gemini)."""
    if _DISABLED:
        return
    try:
        with _conn() as c:
            if c is None:
                return
            row = c.execute("SELECT id FROM exams WHERE hash = %s", (hash_,)).fetchone()
            if not row:
                log.warning("upsert_camera_validation: exam não encontrado hash=%s", hash_[:12])
                return
            exam_id = row[0]
            c.execute(
                """
                INSERT INTO exam_camera_validations
                    (exam_id, validador, veredito, fabricante, confianca, motivo, cost_usd)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (exam_id) DO UPDATE SET
                    validador  = EXCLUDED.validador,
                    veredito   = EXCLUDED.veredito,
                    fabricante = EXCLUDED.fabricante,
                    confianca  = EXCLUDED.confianca,
                    motivo     = EXCLUDED.motivo,
                    cost_usd   = EXCLUDED.cost_usd,
                    validated_at = NOW()
                """,
                (exam_id, validador, veredito, fabricante, confianca, motivo, cost_usd),
            )
        log.info("db.upsert_camera_validation hash=%s veredito=%s", hash_[:12], veredito)
    except Exception as e:
        log.exception("db.upsert_camera_validation falhou hash=%s: %s", hash_[:12], e)


def fetch_status(hash_: str) -> str | None:
    """SELECT status FROM exams WHERE hash=... — leitura leve.

    Usado por `_read_status` em server.py como fonte autoritativa do estado
    do exame (DB é single source of truth depois da Fase A do refactor de
    rotinas). Devolve None se DB indisponível ou exame inexistente —
    caller pode cair em fallback (status.json) sem quebrar.
    """
    if _DISABLED:
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            row = c.execute(
                "SELECT status FROM exams WHERE hash = %s",
                (hash_,),
            ).fetchone()
            return row[0] if row else None
    except Exception as e:
        log.warning("db.fetch_status falhou hash=%s: %s", hash_[:12], e)
        return None


def get_overview(hash_: str) -> dict | None:
    """SELECT FROM v_exams_overview WHERE hash=...

    Devolve dict com todas as colunas da view ou None se não existe.
    Caminho de leitura usado pelo /api/exams/<hash> e similares.
    """
    if _DISABLED:
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            cur = c.execute(
                "SELECT * FROM v_exams_overview WHERE hash = %s",
                (hash_,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d.name for d in cur.description]
            return dict(zip(cols, row))
    except Exception as e:
        log.exception("db.get_overview falhou hash=%s: %s", hash_[:12], e)
        return None


def list_overview(
    *,
    limit: int = 10000,
    resultado: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """SELECT FROM v_exams_overview com filtros opcionais.

    Feed do GET /api/videos pós-F4. Ordena por mtime descendente (mais
    recente primeiro), igual ao behavior atual de file-walking.
    """
    if _DISABLED:
        return []
    where_parts: list[str] = []
    vals: list[Any] = []
    if resultado:
        where_parts.append("resultado = %s")
        vals.append(resultado)
    if status:
        where_parts.append("status = %s")
        vals.append(status)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    vals.append(limit)
    try:
        with _conn() as c:
            if c is None:
                return []
            cur = c.execute(
                f"""
                SELECT * FROM v_exams_overview
                {where}
                ORDER BY COALESCE(updated_at, created_at) DESC
                LIMIT %s
                """,
                vals,
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        log.exception("db.list_overview falhou: %s", e)
        return []


# =============================================================================
# COFRE — invariante: `exams` é IMUTÁVEL pros dados que vieram da integração.
# =============================================================================
#
# Os campos abaixo NUNCA podem ser apagados nem zerados por código de aplicação:
#
#   id, hash, external_id          ← chaves de correlação com sistema externo
#   candidato_nome, candidato_cpf  ← dados pessoais do candidato
#   renach, processo, categoria    ← identificadores DETRAN
#   veiculo, examinador,           ← dados do exame
#   auto_escola, local_unidade
#   rubrica, training_annotations  ← contexto da avaliação
#   gs_video                       ← path do vídeo original no GCS (storage)
#   resultado_exame                ← veredito presencial do examinador (A/R/NULL)
#   created_at                     ← timestamp de chegada
#
# Esses campos só são gravados/atualizados via `insert_exam` (que usa
# COALESCE+NULLIF — nunca apaga valor existente quando o novo é vazio).
#
# Campos DERIVADOS (resultado da análise) PODEM ser resetados pra re-análise:
#
#   status, error, gate_*, aprovado, pontuacao_total, num_infracoes,
#   layout_*, fabricante_provavel, duration_s, size_bytes, cost_*, pdf_path,
#   gs_result_json, gs_laudo_pdf
#
# A função `reset_exam_derivatives` faz isso de forma cirúrgica.
# Não existe DELETE em `exams` no fluxo normal — só em testes.
# =============================================================================


# Lista de colunas DERIVADAS — apagáveis com segurança via reset_exam_derivatives.
# NÃO incluir aqui nada que seja dado-fonte do integrador (vide bloco acima).
_DERIVATIVE_COLUMNS = (
    "error",
    "gate_rejected",
    "gate_motivo",
    "gate_detalhes",
    "aprovado",
    "pontuacao_total",
    "num_infracoes",
    "layout_detectado",
    "layout_confianca",
    "fabricante_provavel",
    "duration_s",
    "size_bytes",
    "cost_usd",
    "cost_tokens_in",
    "cost_tokens_out",
    "gemini_elapsed_s",
    "pdf_path",
    "gs_result_json",
    "gs_laudo_pdf",
)


def reset_exam_derivatives(hash_: str, *, new_status: str = "queued") -> bool:
    """Apaga TODOS os dados derivados de um exame pra permitir reprocessamento.

    O cofre (candidato/renach/processo/categoria/gs_video/etc) permanece
    intacto. Apenas resultado, gate, custo e infrações filhas são zerados.

    Operações:
      1) UPDATE exams SET <derivativos>=NULL, status='queued' WHERE hash=?
         → dispara trigger exams_log_status_change (audit em exam_events)
      2) DELETE FROM exam_infractions WHERE exam_id=?
      3) DELETE FROM exam_camera_validations WHERE exam_id=? (ground truth
         do validador também é re-gerado em re-análise)
      4) NÃO toca em exam_annotations (anotações são DO USUÁRIO, preservar)

    Devolve True se o exame foi encontrado e resetado, False se não existe.
    """
    if _DISABLED:
        return False
    sets_clause = ", ".join(f"{c} = NULL" for c in _DERIVATIVE_COLUMNS)
    try:
        with _conn() as c:
            if c is None:
                return False
            row = c.execute("SELECT id FROM exams WHERE hash = %s", (hash_,)).fetchone()
            if not row:
                log.warning("reset_exam_derivatives: hash %s nao existe", hash_[:12])
                return False
            exam_id = row[0]
            # 1) zera derivativos + muda status (dispara trigger)
            c.execute(
                f"UPDATE exams SET {sets_clause}, status = %s WHERE hash = %s",
                (new_status, hash_),
            )
            # 2) apaga infrações filhas
            c.execute("DELETE FROM exam_infractions WHERE exam_id = %s", (exam_id,))
            # 3) apaga validação independente (ground truth re-gera)
            c.execute("DELETE FROM exam_camera_validations WHERE exam_id = %s", (exam_id,))
            # 4) audit explícito
            log_event(c, hash_, "reset", {"reason": "manual_reprocess"})
        log.info("reset_exam_derivatives hash=%s status->%s", hash_[:12], new_status)
        return True
    except Exception as e:
        log.exception("reset_exam_derivatives falhou hash=%s: %s", hash_[:12], e)
        return False


def log_event(
    conn: Any,
    hash_: str,
    action: str,
    details: dict | None = None,
    actor: str | None = None,
    ip: str | None = None,
) -> None:
    """INSERT em exam_events — trilha de auditoria (LGPD §17.2). Conn já aberta
    passada por fora. `actor` = quem fez (email da sessão ou 'system' p/ pipeline);
    `ip` é guardado em details.ip. Retrocompatível: chamadas sem actor/ip seguem
    gravando actor NULL como antes."""
    if conn is None:
        return
    import json as _json

    payload = dict(details or {})
    if ip:
        payload.setdefault("ip", ip)
    try:
        conn.execute(
            """
            INSERT INTO exam_events (exam_id, actor, action, details)
            SELECT id, %s, %s, %s::jsonb FROM exams WHERE hash = %s
            """,
            (actor, action, _json.dumps(payload), hash_),
        )
    except Exception as e:
        log.warning("log_event falhou hash=%s action=%s: %s", hash_[:12], action, e)


def log_busca_oficial(
    hash_: str,
    origem: str = "manual",
    resultado_recebido: str | None = None,
    detalhe: str | None = None,
) -> None:
    """Registra UMA tentativa de busca do resultado oficial (TechPrático) na tabela
    APPEND-ONLY exam_busca_oficial_log (migration 034). Abre a própria conexão.

    Regra de negócio (Igor, dura): CADA chamada de busca do oficial — single, lote
    ou agendado, com SUCESSO OU FALHA — gera UMA linha aqui. É a fonte da
    classificação RECEBIDO (0 linhas) vs AGUARDANDO RESULTADO OFICIAL (>=1 linha)
    na v_exams_overview. NUNCA UPDATE/DELETE — só INSERT. Best-effort: nunca quebra
    a busca em si (se o log falhar, a tentativa segue)."""
    if _DISABLED:
        return
    try:
        with _conn() as c:
            if c is None:
                return
            c.execute(
                """
                INSERT INTO exam_busca_oficial_log (exam_id, origem, resultado_recebido, detalhe)
                SELECT id, %s, %s, %s FROM exams WHERE hash = %s
                """,
                (origem, resultado_recebido, detalhe, hash_),
            )
        log.info(
            "db.log_busca_oficial hash=%s origem=%s recebido=%s",
            hash_[:12],
            origem,
            resultado_recebido,
        )
    except Exception as e:
        log.warning("log_busca_oficial falhou hash=%s: %s", hash_[:12], e)


def log_access(hash_: str, actor: str | None, ip: str | None, action: str = "read") -> None:
    """Registra acesso de LEITURA a um exame (vídeo/laudo) na trilha — abre a
    própria conexão. Best-effort: nunca quebra a resposta ao usuário."""
    try:
        with _conn() as c:
            if c is None:
                return
            log_event(c, hash_, action, None, actor=actor, ip=ip)
    except Exception as e:  # noqa: BLE001
        log.warning("log_access falhou hash=%s: %s", str(hash_)[:12], e)


# =============================================================================
# Esteira de auditoria humana / custos (reconciliação) — funções adicionadas
# do repo. Quando VALBOT_DB_DISABLED=1 ou tabelas ausentes, viram no-op.
# =============================================================================


def _disabled() -> bool:
    """True quando não há DB pra ler/gravar — server.py decide pelo mock."""
    return _DISABLED or psycopg is None or not _DSN


def custos_agregados(dias: int = 30) -> dict | None:
    """Agregação de custo de processamento (vídeo/tokens) da janela — fila de cobrança.

    Quebra cost_usd e tokens por dia/unidade/categoria sobre `exams`. Devolve None
    se DB indisponível (server cai no fallback); dict (campos zerados se vazio) caso
    contrário. Cada recorte é isolado — falha de um não derruba o resto.
    """
    if _disabled():
        return None
    janela = str(int(dias))
    out: dict = {
        "periodo_dias": int(dias),
        "custo_total_usd": 0.0,
        "num_exames_cobrados": 0,
        "custo_medio_por_exame_usd": 0.0,
        "tokens_in_total": 0,
        "tokens_out_total": 0,
        "serie_diaria": [],
        "por_unidade": [],
        "por_categoria": [],
    }
    try:
        with _conn() as c:
            if c is None:
                return None
            # Escopo cat B (regra Igor: agregados contam só categoria='B'). A
            # quebra por_categoria abaixo é a EXCEÇÃO — ela mostra a distribuição
            # entre todas as categorias de propósito, então não leva este filtro.
            _catb = "AND upper(btrim(coalesce(categoria,''))) = 'B'"
            row = c.execute(
                f"""
                SELECT COALESCE(SUM(cost_usd),0) AS total,
                       COUNT(*) FILTER (WHERE cost_usd IS NOT NULL) AS n,
                       COALESCE(SUM(cost_tokens_in),0) AS tin,
                       COALESCE(SUM(cost_tokens_out),0) AS tout,
                       COALESCE(SUM(cost_usd)/NULLIF(COUNT(*) FILTER (WHERE cost_usd IS NOT NULL),0),0) AS media
                FROM exams WHERE created_at >= NOW() - (%s || ' days')::interval {_catb}
                """,
                (janela,),
            ).fetchone()
            if row:
                out["custo_total_usd"] = float(row[0] or 0)
                out["num_exames_cobrados"] = int(row[1] or 0)
                out["tokens_in_total"] = int(row[2] or 0)
                out["tokens_out_total"] = int(row[3] or 0)
                out["custo_medio_por_exame_usd"] = float(row[4] or 0)
            cur = c.execute(
                f"""
                SELECT to_char(date_trunc('day',created_at),'YYYY-MM-DD') AS dia,
                       COALESCE(SUM(cost_usd),0) AS custo, COUNT(*) AS n
                FROM exams WHERE created_at >= NOW() - (%s || ' days')::interval {_catb}
                GROUP BY 1 ORDER BY 1
                """,
                (janela,),
            )
            out["serie_diaria"] = [
                {"dia": r[0], "custo_usd": float(r[1] or 0), "num_exames": int(r[2] or 0)}
                for r in cur.fetchall()
            ]
            for chave, col in (("por_unidade", "local_unidade"), ("por_categoria", "categoria")):
                # por_unidade leva o filtro cat B; por_categoria é a quebra entre
                # categorias (mostra A/B/C/D/E de propósito) → sem filtro.
                _fcatb = "" if col == "categoria" else _catb
                cur = c.execute(
                    f"""
                    SELECT COALESCE(NULLIF({col},''),'N/D') AS rot,
                           COALESCE(SUM(cost_usd),0) AS custo, COUNT(*) AS n
                    FROM exams WHERE created_at >= NOW() - (%s || ' days')::interval {_fcatb}
                    GROUP BY 1 ORDER BY custo DESC LIMIT 50
                    """,
                    (janela,),
                )
                out[chave] = [
                    {"rotulo": r[0], "custo_usd": float(r[1] or 0), "num_exames": int(r[2] or 0)}
                    for r in cur.fetchall()
                ]
        return out
    except Exception as e:
        log.warning("db.custos_agregados falhou: %s", e)
        return out


def comite_pos_divergencia_por_hash() -> dict[str, str]:
    """Mapa exam_hash → tipo_divergencia_pos_comite (laudo de comitê mais recente).

    A fila usa isto pra ESCONDER exames cuja divergência foi RESOLVIDA pelo
    Comitê (concordou com o examinador após reavaliar com o prompt MBEDV).
    Resiliente: DB off, coluna ausente (migration 019 não aplicada) ou erro →
    devolve {} (nada é escondido — conservador).
    """
    if _disabled():
        return {}
    try:
        with _conn() as c:
            if c is None:
                return {}
            cur = c.execute(
                """
                SELECT DISTINCT ON (e.hash) e.hash, l.tipo_divergencia_pos_comite
                FROM exam_comite_laudos l
                JOIN exams e ON e.id = l.exam_id
                WHERE l.tipo_divergencia_pos_comite IS NOT NULL
                ORDER BY e.hash, l.created_at DESC
                """
            )
            return {row[0]: row[1] for row in cur.fetchall() if row[0]}
    except Exception as e:
        log.warning("db.comite_pos_divergencia_por_hash indisponível: %s", e)
        return {}


def os_id_por_hash(exam_hash: str, tipo_divergencia: str = "resultado") -> str | None:
    """GET-OR-CREATE: resolve (ou cria) o id da OS (ordens_servico.id) do exam_hash.

    As OS NÃO são geradas pelo pipeline em prod (a fila /api/os é derivada
    on-the-fly de v_exams_overview); a tabela `ordens_servico` fica vazia. Mas o
    parecer do Auditor precisa de uma OS formal pra gravar em auditor_pareceres.

    Por isso este resolvedor é GET-OR-CREATE: resolve exam_hash → exam_id (uuid),
    e faz INSERT ... ON CONFLICT(exam_id) DO UPDATE em ordens_servico, devolvendo
    o id da OS. Idempotente (UNIQUE em exam_id). None se DB off, hash sem exam, ou erro.

    `tipo_divergencia` (NOT NULL) — default 'resultado' (que é o tipo derivado por
    /api/os). Aceita qualquer string curta (≤40 chars).
    """
    if _disabled() or not exam_hash:
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            erow = c.execute("SELECT id FROM exams WHERE hash = %s", (exam_hash,)).fetchone()
            if not erow:
                log.warning("os_id_por_hash: exam não encontrado hash=%s", exam_hash[:12])
                return None
            exam_id = erow[0]
            tipo = (tipo_divergencia or "resultado")[:40]
            row = c.execute(
                """
                INSERT INTO ordens_servico (exam_id, tipo_divergencia, status, numero_os)
                VALUES (%s, %s, 'aguardando_supervisor', %s)
                ON CONFLICT (exam_id) DO UPDATE SET atualizada_em = NOW()
                RETURNING id::text
                """,
                (exam_id, tipo, f"OS-{exam_hash[:8].upper()}"),
            ).fetchone()
            return row[0] if row else None
    except Exception as e:
        log.warning("db.os_id_por_hash falhou hash=%s: %s", exam_hash, e)
        return None


# Hash sha256 de exame = 64 hex. O frontend manda ora o id REAL da OS (UUID),
# ora este hash (os_id sintético da fila /api/os). Usado por resolver_os_id.
_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
# numero_os materializado = "OS-<hash8>" (ver os_id_por_hash / ensure_os_em_auditoria,
# que gravam f"OS-{hash[:8].upper()}"). Depois que as OS foram materializadas o
# frontend (SupervisorWorkspace) passou a mandar este numero_os no lugar do hash cru.
_NUMERO_OS_RE = re.compile(r"^OS-([0-9a-fA-F]{6,})$")


def resolver_os_id(identificador: str | None, tipo_divergencia: str = "resultado") -> str | None:
    """Resolve um identificador vindo do frontend → id REAL da OS (UUID).

    TOLERANTE (o frontend manda os três formatos, ver SupervisorWorkspace):
      • 64 hex  → é o HASH do exame → os_id_por_hash (GET-OR-CREATE; materializa a
        OS se ainda não existir — resolve de quebra o legado de exames em
        'auditoria' sem ordens_servico).
      • "OS-<hash8>" (numero_os de uma OS já materializada) → resolve para o UUID
        real: PRIMEIRO via SELECT por numero_os (a OS existe); se não achar, extrai
        o sufixo hex, recupera o hash completo do exame (hash LIKE '<sufixo>%') e
        cai no os_id_por_hash (GET-OR-CREATE). Sem isso o "OS-..." cru ia direto p/
        uma comparação com coluna UUID → ORA/Postgres "invalid input syntax for uuid".
      • caso contrário → assume ser o UUID de uma OS já existente; devolve como veio
        (a validação real acontece em save_supervisor_decisao, que faz o SELECT por PK).
    None se DB off, hash sem exame, ou identificador vazio.
    """
    if _disabled() or not identificador:
        return None
    s = str(identificador).strip()
    if not s:
        return None
    if _HEX64_RE.match(s):
        return os_id_por_hash(s, tipo_divergencia)
    m = _NUMERO_OS_RE.match(s)
    if m:
        sufixo = m.group(1)
        exam_hash = None
        try:
            with _conn() as c:
                if c is None:
                    return None
                # 1) OS já materializada → numero_os guarda o vínculo p/ o UUID real.
                #    numero_os é gravado com sufixo UPPER (f"OS-{hash[:8].upper()}").
                row = c.execute(
                    "SELECT id::text FROM ordens_servico WHERE numero_os = %s",
                    (f"OS-{sufixo.upper()}",),
                ).fetchone()
                if row:
                    return row[0]
                # 2) Ainda sem OS → resolve o exame pelo prefixo do hash (sha256
                #    lowercase) e materializa via GET-OR-CREATE logo abaixo.
                erow = c.execute(
                    "SELECT hash FROM exams WHERE hash LIKE %s LIMIT 1",
                    (sufixo.lower() + "%",),
                ).fetchone()
                exam_hash = erow[0] if erow else None
        except Exception as e:
            log.warning("db.resolver_os_id falhou id=%s: %s", s, e)
            return None
        if exam_hash:
            return os_id_por_hash(exam_hash, tipo_divergencia)
        return None
    return s


def ensure_os_em_auditoria(hashes: list[str]) -> int:
    """Materializa (idempotente) uma OS para cada exam_hash dado que ainda não a
    tenha. UM único INSERT...SELECT ... ON CONFLICT(exam_id) DO NOTHING — barato
    mesmo com centenas de hashes (uma ida ao banco). Cobre os exames que entraram
    em 'auditoria' (divergência pós-comitê) ANTES de existir camada de
    materialização. Espelha exatamente o shape de os_id_por_hash
    (tipo_divergencia='resultado', status='aguardando_supervisor', numero_os).
    Retorna o nº de OS criadas (0 se DB off / nada a criar). Nunca lança.
    """
    if _disabled():
        return 0
    hs = [h for h in (hashes or []) if h]
    if not hs:
        return 0
    try:
        with _conn() as c:
            if c is None:
                return 0
            cur = c.execute(
                """
                INSERT INTO ordens_servico (exam_id, tipo_divergencia, status, numero_os)
                SELECT e.id, 'resultado', 'aguardando_supervisor',
                       'OS-' || upper(substr(e.hash, 1, 8))
                FROM exams e
                WHERE e.hash = ANY(%s)
                ON CONFLICT (exam_id) DO NOTHING
                """,
                (hs,),
            )
            n = cur.rowcount or 0
            if n:
                log.info("db.ensure_os_em_auditoria: %d OS materializadas", n)
            return n
    except Exception as e:
        log.warning("db.ensure_os_em_auditoria falhou: %s", e)
        return 0


def reset_running_orfaos(idade_min: int = 5) -> int:
    """Re-enfileira exames presos em status='running' órfãos (sem worker ativo).

    Cada restart do container (CD, recreate) mata os batches em andamento e deixa
    os exames como 'running' órfãos; o worker só faz CLAIM de 'queued'
    (_claim_next_queued), então nunca os recupera → a fila trava. No BOOT do worker
    nenhum processamento está ativo (o processo anterior morreu), logo é seguro
    resetar todos os 'running' de volta para 'queued'. O gate de resultado oficial
    NÃO é tocado aqui: exames sem oficial voltam a 'queued' e o worker corretamente
    os SKIPa; os com oficial são processados.

    `idade_min` (default 5) — só reseta 'running' mais velhos que isso, por garantia
    (no boot qualquer órfão real já passou disso). Best-effort/idempotente: try/except,
    loga e NUNCA derruba o boot. Retorna o nº de linhas afetadas (0 se DB off / nada).
    """
    if _disabled():
        return 0
    try:
        with _conn() as c:
            if c is None:
                return 0
            cur = c.execute(
                """
                UPDATE exams SET status='queued', updated_at=NOW()
                WHERE status='running'
                  AND updated_at < NOW() - (%s || ' minutes')::interval
                """,
                (str(int(idade_min)),),
            )
            return cur.rowcount or 0
    except Exception as e:
        log.warning("db.reset_running_orfaos falhou: %s", e)
        return 0


def save_parecer_auditor(
    os_id: str,
    *,
    auditor: str | None,
    decisao: str,
    resultado_final: str | None,
    justificativa: str | None,
    referencia_mbedv: str | None,
) -> dict | None:
    """Upsert do parecer (UNIQUE os_id) + move OS → aguardando_supervisor + audita.

    Devolve o parecer gravado, ou None se DB off (server responde eco do mock).
    """
    if _disabled():
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            # Resolve exam_id (+ hash p/ trilha) e o status atual da OS.
            erow = c.execute(
                """
                SELECT os.exam_id::text, os.status, e.hash
                FROM ordens_servico os
                JOIN exams e ON e.id = os.exam_id
                WHERE os.id = %s
                """,
                (os_id,),
            ).fetchone()
            if not erow:
                return None
            exam_id, de_status, exam_hash = erow
            import json as _json

            # auditor_pareceres NÃO tem UNIQUE(os_id) nem coluna resultado_final/
            # exam_id no schema de prod. Upsert manual: apaga o parecer anterior
            # da OS e insere o novo. `justificativa` é NOT NULL → ''.
            # resultado_final fica preservado no os_eventos.details (jsonb) e na
            # trilha exam_events. O parecer humano não carrega infrações.
            c.execute("DELETE FROM auditor_pareceres WHERE os_id = %s", (os_id,))
            prow = c.execute(
                """
                INSERT INTO auditor_pareceres
                    (os_id, auditor_email, decisao, justificativa, referencia_mbedv)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (os_id, auditor or "", decisao, justificativa or "", referencia_mbedv),
            ).fetchone()
            # Move OS → aguardando_supervisor + registra o auditor.
            c.execute(
                "UPDATE ordens_servico SET status = %s, auditor_email = %s, atualizada_em = NOW() WHERE id = %s",
                ("aguardando_supervisor", auditor, os_id),
            )
            # Audita em os_eventos (resultado_final no details jsonb). O parecer
            # humano NÃO carrega lista de infrações — `infracoes` não é gravado.
            c.execute(
                """
                INSERT INTO os_eventos (os_id, actor, action, details)
                VALUES (%s, %s, 'parecer_auditor', %s::jsonb)
                """,
                (
                    os_id,
                    auditor,
                    _json.dumps(
                        {
                            "decisao": decisao,
                            "resultado_final": resultado_final,
                            "de_status": de_status,
                            "para_status": "aguardando_supervisor",
                            "referencia_mbedv": referencia_mbedv,
                        }
                    ),
                ),
            )
            # Espelha no exam_events (auditoria por hash, se houver).
            if exam_hash:
                log_event(
                    c,
                    exam_hash,
                    "parecer_auditor",
                    {"os_id": os_id, "decisao": decisao, "resultado_final": resultado_final},
                    actor=auditor,
                )
            return {
                "id": prow[0],
                "os_id": os_id,
                "exam_id": exam_id,
                "auditor": auditor,
                "decisao": decisao,
                "resultado_final": resultado_final,
                "justificativa": justificativa,
                "referencia_mbedv": referencia_mbedv,
                "created_at": prow[1],
                "updated_at": prow[1],
                "status_os": "aguardando_supervisor",
            }
    except Exception as e:
        log.exception("db.save_parecer_auditor falhou os=%s: %s", os_id, e)
        return None


# ============================================================================
# APP_SETTINGS — config chave/valor (provisão de câmbio USD→BRL, etc.).
# Tabela: app_settings(key PK, value text NOT NULL, description, updated_at, updated_by).
# ============================================================================


def list_app_settings() -> list[dict] | None:
    """Lista todas as configs (key/value/description/updated_at). None se DB off."""
    if _disabled():
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            rows = c.execute(
                """
                SELECT key, value, description, updated_at, updated_by
                FROM app_settings ORDER BY key
                """
            ).fetchall()
            out = []
            for r in rows:
                ua = r[3]
                out.append(
                    {
                        "key": r[0],
                        "value": r[1],
                        "description": r[2],
                        "updated_at": ua.isoformat() if hasattr(ua, "isoformat") else ua,
                        "updated_by": r[4],
                    }
                )
            return out
    except Exception as e:
        log.warning("db.list_app_settings falhou: %s", e)
        return None


def get_app_setting(key: str, default: str | None = None) -> str | None:
    """Retorna o value (str) de uma chave, ou `default` se ausente/DB off."""
    if _disabled() or not key:
        return default
    try:
        with _conn() as c:
            if c is None:
                return default
            row = c.execute("SELECT value FROM app_settings WHERE key = %s", (key,)).fetchone()
            return row[0] if row else default
    except Exception as e:
        log.warning("db.get_app_setting falhou key=%s: %s", key, e)
        return default


def set_app_setting(
    key: str, value: str, *, updated_by: str | None = None, description: str | None = None
) -> dict | None:
    """Upsert de uma config (UPDATE se existe, INSERT senão). None se DB off/erro.

    Devolve {key, value, description, updated_at, updated_by}.
    """
    if _disabled() or not key:
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            row = c.execute(
                """
                INSERT INTO app_settings (key, value, description, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value       = EXCLUDED.value,
                    description = COALESCE(EXCLUDED.description, app_settings.description),
                    updated_by  = EXCLUDED.updated_by,
                    updated_at  = NOW()
                RETURNING key, value, description, updated_at, updated_by
                """,
                (str(key), str(value), description, updated_by),
            ).fetchone()
            if not row:
                return None
            ua = row[3]
            return {
                "key": row[0],
                "value": row[1],
                "description": row[2],
                "updated_at": ua.isoformat() if hasattr(ua, "isoformat") else ua,
                "updated_by": row[4],
            }
    except Exception as e:
        log.warning("db.set_app_setting falhou key=%s: %s", key, e)
        return None


# ============================================================================
# TELAS DE GESTÃO (reconciliação) — funções copiadas do repo api_stub/db.py.
# Usuários, Relatórios/Laudo-dossiê, Telemetria/Métricas, Cron/Batch, Supervisor.
# Dependências de senha (_PBKDF2_ITERS / hash_password / create_admin_user)
# trazidas junto — não existiam neste db de produção.
# ============================================================================

_PBKDF2_ITERS = 200_000


def hash_password(password: str, *, iterations: int = _PBKDF2_ITERS) -> str:
    """Gera hash PBKDF2-SHA256 no formato `pbkdf2_sha256$iters$salt_hex$hash_hex`."""
    import hashlib
    import secrets

    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def create_admin_user(email: str, password: str, role: str = "admin") -> str:
    """Cria (ou reativa) um usuário do painel na tabela ÚNICA `users`. Retorna o id.

    Tabela unificada (2026): `admin_users` virou backup; o painel de Usuários e o
    login do SPA operam ambos sobre `users`, com admin = FLAG `role`. O hash é
    gravado com `_hash_password_login` (formato que `server._verify_password` lê),
    de modo que o usuário criado JÁ consegue logar com a senha definida aqui.
    `ativo=TRUE` e `revoked_at=NULL` reativam quem estava revogado.
    """
    if _DISABLED:
        raise RuntimeError("DB desabilitado — não dá pra criar admin")
    email = (email or "").strip().lower()
    with _conn() as c:
        if c is None:
            raise RuntimeError("conexão Postgres não disponível")
        row = c.execute(
            """
            INSERT INTO users (email, senha_hash, role, nome, ativo,
                               senha_temporaria, revoked_at)
            VALUES (%s, %s, %s, %s, TRUE, FALSE, NULL)
            ON CONFLICT (email) DO UPDATE
                SET senha_hash = EXCLUDED.senha_hash,
                    role = EXCLUDED.role,
                    ativo = TRUE,
                    senha_temporaria = FALSE,
                    revoked_at = NULL
            RETURNING id::text
            """,
            (email, _hash_password_login(password), role, email.split("@")[0]),
        ).fetchone()
        admin_id = row[0]
    log.info("user (painel) criado/atualizado email=%s id=%s role=%s", email, admin_id, role)
    return admin_id


def list_admin_users() -> list[dict] | None:
    """Lista os admins do painel. None se DB off; [] se tabela vazia.

    Não devolve senha_hash — só metadados de gestão (id, email, role,
    timestamps, revoked). Tabela ÚNICA `users` (admin = flag `role`); `revoked_at`
    e `ativo` vêm das colunas reais e o front usa `revoked_at` p/ o status.
    `is_admin` é derivado de role IN (admin, auditor) — espelha _verify_session.
    Só lista contas ATIVAS por padrão? Não: lista todas (a tela mostra revogados).
    """
    if _disabled():
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            cur = c.execute(
                """
                SELECT id::text, email, role, created_at, last_login_at,
                       revoked_at, ativo,
                       (role IN ('admin','auditor')) AS is_admin,
                       pode_enviar_laudos
                FROM users
                ORDER BY created_at DESC
                """
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        log.exception("db.list_admin_users falhou: %s", e)
        return None


def update_admin_user(
    user_id: str, *, role: str | None = None, revoked: bool | None = None
) -> dict | None:
    """Atualiza role e/ou estado de revogação de um admin. None se DB off ou inexistente.

    Tabela ÚNICA `users` (admin = flag role). `revoked=True` →
    revoked_at=NOW(), ativo=FALSE (bloqueia o login, que exige ativo);
    `revoked=False` → revoked_at=NULL, ativo=TRUE (reativa).
    Devolve o registro atualizado (sem o hash).
    """
    if _disabled():
        return None
    sets: list[str] = []
    vals: list[Any] = []
    if role is not None:
        sets.append("role = %s")
        vals.append(role)
    if revoked is not None:
        sets.append("revoked_at = " + ("NOW()" if revoked else "NULL"))
        sets.append("ativo = " + ("FALSE" if revoked else "TRUE"))
    if not sets:
        return None
    vals.append(user_id)
    try:
        with _conn() as c:
            if c is None:
                return None
            row = c.execute(
                f"""
                UPDATE users SET {", ".join(sets)}
                WHERE id = %s
                RETURNING id::text, email, role, created_at, last_login_at,
                          revoked_at, ativo
                """,
                vals,
            ).fetchone()
            if not row:
                return None
            cols = ["id", "email", "role", "created_at", "last_login_at", "revoked_at", "ativo"]
            return dict(zip(cols, row))
    except Exception as e:
        log.exception("db.update_admin_user falhou id=%s: %s", user_id, e)
        return None


def _hash_password_login(password: str, *, iterations: int = _PBKDF2_ITERS) -> str:
    """Hash PBKDF2-SHA256 no MESMO formato que o login do SPA valida
    (server._verify_password): salt como STRING hex e `salt.encode()` no
    derivador. Difere de `hash_password` (que usa o salt como bytes brutos),
    cujo hash o login da tabela `users` NÃO consegue verificar. Use este para
    gravar senha em `users.senha_hash`.
    """
    import hashlib
    import secrets

    salt = secrets.token_hex(16)  # string hex — login faz salt.encode()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"


def reset_admin_password(user_id: str) -> str | None:
    """Gera uma senha temporária, grava o hash e devolve a senha em claro (1×).

    None se DB off ou usuário inexistente. A senha temp tem ~12 chars
    url-safe; o operador deve repassá-la ao usuário, que será OBRIGADO a
    trocá-la no 1º login.

    Tabela ÚNICA `users` (2026): `user_id` é o uuid de `users.id` (a tela opera
    por id), e o login do SPA autentica contra a mesma `users`. Gravamos o hash
    temporário em `users.senha_hash` com `_hash_password_login` (formato que
    `server._verify_password` lê) + `senha_temporaria=TRUE` na MESMA linha,
    casando por id. Sem dupla escrita — `admin_users` é só backup.
    """
    if _disabled():
        return None
    import secrets

    temp = secrets.token_urlsafe(9)  # ~12 chars
    try:
        with _conn() as c:
            if c is None:
                return None
            row = c.execute(
                """
                UPDATE users
                   SET senha_hash = %s, senha_temporaria = TRUE
                 WHERE id = %s
                RETURNING email
                """,
                (_hash_password_login(temp), user_id),
            ).fetchone()
            if not row:
                return None
        log.info("user senha resetada id=%s (temp+flag em users)", user_id)
        return temp
    except Exception as e:
        log.exception("db.reset_admin_password falhou id=%s: %s", user_id, e)
        return None


def delete_admin_user(user_id: str) -> bool:
    """Revoga (soft-delete) um usuário do painel — set revoked_at=NOW(),
    ativo=FALSE (bloqueia o login). False se DB off/inexistente.

    Tabela ÚNICA `users`. Nunca apaga a linha (preserva trilha). Idempotente.
    """
    if _disabled():
        return False
    try:
        with _conn() as c:
            if c is None:
                return False
            row = c.execute(
                "UPDATE users SET revoked_at = NOW(), ativo = FALSE WHERE id = %s RETURNING id",
                (user_id,),
            ).fetchone()
            return bool(row)
    except Exception as e:
        log.exception("db.delete_admin_user falhou id=%s: %s", user_id, e)
        return False


# --- 2. Relatórios — lista de v_exams_overview filtrada ----------------------


def list_resultados(
    *,
    dias: int | None = None,
    desde: str | None = None,
    unidade: str | None = None,
    examinador: str | None = None,
    resultado: str | None = None,
    categoria: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict] | None:
    """Lista de exames (v_exams_overview) p/ a tela Relatórios. None se DB off.

    Filtros opcionais combináveis. `dias` recorta por created_at. Ordenado por
    created_at desc.
    """
    if _disabled():
        return None
    where: list[str] = []
    vals: list[Any] = []
    if dias:
        where.append("created_at >= NOW() - (%s || ' days')::interval")
        vals.append(str(int(dias)))
    if unidade:
        where.append("local_unidade = %s")
        vals.append(unidade)
    if examinador:
        where.append("examinador = %s")
        vals.append(examinador)
    if resultado:
        where.append("resultado = %s")
        vals.append(resultado)
    if categoria:
        where.append("categoria = %s")
        vals.append(categoria)
    if desde:
        # Corte por data absoluta (fila só com vídeos a partir de DD/MM/AAAA).
        where.append("created_at >= %s")
        vals.append(desde)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    vals.append(int(limit))
    vals.append(max(0, int(offset)))
    try:
        with _conn() as c:
            if c is None:
                return None
            cur = c.execute(
                f"""
                SELECT * FROM v_exams_overview
                {clause}
                ORDER BY COALESCE(updated_at, created_at) DESC
                LIMIT %s OFFSET %s
                """,
                vals,
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        log.exception("db.list_resultados falhou: %s", e)
        return None


# Prazo default do auditor para o vencimento do SLA, em horas. Bate com o
# DEFAULT da coluna ordens_servico.sla_prazo_auditor_h (migration 014).
SLA_PRAZO_AUDITOR_H = 24


def os_enrichment(hashes: list[str]) -> dict[str, dict] | None:
    """Sinais de enriquecimento da fila de OS por exam_hash (dados que já existem
    no banco mas não estão na v_exams_overview). Uma query batelada por sinal,
    chaveada pelo hash do exame. None se DB off; {} se nenhum hash.

    Retorna, por hash:
      - conduta_inadequada (bool): há comentário de conduta inadequada do
        examinador em exam_comentarios_compliance (tipo='examinador_inadequado').
      - comite_concluido (bool): há laudo de comitê (exam_comite_laudos) para o
        exame.

    Ausência de hash no dicionário ⇒ sem dado ⇒ o chamador grava null. NUNCA
    inventa valor: só entram hashes que casaram em cada tabela.
    """
    if _disabled():
        return None
    hs = [h for h in (hashes or []) if h]
    if not hs:
        return {}
    out: dict[str, dict] = {}
    try:
        with _conn() as c:
            if c is None:
                return None
            # Conduta inadequada do examinador (compliance §6/§10).
            cur = c.execute(
                """
                SELECT DISTINCT e.hash
                FROM exam_comentarios_compliance cc
                JOIN exams e ON e.id = cc.exam_id
                WHERE e.hash = ANY(%s)
                  AND cc.tipo = 'examinador_inadequado'
                """,
                (hs,),
            )
            for (h,) in cur.fetchall():
                out.setdefault(h, {})["conduta_inadequada"] = True

            # Laudo de comitê concluído para o exame.
            cur = c.execute(
                """
                SELECT DISTINCT e.hash
                FROM exam_comite_laudos cl
                JOIN exams e ON e.id = cl.exam_id
                WHERE e.hash = ANY(%s)
                """,
                (hs,),
            )
            for (h,) in cur.fetchall():
                out.setdefault(h, {})["comite_concluido"] = True
            return out
    except Exception as e:
        log.exception("db.os_enrichment falhou: %s", e)
        return None


def os_signals(hashes: list[str]) -> dict[str, dict] | None:
    """Sinais de ETAPA da cadeia humana por exam_hash, lidos das tabelas reais da
    OS (ordens_servico / supervisor_decisoes). Read-only e derivado — NÃO altera
    o pipeline nem grava nada. Uma query batelada por exam_hash. None se DB off;
    {} se nenhum hash.

    A fila de /api/os é montada por hash de exame (v_exams_overview), mas os
    sinais de quem já agiu vivem na OS:
      - auditor_email: ordens_servico.auditor_email (setado em save_parecer_auditor
        quando o auditor dá o parecer — a OS passa a 'aguardando_supervisor').
      - supervisor_email: supervisor_decisoes.supervisor_email (a coluna homônima
        em ordens_servico existe mas NÃO é preenchida; a fonte real da decisão é
        supervisor_decisoes — ver save_supervisor_decisao).
      - os_status: ordens_servico.status (estágio bruto da OS, p/ depuração).

    Ausência de hash no dicionário ⇒ sem OS ⇒ o chamador trata como null/sem
    parecer. NUNCA inventa valor: só entram hashes que têm OS no banco.
    """
    if _disabled():
        return None
    hs = [h for h in (hashes or []) if h]
    if not hs:
        return {}
    out: dict[str, dict] = {}
    try:
        with _conn() as c:
            if c is None:
                return None
            # auditor_email + status da OS, por hash do exame (1 OS por exame).
            cur = c.execute(
                """
                SELECT e.hash, os.auditor_email, os.status
                FROM ordens_servico os
                JOIN exams e ON e.id = os.exam_id
                WHERE e.hash = ANY(%s)
                """,
                (hs,),
            )
            for h, auditor_email, status in cur.fetchall():
                d = out.setdefault(h, {})
                if auditor_email:
                    d["auditor_email"] = auditor_email
                if status:
                    d["os_status"] = status

            # Supervisor: fonte real é supervisor_decisoes (a coluna em
            # ordens_servico não é preenchida). Pega a decisão mais recente.
            cur = c.execute(
                """
                SELECT DISTINCT ON (e.hash) e.hash, sd.supervisor_email
                FROM supervisor_decisoes sd
                JOIN ordens_servico os ON os.id = sd.os_id
                JOIN exams e ON e.id = os.exam_id
                WHERE e.hash = ANY(%s)
                ORDER BY e.hash, sd.created_at DESC
                """,
                (hs,),
            )
            for h, supervisor_email in cur.fetchall():
                if supervisor_email:
                    out.setdefault(h, {})["supervisor_email"] = supervisor_email
            return out
    except Exception as e:
        log.exception("db.os_signals falhou: %s", e)
        return None


def count_resultados(
    *,
    dias: int | None = None,
    unidade: str | None = None,
    examinador: str | None = None,
    resultado: str | None = None,
    categoria: str | None = None,
) -> int | None:
    """Total de exames que casam com os filtros (p/ paginar). None se DB off."""
    if _disabled():
        return None
    where: list[str] = []
    vals: list[Any] = []
    if dias:
        where.append("created_at >= NOW() - (%s || ' days')::interval")
        vals.append(str(int(dias)))
    if unidade:
        where.append("local_unidade = %s")
        vals.append(unidade)
    if examinador:
        where.append("examinador = %s")
        vals.append(examinador)
    if resultado:
        where.append("resultado = %s")
        vals.append(resultado)
    if categoria:
        where.append("categoria = %s")
        vals.append(categoria)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    try:
        with _conn() as c:
            if c is None:
                return None
            cur = c.execute(f"SELECT COUNT(*) FROM v_exams_overview {clause}", vals)
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except Exception as e:
        log.exception("db.count_resultados falhou: %s", e)
        return None


def laudo_dossie(exam_hash: str) -> dict | None:
    """Junta tudo que alimenta o PDF do laudo (§14.2): exam + comitê + parecer +
    decisão supervisor + eventos da OS + divergência + eventos brutos +
    enquadramentos + infrações oficiais + compliance + matriz vigente.
    None se DB off ou exame inexistente.

    Resiliente: cada bloco é isolado; ausência de OS/parecer/decisão/divergência
    devolve None/[] nesse bloco sem derrubar o resto. Colunas de `exams` fora da
    view (identificação completa, resultado oficial detalhado) vêm de um SELECT
    direto extra, também best-effort.
    """
    if _disabled():
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            # Exame (overview)
            cur = c.execute("SELECT * FROM v_exams_overview WHERE hash = %s", (exam_hash,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d.name for d in cur.description]
            out: dict = {"exam": dict(zip(cols, row))}

            # Materializa a OS (idempotente) quando o exame está em 'auditoria'
            # (divergência pós-comitê) e ainda não tem ordens_servico — cobre o
            # legado sem materialização, garantindo que o dossiê e a decisão do
            # supervisor tenham uma OS REAL. Mesma conexão (barato). Best-effort:
            # falha aqui jamais derruba o dossiê.
            try:
                if (out["exam"].get("stage") == "auditoria") and out["exam"].get("id"):
                    c.execute(
                        """
                        INSERT INTO ordens_servico
                            (exam_id, tipo_divergencia, status, numero_os)
                        VALUES (%s, 'resultado', 'aguardando_supervisor',
                                'OS-' || upper(substr(%s, 1, 8)))
                        ON CONFLICT (exam_id) DO NOTHING
                        """,
                        (out["exam"]["id"], exam_hash),
                    )
            except Exception as e:
                log.warning("laudo_dossie ensure_os falhou: %s", e)

            # Colunas de `exams` que a view v_exams_overview NÃO expõe mas que o
            # laudo precisa (identificação completa §3, resultado oficial §4,
            # resultado calculado §5, identificação do laudo §1). Best-effort:
            # se alguma coluna não existir no schema do cliente, o bloco inteiro
            # é ignorado sem derrubar o resto.
            try:
                xrow = c.execute(
                    """
                    SELECT processo, rubrica, training_annotations,
                           unidade, tipo_exame,
                           examinador_matricula, examinador_eh_preposto,
                           data_hora_exame,
                           pontuacao_oficial, houve_interrupcao, motivo_interrupcao,
                           resultado_calculado, pontuacao_calculada, matriz_versao,
                           engine_backend, engine_model, engine_preset,
                           cost_usd, cost_tokens_in, cost_tokens_out, gemini_elapsed_s
                    FROM exams WHERE hash = %s
                    """,
                    (exam_hash,),
                ).fetchone()
                if xrow:
                    xcols = [
                        "processo",
                        "rubrica",
                        "training_annotations",
                        "unidade",
                        "tipo_exame",
                        "examinador_matricula",
                        "examinador_eh_preposto",
                        "data_hora_exame",
                        "pontuacao_oficial",
                        "houve_interrupcao",
                        "motivo_interrupcao",
                        "resultado_calculado",
                        "pontuacao_calculada",
                        "matriz_versao",
                        "engine_backend",
                        "engine_model",
                        "engine_preset",
                        "cost_usd",
                        "cost_tokens_in",
                        "cost_tokens_out",
                        "gemini_elapsed_s",
                    ]
                    # Não sobrescreve chaves já vindas da view (ex.: nenhuma
                    # colide hoje, mas mantém a view como fonte preferencial).
                    for k, v in dict(zip(xcols, xrow)).items():
                        out["exam"].setdefault(k, v)
            except Exception as e:
                log.warning("laudo_dossie exam_extra falhou: %s", e)

            # OS mais recente do exame.
            # NOTA schema: ordens_servico não tem exam_hash (usa exam_id), nem as
            # colunas resultado_*/pontuacao_*/sla_due_at/aberta_em. Filtra por
            # exam_id (via hash→exams) e usa as colunas reais. Resultado/pontuação
            # são DERIVADOS de `exams` (já vêm no bloco `exam` acima); o vencimento
            # do SLA é calculado de sla_inicio + sla_prazo_auditor_h.
            os_id = None
            try:
                orow = c.execute(
                    """
                    SELECT os.id::text, os.numero_os, os.tipo_divergencia, os.status,
                           os.criada_em, os.atualizada_em, os.encerrada_em,
                           os.sla_inicio, os.sla_prazo_auditor_h,
                           (os.sla_inicio + (os.sla_prazo_auditor_h || ' hours')::interval) AS sla_due_at,
                           e.resultado, e.resultado_calculado,
                           e.pontuacao_oficial, e.pontuacao_calculada, e.pontuacao_total
                    FROM ordens_servico os
                    LEFT JOIN exams e ON e.id = os.exam_id
                    WHERE os.exam_id = (SELECT id FROM exams WHERE hash = %s)
                    ORDER BY os.criada_em DESC NULLS LAST LIMIT 1
                    """,
                    (exam_hash,),
                ).fetchone()
                if orow:
                    ocols = [
                        "os_id",
                        "numero_os",
                        "tipo_divergencia",
                        "status",
                        "criada_em",
                        "atualizada_em",
                        "encerrada_em",
                        "sla_inicio",
                        "sla_prazo_auditor_h",
                        "sla_due_at",
                        "resultado_oficial",
                        "resultado_calculado",
                        "pontuacao_oficial",
                        "pontuacao_calculada",
                        "pontuacao_total",
                    ]
                    out["ordem_servico"] = dict(zip(ocols, orow))
                    os_id = orow[0]
            except Exception as e:
                log.warning("laudo_dossie ordem_servico falhou: %s", e)

            # Laudo do comitê (por exame ou por OS)
            try:
                crow = c.execute(
                    """
                    SELECT causas_identificadas, verificacoes_executadas,
                           comentarios_examinador,
                           recomendacao_para_auditor, conclusao_comite,
                           resultado_comite, tipo_divergencia_pos_comite, created_at
                    FROM exam_comite_laudos
                    WHERE exam_id = (SELECT id FROM exams WHERE hash = %s)
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (exam_hash,),
                ).fetchone()
                if crow:
                    ccols = [
                        "causas_identificadas",
                        "verificacoes_executadas",
                        "comentarios_examinador",
                        "recomendacao_para_auditor",
                        "conclusao_comite",
                        "resultado_comite",
                        "tipo_divergencia_pos_comite",
                        "created_at",
                    ]
                    out["laudo_comite"] = dict(zip(ccols, crow))
            except Exception as e:
                log.warning("laudo_dossie comite falhou: %s", e)

            # Infrações detectadas
            try:
                icur = c.execute(
                    """
                    SELECT regra_id, gravidade, pontos, descricao, timestamp_s,
                           duracao_s, cameras, confianca, base_legal, status
                    FROM exam_infractions
                    WHERE exam_id = (SELECT id FROM exams WHERE hash = %s)
                    ORDER BY timestamp_s NULLS LAST
                    """,
                    (exam_hash,),
                )
                icols = [d.name for d in icur.description]
                out["infracoes"] = [dict(zip(icols, r)) for r in icur.fetchall()]
            except Exception as e:
                log.warning("laudo_dossie infracoes falhou: %s", e)
                out["infracoes"] = []

            # Parecer do auditor + decisão do supervisor (por OS)
            if os_id:
                try:
                    # auditor_pareceres real: auditor_email, decisao, justificativa,
                    # referencia_mbedv. Sem resultado_final/infracoes/updated_at →
                    # resultado_final DERIVADO de decisao×exams.aprovado.
                    prow = c.execute(
                        """
                        SELECT p.auditor_email, p.decisao, p.justificativa,
                               p.referencia_mbedv, p.created_at, e.aprovado
                        FROM auditor_pareceres p
                        LEFT JOIN ordens_servico os ON os.id = p.os_id
                        LEFT JOIN exams e ON e.id = os.exam_id
                        WHERE p.os_id = %s
                        ORDER BY p.created_at DESC LIMIT 1
                        """,
                        (os_id,),
                    ).fetchone()
                    if prow:
                        auditor_email, decisao_p, justif_p, ref_p, created_p, aprov = prow
                        if aprov is None:
                            resultado_final = None
                        else:
                            concorda = decisao_p == "concorda"
                            final_aprovado = aprov if concorda else (not aprov)
                            resultado_final = "aprovado" if final_aprovado else "reprovado"
                        out["parecer_auditor"] = {
                            "auditor": auditor_email,
                            "decisao": decisao_p,
                            "resultado_final": resultado_final,
                            "justificativa": justif_p,
                            "referencia_mbedv": ref_p,
                            "created_at": created_p,
                        }
                except Exception as e:
                    log.warning("laudo_dossie parecer falhou: %s", e)
                try:
                    srow = c.execute(
                        """
                        SELECT supervisor_email, decisao_final, concorda_auditor,
                               resultado_final, justificativa, created_at
                        FROM supervisor_decisoes WHERE os_id = %s
                        """,
                        (os_id,),
                    ).fetchone()
                    if srow:
                        scols = [
                            "supervisor",
                            "decisao",
                            "concorda_auditor",
                            # Veredito final EXPLÍCITO do supervisor (APROVADO/REPROVADO)
                            # — fonte do veredito publicado no laudo (precede auditor).
                            "resultado_final",
                            "justificativa",
                            "created_at",
                        ]
                        out["decisao_supervisor"] = dict(zip(scols, srow))
                except Exception as e:
                    log.warning("laudo_dossie decisao falhou: %s", e)
                # Eventos da OS (trilha)
                try:
                    ecur = c.execute(
                        """
                        SELECT actor, action, nivel, details, created_at
                        FROM os_eventos WHERE os_id = %s ORDER BY created_at
                        """,
                        (os_id,),
                    )
                    ecols = [d.name for d in ecur.description]
                    out["os_eventos"] = [dict(zip(ecols, r)) for r in ecur.fetchall()]
                except Exception as e:
                    log.warning("laudo_dossie os_eventos falhou: %s", e)
                    out["os_eventos"] = []

            # --- Análise de divergência (§6) — exam_divergencias (1 por exame) --
            try:
                drow = c.execute(
                    """
                    SELECT tipo_divergencia, subtipos_associados,
                           resultado_oficial, resultado_calculado,
                           pontuacao_oficial, pontuacao_calculada,
                           concorda_resultado, concorda_pontuacao, concorda_infracoes,
                           evidencia_suficiente, encaminhamento, detalhes, created_at
                    FROM exam_divergencias
                    WHERE exam_id = (SELECT id FROM exams WHERE hash = %s)
                    """,
                    (exam_hash,),
                ).fetchone()
                if drow:
                    dcols = [
                        "tipo_divergencia",
                        "subtipos_associados",
                        "resultado_oficial",
                        "resultado_calculado",
                        "pontuacao_oficial",
                        "pontuacao_calculada",
                        "concorda_resultado",
                        "concorda_pontuacao",
                        "concorda_infracoes",
                        "evidencia_suficiente",
                        "encaminhamento",
                        "detalhes",
                        "created_at",
                    ]
                    out["divergencia"] = dict(zip(dcols, drow))
            except Exception as e:
                log.warning("laudo_dossie divergencia falhou: %s", e)

            # --- Eventos BRUTOS detectados (§7 sem-enquadramento, §8 timeline) --
            try:
                evcur = c.execute(
                    """
                    SELECT evento_id, categoria, descricao,
                           timestamp_video_seg, timestamp_audio_seg, duracao_seg,
                           confianca, canal_evidencia, quadrante_origem, camera_origem,
                           transcricao, classificacao, contexto
                    FROM exam_eventos
                    WHERE exam_id = (SELECT id FROM exams WHERE hash = %s)
                    ORDER BY timestamp_video_seg NULLS LAST
                    """,
                    (exam_hash,),
                )
                evcols = [d.name for d in evcur.description]
                out["eventos"] = [dict(zip(evcols, r)) for r in evcur.fetchall()]
            except Exception as e:
                log.warning("laudo_dossie eventos falhou: %s", e)
                out["eventos"] = []

            # --- Enquadramentos (evento → regra da Matriz; fundamentação §7) ----
            try:
                enqcur = c.execute(
                    """
                    SELECT evento_id, enquadrado, regra_aplicada, artigo_ctb,
                           ficha_mbedv, natureza, peso, excecao_aplicada,
                           justificativa, confianca, requer_revisao_humana, matriz_versao
                    FROM exam_enquadramentos
                    WHERE exam_id = (SELECT id FROM exams WHERE hash = %s)
                    """,
                    (exam_hash,),
                )
                enqcols = [d.name for d in enqcur.description]
                out["enquadramentos"] = [dict(zip(enqcols, r)) for r in enqcur.fetchall()]
            except Exception as e:
                log.warning("laudo_dossie enquadramentos falhou: %s", e)
                out["enquadramentos"] = []

            # --- Infrações apontadas OFICIALMENTE pela Comissão (§4) ------------
            try:
                iocur = c.execute(
                    """
                    SELECT artigo_ctb, natureza, peso
                    FROM exam_infracoes_oficiais
                    WHERE exam_id = (SELECT id FROM exams WHERE hash = %s)
                    ORDER BY artigo_ctb
                    """,
                    (exam_hash,),
                )
                iocols = [d.name for d in iocur.description]
                out["infracoes_oficiais"] = [dict(zip(iocols, r)) for r in iocur.fetchall()]
            except Exception as e:
                log.warning("laudo_dossie infracoes_oficiais falhou: %s", e)
                out["infracoes_oficiais"] = []

            # --- Compliance (sinais não-pontuáveis: conduta examinador/candidato)
            try:
                cmcur = c.execute(
                    """
                    SELECT tipo, origem_codigo, descricao, timestamp_s,
                           transcricao, classificacao, severidade, status
                    FROM exam_comentarios_compliance
                    WHERE exam_id = (SELECT id FROM exams WHERE hash = %s)
                    ORDER BY timestamp_s NULLS LAST
                    """,
                    (exam_hash,),
                )
                cmcols = [d.name for d in cmcur.description]
                out["compliance"] = [dict(zip(cmcols, r)) for r in cmcur.fetchall()]
            except Exception as e:
                log.warning("laudo_dossie compliance falhou: %s", e)
                out["compliance"] = []

            # --- Extras do laudo do Comitê (§1/§2: versão, tempo, custo) --------
            # O bloco laudo_comite acima usa o schema 013; aqui buscamos as
            # colunas extras do schema 012 (comite_versao/tempo/custo) que só
            # existem quando a migration 012 foi aplicada. Best-effort.
            try:
                cxrow = c.execute(
                    """
                    SELECT comite_versao, tipo_divergencia_analisada,
                           tempo_processamento_seg, cost_usd
                    FROM exam_comite_laudos
                    WHERE exam_id = (SELECT id FROM exams WHERE hash = %s)
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (exam_hash,),
                ).fetchone()
                if cxrow:
                    out["comite_meta"] = {
                        "comite_versao": cxrow[0],
                        "tipo_divergencia_analisada": cxrow[1],
                        "tempo_processamento_seg": cxrow[2],
                        "cost_usd": cxrow[3],
                    }
            except Exception as e:
                log.warning("laudo_dossie comite_meta falhou: %s", e)

            # --- Matriz Nacional vigente (§1: matriz nacional v1.x) -------------
            try:
                mrow = c.execute(
                    """
                    SELECT versao, descricao FROM matriz_versoes
                    WHERE vigente = TRUE
                    ORDER BY created_at DESC LIMIT 1
                    """,
                ).fetchone()
                if mrow:
                    out["matriz_vigente"] = {"versao": mrow[0], "descricao": mrow[1]}
            except Exception as e:
                log.warning("laudo_dossie matriz_vigente falhou: %s", e)

            return out
    except Exception as e:
        log.exception("db.laudo_dossie falhou hash=%s: %s", exam_hash, e)
        return None


# --- 3. Telemetria do Auditor (auditor_telemetria — migration 020) -----------


def insert_telemetria(
    *,
    auditor: str | None,
    exam_hash: str | None,
    assistido_ate_seg: float | None,
    dur_seg: float | None,
    tempo_sessao_s: float | None,
    avancos_bloqueados: int = 0,
) -> bool:
    """Grava uma linha de telemetria de sessão de revisão. False se DB off/falha."""
    if _disabled():
        return False
    try:
        with _conn() as c:
            if c is None:
                return False
            c.execute(
                """
                INSERT INTO auditor_telemetria
                    (auditor, exam_hash, assistido_ate_seg, dur_seg,
                     tempo_sessao_s, avancos_bloqueados)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    auditor,
                    exam_hash,
                    assistido_ate_seg,
                    dur_seg,
                    tempo_sessao_s,
                    int(avancos_bloqueados or 0),
                ),
            )
        return True
    except Exception as e:
        log.exception("db.insert_telemetria falhou: %s", e)
        return False


def auditor_metrics(auditor: str | None = None, dias: int = 30) -> dict | None:
    """Agrega produtividade/qualidade do Auditor. None se DB off.

    Cruza auditor_telemetria (exames assistidos, % assistido médio, avanços
    bloqueados) com auditor_pareceres (resultados aprovado/reprovado, %
    concordância auditor×IA). `auditor` filtra um auditor; sem ele agrega todos.
    """
    if _disabled():
        return None
    janela = str(int(dias))
    out: dict = {
        "periodo_dias": int(dias),
        "filtro_auditor": auditor,
        "por_auditor": [],
        "serie_diaria": [],
        "totais": {
            "exames_assistidos": 0,
            "pct_assistido_medio": 0.0,
            "avancos_bloqueados": 0,
            "pareceres": 0,
            "aprovados": 0,
            "reprovados": 0,
            "concordancia_ia_pct": 0.0,
        },
    }
    filtro = ""
    extra: list[Any] = []
    if auditor:
        filtro = " AND auditor = %s"
        extra = [auditor]
    try:
        with _conn() as c:
            if c is None:
                return None
            # Telemetria por auditor
            cur = c.execute(
                f"""
                SELECT COALESCE(NULLIF(auditor,''),'(sem auditor)') AS auditor,
                       COUNT(DISTINCT exam_hash)                    AS exames_assistidos,
                       COALESCE(AVG(
                         CASE WHEN dur_seg > 0
                              THEN 100.0 * assistido_ate_seg / dur_seg END), 0) AS pct_assistido_medio,
                       COALESCE(SUM(avancos_bloqueados), 0)         AS avancos_bloqueados,
                       COALESCE(AVG(tempo_sessao_s), 0)             AS tempo_sessao_medio_s
                FROM auditor_telemetria
                WHERE created_at >= NOW() - (%s || ' days')::interval{filtro}
                GROUP BY 1 ORDER BY exames_assistidos DESC
                """,
                [janela, *extra],
            )
            tele = {
                r[0]: {
                    "auditor": r[0],
                    "exames_assistidos": int(r[1] or 0),
                    "pct_assistido_medio": round(float(r[2] or 0), 1),
                    "avancos_bloqueados": int(r[3] or 0),
                    "tempo_sessao_medio_s": round(float(r[4] or 0), 1),
                }
                for r in cur.fetchall()
            }

            # Pareceres por auditor (resultados + concordância IA)
            pfiltro = ""
            pextra: list[Any] = []
            if auditor:
                pfiltro = " AND p.auditor_email = %s"
                pextra = [auditor]
            # resultado_final não existe em auditor_pareceres → derivado: a decisão
            # 'concorda' mantém o resultado da IA (exams.aprovado); 'discorda' inverte.
            pcur = c.execute(
                f"""
                SELECT COALESCE(NULLIF(p.auditor_email,''),'(sem auditor)') AS auditor,
                       COUNT(*)                                      AS pareceres,
                       COUNT(*) FILTER (WHERE
                           (p.decisao = 'concorda' AND e.aprovado IS TRUE)
                        OR (p.decisao = 'discorda' AND e.aprovado IS FALSE)) AS aprovados,
                       COUNT(*) FILTER (WHERE
                           (p.decisao = 'concorda' AND e.aprovado IS FALSE)
                        OR (p.decisao = 'discorda' AND e.aprovado IS TRUE))  AS reprovados,
                       COALESCE(100.0 * COUNT(*) FILTER (WHERE p.decisao = 'concorda')
                                / NULLIF(COUNT(*), 0), 0)            AS concordancia_ia_pct
                FROM auditor_pareceres p
                JOIN ordens_servico os ON os.id = p.os_id
                LEFT JOIN exams e ON e.id = os.exam_id
                WHERE p.created_at >= NOW() - (%s || ' days')::interval{pfiltro}
                GROUP BY 1
                """,
                [janela, *pextra],
            )
            par = {
                r[0]: {
                    "pareceres": int(r[1] or 0),
                    "aprovados": int(r[2] or 0),
                    "reprovados": int(r[3] or 0),
                    "concordancia_ia_pct": round(float(r[4] or 0), 1),
                }
                for r in pcur.fetchall()
            }

            # Merge telemetria + pareceres por auditor
            todos = set(tele) | set(par)
            linhas = []
            for a in todos:
                base = tele.get(
                    a,
                    {
                        "auditor": a,
                        "exames_assistidos": 0,
                        "pct_assistido_medio": 0.0,
                        "avancos_bloqueados": 0,
                        "tempo_sessao_medio_s": 0.0,
                    },
                )
                base.update(
                    par.get(
                        a,
                        {
                            "pareceres": 0,
                            "aprovados": 0,
                            "reprovados": 0,
                            "concordancia_ia_pct": 0.0,
                        },
                    )
                )
                linhas.append(base)
            linhas.sort(key=lambda x: x.get("exames_assistidos", 0), reverse=True)
            out["por_auditor"] = linhas

            # Totais
            t = out["totais"]
            t["exames_assistidos"] = sum(l["exames_assistidos"] for l in linhas)
            t["avancos_bloqueados"] = sum(l["avancos_bloqueados"] for l in linhas)
            t["pareceres"] = sum(l["pareceres"] for l in linhas)
            t["aprovados"] = sum(l["aprovados"] for l in linhas)
            t["reprovados"] = sum(l["reprovados"] for l in linhas)
            if linhas:
                pcts = [l["pct_assistido_medio"] for l in linhas if l["exames_assistidos"]]
                t["pct_assistido_medio"] = round(sum(pcts) / len(pcts), 1) if pcts else 0.0
            # concordância global = concorda / pareceres (recalcula via SQL p/ exatidão)
            grow = c.execute(
                f"""
                SELECT COALESCE(100.0 * COUNT(*) FILTER (WHERE p.decisao='concorda')
                       / NULLIF(COUNT(*),0), 0)
                FROM auditor_pareceres p
                WHERE p.created_at >= NOW() - (%s || ' days')::interval{pfiltro}
                """,
                [janela, *pextra],
            ).fetchone()
            t["concordancia_ia_pct"] = round(float(grow[0] or 0), 1) if grow else 0.0

            # Série diária (exames assistidos por dia)
            scur = c.execute(
                f"""
                SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS dia,
                       COUNT(DISTINCT exam_hash) AS exames,
                       COALESCE(AVG(CASE WHEN dur_seg > 0
                            THEN 100.0 * assistido_ate_seg / dur_seg END), 0) AS pct_assistido
                FROM auditor_telemetria
                WHERE created_at >= NOW() - (%s || ' days')::interval{filtro}
                GROUP BY 1 ORDER BY 1
                """,
                [janela, *extra],
            )
            out["serie_diaria"] = [
                {
                    "dia": r[0],
                    "exames_assistidos": int(r[1] or 0),
                    "pct_assistido_medio": round(float(r[2] or 0), 1),
                }
                for r in scur.fetchall()
            ]
        return out
    except Exception as e:
        log.exception("db.auditor_metrics falhou: %s", e)
        return out


# --- 4. Cron / Batch (cron_jobs + cron_job_runs — migration 021) -------------

_CRON_JOB_COLS = (
    "id",
    "nome",
    "enabled",
    "schedule_kind",
    "horario",
    "cron_expr",
    "batch_limit",
    "retry",
    "escopo",
    "categoria",
    "created_at",
    "updated_at",
)
_CRON_JOB_SELECT = (
    "id::text, nome, enabled, schedule_kind, horario, cron_expr, "
    "batch_limit, retry, escopo, categoria, created_at, updated_at"
)


def list_cron_jobs() -> list[dict] | None:
    """Lista os agendamentos. None se DB off; [] se vazio."""
    if _disabled():
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            cur = c.execute(f"SELECT {_CRON_JOB_SELECT} FROM cron_jobs ORDER BY created_at DESC")
            return [dict(zip(_CRON_JOB_COLS, row)) for row in cur.fetchall()]
    except Exception as e:
        log.exception("db.list_cron_jobs falhou: %s", e)
        return None


def get_cron_job(job_id: str) -> dict | None:
    """Um agendamento por id. None se DB off ou inexistente."""
    if _disabled():
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            row = c.execute(
                f"SELECT {_CRON_JOB_SELECT} FROM cron_jobs WHERE id = %s", (job_id,)
            ).fetchone()
            return dict(zip(_CRON_JOB_COLS, row)) if row else None
    except Exception as e:
        log.exception("db.get_cron_job falhou id=%s: %s", job_id, e)
        return None


def create_cron_job(
    *,
    nome: str,
    enabled: bool = True,
    schedule_kind: str = "daily",
    horario: str | None = None,
    cron_expr: str | None = None,
    batch_limit: int = 50,
    retry: int = 0,
    escopo: str = "pending",
    categoria: str | None = None,
) -> dict | None:
    """Cria um agendamento. None se DB off.

    `categoria` (opcional): filtro de categoria CNH (ACC/A/B/C/D/E). None/vazio
    => processa todas as categorias no batch.
    """
    if _disabled():
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            row = c.execute(
                f"""
                INSERT INTO cron_jobs
                    (nome, enabled, schedule_kind, horario, cron_expr,
                     batch_limit, retry, escopo, categoria)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {_CRON_JOB_SELECT}
                """,
                (
                    nome,
                    enabled,
                    schedule_kind,
                    horario,
                    cron_expr,
                    int(batch_limit),
                    int(retry),
                    escopo,
                    (categoria or None),
                ),
            ).fetchone()
            return dict(zip(_CRON_JOB_COLS, row)) if row else None
    except Exception as e:
        log.exception("db.create_cron_job falhou: %s", e)
        return None


def update_cron_job(job_id: str, fields: dict) -> dict | None:
    """Atualiza campos de um agendamento. None se DB off, sem campos ou inexistente."""
    if _disabled():
        return None
    allowed = {
        "nome",
        "enabled",
        "schedule_kind",
        "horario",
        "cron_expr",
        "batch_limit",
        "retry",
        "escopo",
        "categoria",
    }
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return None
    cols = ", ".join(f"{k} = %s" for k in sets)
    vals = list(sets.values()) + [job_id]
    try:
        with _conn() as c:
            if c is None:
                return None
            row = c.execute(
                f"""
                UPDATE cron_jobs SET {cols}, updated_at = NOW()
                WHERE id = %s
                RETURNING {_CRON_JOB_SELECT}
                """,
                vals,
            ).fetchone()
            return dict(zip(_CRON_JOB_COLS, row)) if row else None
    except Exception as e:
        log.exception("db.update_cron_job falhou id=%s: %s", job_id, e)
        return None


def delete_cron_job(job_id: str) -> bool:
    """Remove um agendamento (cascateia os runs). False se DB off/inexistente."""
    if _disabled():
        return False
    try:
        with _conn() as c:
            if c is None:
                return False
            row = c.execute(
                "DELETE FROM cron_jobs WHERE id = %s RETURNING id", (job_id,)
            ).fetchone()
            return bool(row)
    except Exception as e:
        log.exception("db.delete_cron_job falhou id=%s: %s", job_id, e)
        return False


def start_cron_run(job_id: str | None) -> str | None:
    """Abre um cron_job_runs (status=running). Devolve o id (BIGSERIAL como str).

    None se DB off. job_id pode ser None p/ um disparo avulso (sem agendamento).
    """
    if _disabled():
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            row = c.execute(
                """
                INSERT INTO cron_job_runs (cron_job_id, status)
                VALUES (%s, 'running')
                RETURNING id::text
                """,
                (job_id,),
            ).fetchone()
            return row[0] if row else None
    except Exception as e:
        log.exception("db.start_cron_run falhou job=%s: %s", job_id, e)
        return None


def finish_cron_run(
    run_id: str | None,
    *,
    n_processados: int = 0,
    n_falhas: int = 0,
    custo_usd: float = 0.0,
    status: str = "success",
) -> bool:
    """Fecha um cron_job_runs com os totais. False se DB off ou run inexistente."""
    if _disabled() or not run_id:
        return False
    try:
        with _conn() as c:
            if c is None:
                return False
            row = c.execute(
                """
                UPDATE cron_job_runs SET
                    finalizado_em = NOW(),
                    n_processados = %s,
                    n_falhas      = %s,
                    custo_usd     = %s,
                    status        = %s
                WHERE id = %s
                RETURNING id
                """,
                (int(n_processados), int(n_falhas), float(custo_usd or 0), status, run_id),
            ).fetchone()
            return bool(row)
    except Exception as e:
        log.exception("db.finish_cron_run falhou id=%s: %s", run_id, e)
        return False


def list_cron_runs(job_id: str | None = None, limit: int = 50) -> list[dict] | None:
    """Histórico de execuções (todas, ou de um job). None se DB off; [] se vazio."""
    if _disabled():
        return None
    where = ""
    vals: list[Any] = []
    if job_id:
        where = "WHERE cron_job_id = %s"
        vals.append(job_id)
    vals.append(int(limit))
    try:
        with _conn() as c:
            if c is None:
                return None
            cur = c.execute(
                f"""
                SELECT id::text, cron_job_id::text, iniciado_em, finalizado_em,
                       n_processados, n_falhas, custo_usd, status
                FROM cron_job_runs {where}
                ORDER BY iniciado_em DESC LIMIT %s
                """,
                vals,
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        log.exception("db.list_cron_runs falhou: %s", e)
        return None


# --- 5. Supervisor — decisão final sobre a OS (supervisor_decisoes — 017) ----


def _canon_resultado(v) -> str | None:
    """Normaliza o veredito do supervisor → 'APROVADO' | 'REPROVADO' | None.

    Valores canônicos gravados na coluna supervisor_decisoes.resultado_final
    (a coluna é VARCHAR(16); 'APROVADO'/'REPROVADO' cabem). Aceita 'A'/'R',
    'aprovado'/'reprovado' (com/sem caixa/acento) e bool. Desconhecido → None
    (linha fica com NULL — o laudo cai no fallback de derivação legado).
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return "APROVADO" if v else "REPROVADO"
    s = str(v).strip().lower()
    if not s:
        return None
    if s == "a" or s.startswith("aprov"):
        return "APROVADO"
    if s == "r" or s.startswith("reprov") or s.startswith("repr"):
        return "REPROVADO"
    return None


def save_supervisor_decisao(
    os_id: str,
    *,
    supervisor: str | None,
    decisao: str,
    resultado_final: str | None,
    justificativa: str | None,
    homologar_conduta: bool = False,
) -> dict | None:
    """Grava a decisão do Supervisor (upsert UNIQUE os_id) + encerra a OS + audita.

    `decisao`: 'homologar' (mantém parecer auditor) | 'reformar' (sobrepõe).
    Move a OS p/ status 'decisao_final' e seta encerrada_em. None se DB off ou
    OS inexistente (server responde eco do mock).
    """
    if _disabled():
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            # Não há coluna exam_hash em ordens_servico → usa exam_id e busca o
            # hash via JOIN em exams (necessário p/ log_event por exame).
            erow = c.execute(
                """
                SELECT os.status, e.hash
                FROM ordens_servico os
                LEFT JOIN exams e ON e.id = os.exam_id
                WHERE os.id = %s
                """,
                (os_id,),
            ).fetchone()
            if not erow:
                return None
            de_status, exam_hash = erow
            # concorda_auditor (NOT NULL) é DERIVADO: 'homologar' mantém o parecer
            # do auditor (concorda=True); 'reformar' sobrepõe (concorda=False).
            # Sem parecer do auditor → False (default decidido).
            prow = c.execute(
                "SELECT decisao FROM auditor_pareceres WHERE os_id = %s ORDER BY created_at DESC LIMIT 1",
                (os_id,),
            ).fetchone()
            tem_parecer = prow is not None
            concorda_auditor = bool(tem_parecer and decisao == "homologar")
            # Veredito final EXPLÍCITO do supervisor (A/R) → coluna resultado_final
            # (canônico APROVADO/REPROVADO). É a FONTE do veredito publicado no laudo
            # — sem isso o laudo derivava por inversão binária do auditor (frágil).
            resultado_final_canon = _canon_resultado(resultado_final)
            # supervisor_decisoes NÃO tem UNIQUE(os_id) no schema de prod (só PK em
            # id) → ON CONFLICT(os_id) é inválido. Upsert manual: apaga a decisão
            # anterior da OS e insere a nova. justificativa é NOT NULL → ''.
            c.execute("DELETE FROM supervisor_decisoes WHERE os_id = %s", (os_id,))
            srow = c.execute(
                """
                INSERT INTO supervisor_decisoes
                    (os_id, supervisor_email, decisao_final, concorda_auditor,
                     resultado_final, justificativa, homologar_conduta)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id::text, created_at
                """,
                (
                    os_id,
                    supervisor,
                    decisao,
                    concorda_auditor,
                    resultado_final_canon,
                    justificativa or "",
                    bool(homologar_conduta),
                ),
            ).fetchone()
            # Encerra a OS
            c.execute(
                """
                UPDATE ordens_servico
                SET status = 'decisao_final', encerrada_em = NOW(), atualizada_em = NOW()
                WHERE id = %s
                """,
                (os_id,),
            )
            # Audita em os_eventos (de/para_status não são colunas → vão no details jsonb)
            import json as _json

            c.execute(
                """
                INSERT INTO os_eventos (os_id, actor, action, nivel, details)
                VALUES (%s, %s, 'decisao_supervisor', 'info', %s::jsonb)
                """,
                (
                    os_id,
                    supervisor,
                    _json.dumps(
                        {
                            "de_status": de_status,
                            "para_status": "decisao_final",
                            "decisao": decisao,
                            "resultado_final": resultado_final,
                            "concorda_auditor": concorda_auditor,
                        }
                    ),
                ),
            )
            if exam_hash:
                log_event(c, exam_hash, "decisao_supervisor", {"os_id": os_id, "decisao": decisao})
            return {
                "id": srow[0],
                "os_id": os_id,
                "supervisor": supervisor,
                "decisao": decisao,
                "resultado_final": resultado_final_canon,
                "concorda_auditor": concorda_auditor,
                "homologar_conduta": bool(homologar_conduta),
                "justificativa": justificativa,
                "created_at": srow[1],
                "status_os": "decisao_final",
            }
    except Exception as e:
        log.exception("db.save_supervisor_decisao falhou os=%s: %s", os_id, e)
        return None


def os_ja_encerrada(os_id: str) -> bool:
    """True se a OS já está encerrada (encerrada_em IS NOT NULL).

    Guard do POST /api/os/{id}/decisao: uma OS encerrada teve seu laudo oficial
    publicado e NÃO pode ser re-encerrada/sobrescrita silenciosamente (sem flag de
    reabertura). DB off, OS inexistente ou erro → False (não bloqueia o eco-mock /
    a materialização normal). Nunca lança.
    """
    if _disabled() or not os_id:
        return False
    try:
        with _conn() as c:
            if c is None:
                return False
            row = c.execute(
                "SELECT encerrada_em FROM ordens_servico WHERE id = %s",
                (os_id,),
            ).fetchone()
            return bool(row and row[0] is not None)
    except Exception as e:
        log.warning("db.os_ja_encerrada falhou os=%s: %s", os_id, e)
        return False


def get_supervisor_decisao(os_id: str) -> dict | None:
    """Recupera a decisão do supervisor de uma OS. None se DB off ou inexistente."""
    if _disabled():
        return None
    try:
        with _conn() as c:
            if c is None:
                return None
            row = c.execute(
                """
                SELECT id::text, os_id::text, supervisor_email, decisao_final,
                       concorda_auditor, resultado_final, homologar_conduta,
                       justificativa, created_at
                FROM supervisor_decisoes WHERE os_id = %s
                """,
                (os_id,),
            ).fetchone()
            if not row:
                return None
            cols = [
                "id",
                "os_id",
                "supervisor",
                "decisao",
                "concorda_auditor",
                "resultado_final",
                "homologar_conduta",
                "justificativa",
                "created_at",
            ]
            return dict(zip(cols, row))
    except Exception as e:
        log.exception("db.get_supervisor_decisao falhou os=%s: %s", os_id, e)
        return None


def supervisor_concordancia(dias: int = 30) -> dict | None:
    """Concordância Supervisor×Auditor e Supervisor×IA na janela. None se DB off.

    - supervisor×auditor: % de decisões 'homologar' (mantém o parecer do auditor).
    - supervisor×ia: cruza decisao do supervisor com a decisao do parecer (que já
      é concorda/discorda da IA) — % em que o resultado final do supervisor
      coincide com o resultado_final do auditor.
    """
    if _disabled():
        return None
    janela = str(int(dias))
    out = {
        "periodo_dias": int(dias),
        "total_decisoes": 0,
        "homologadas": 0,
        "reformadas": 0,
        "concordancia_supervisor_auditor_pct": 0.0,
        "concordancia_supervisor_ia_pct": 0.0,
    }
    try:
        with _conn() as c:
            if c is None:
                return None
            row = c.execute(
                """
                SELECT COUNT(*)                                              AS total,
                       COUNT(*) FILTER (WHERE s.decisao_final = 'homologar')  AS homol,
                       COUNT(*) FILTER (WHERE s.decisao_final = 'reformar')   AS reform,
                       COALESCE(100.0 * COUNT(*) FILTER (WHERE s.concorda_auditor IS TRUE)
                                / NULLIF(COUNT(*), 0), 0)                    AS conc_auditor,
                       COALESCE(100.0 * COUNT(*) FILTER (
                                WHERE p.decisao = 'concorda' AND s.concorda_auditor IS TRUE)
                                / NULLIF(COUNT(*), 0), 0)                    AS conc_ia
                FROM supervisor_decisoes s
                LEFT JOIN auditor_pareceres p ON p.os_id = s.os_id
                WHERE s.created_at >= NOW() - (%s || ' days')::interval
                """,
                (janela,),
            ).fetchone()
            if row:
                out["total_decisoes"] = int(row[0] or 0)
                out["homologadas"] = int(row[1] or 0)
                out["reformadas"] = int(row[2] or 0)
                out["concordancia_supervisor_auditor_pct"] = round(float(row[3] or 0), 1)
                out["concordancia_supervisor_ia_pct"] = round(float(row[4] or 0), 1)
        return out
    except Exception as e:
        log.exception("db.supervisor_concordancia falhou: %s", e)
        return out


# dia-da-semana (0=domingo no to_char 'D' do Postgres) → label PT-BR curto.
_DOW_LABEL_PT = {1: "Dom", 2: "Seg", 3: "Ter", 4: "Qua", 5: "Qui", 6: "Sex", 7: "Sáb"}

# gravidade (exam_infractions) → bucket de severidade da UI + cor.
# leve→Baixo, media→Médio, grave→Alto, gravissima/eliminatoria/etica→Crítico.
_SEV_BUCKET = {
    "leve": "Baixo",
    "media": "Médio",
    "grave": "Alto",
    "gravissima": "Crítico",
    "eliminatoria": "Crítico",
    "etica": "Crítico",
}
_SEV_COLOR = {"Crítico": "#EF4444", "Alto": "#F97316", "Médio": "#F59E0B", "Baixo": "#10B981"}
_SEV_ORDER = ("Crítico", "Alto", "Médio", "Baixo")
# pontuação → severidade do caso prioritário (sem infração detalhada por OS).
_SEV_BY_PONTOS = lambda p: (
    "Crítico" if p >= 20 else "Alto" if p >= 10 else "Médio" if p >= 5 else "Baixo"
)  # noqa: E731


def _fmt_sla(due_at: Any) -> str:
    """Formata o tempo restante até o SLA como 'HH:MMh'. Vencido → 'vencido'.

    Aceita datetime (TIMESTAMPTZ) ou None. None/erro → '—'.
    """
    if due_at is None:
        return "—"
    try:
        from datetime import datetime

        now = datetime.now(UTC)
        delta = (due_at - now).total_seconds()
        if delta <= 0:
            return "vencido"
        h = int(delta // 3600)
        m = int((delta % 3600) // 60)
        return f"{h:02d}:{m:02d}h"
    except Exception:
        return "—"


def dashboard_kpis() -> dict | None:
    """KPIs reais do Painel executivo (tela Dashboard). None se DB off.

    Blocos (cada um isolado em sub-try, recorte vazio = neutro):
      weekly         — últimos 7 dias de `exams` por dia da semana
                       (recebidos=count, processados=status='processed',
                        indicio=exames com divergência registrada em exam_divergencias).
      severity       — distribuição das infrações (exam_infractions.gravidade)
                       nos buckets Crítico/Alto/Médio/Baixo da UI (janela 30d).
      units          — top unidades por volume (exams.local_unidade, janela 30d).
      priority_cases — OS abertas (ordens_servico, status != encerrada/decisao_final)
                       ordenadas por SLA mais próximo.
      totals         — recebidos_hoje, processados, indicio (hoje), criticos
                       (OS abertas com SLA vencido), tempo_medio (gemini_elapsed_s
                        médio 30d), sla (% OS no prazo).
      insights       — 1-3 derivados (unidade líder de volume, taxa de divergência).

    Resiliente: qualquer falha global → retorna a estrutura zerada (nunca levanta).
    """
    zero: dict = {
        "weekly": [],
        "severity": [],
        "units": [],
        "priority_cases": [],
        "totals": {
            "recebidos_hoje": 0,
            "recebidos_sub": "—",
            "processados": 0,
            "processados_sub": "—",
            "indicio": 0,
            "indicio_sub": "—",
            "criticos": 0,
            "criticos_sub": "—",
            "tempo_medio": "—",
            "tempo_medio_sub": "—",
            "sla": "—",
            "sla_sub": "—",
        },
        "insights": [],
    }
    if _disabled():
        return None
    out: dict = {
        "weekly": [],
        "severity": [],
        "units": [],
        "priority_cases": [],
        "totals": dict(zero["totals"]),
        "insights": [],
    }
    try:
        with _conn() as c:
            if c is None:
                return None

            # --- weekly: últimos 7 dias por dia da semana --------------------
            try:
                cur = c.execute(
                    """
                    SELECT EXTRACT(DOW FROM e.created_at)::int + 1            AS dow,
                           to_char(date_trunc('day', e.created_at),'YYYY-MM-DD') AS dia,
                           COUNT(*)                                           AS recebidos,
                           COUNT(*) FILTER (WHERE e.status = 'processed')     AS processados,
                           COUNT(*) FILTER (WHERE d.exam_id IS NOT NULL)      AS indicio
                    FROM exams e
                    LEFT JOIN exam_divergencias d ON d.exam_id = e.id
                    WHERE e.created_at >= date_trunc('day', NOW()) - INTERVAL '6 days'
                    GROUP BY 1, 2
                    ORDER BY 2
                    """
                )
                out["weekly"] = [
                    {
                        "name": _DOW_LABEL_PT.get(int(r[0]), "?"),
                        "recebidos": int(r[2] or 0),
                        "processados": int(r[3] or 0),
                        "indicio": int(r[4] or 0),
                    }
                    for r in cur.fetchall()
                ]
            except Exception as e:
                log.warning("dashboard_kpis weekly falhou: %s", e)

            # --- severity: infrações por bucket (janela 30d) -----------------
            try:
                cur = c.execute(
                    """
                    SELECT LOWER(i.gravidade) AS grav, COUNT(*) AS n
                    FROM exam_infractions i
                    JOIN exams e ON e.id = i.exam_id
                    WHERE e.created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY 1
                    """
                )
                buckets: dict[str, int] = {b: 0 for b in _SEV_ORDER}
                for grav, n in cur.fetchall():
                    bucket = _SEV_BUCKET.get((grav or "").strip(), "Baixo")
                    buckets[bucket] += int(n or 0)
                out["severity"] = [
                    {"name": b, "value": buckets[b], "color": _SEV_COLOR[b]} for b in _SEV_ORDER
                ]
            except Exception as e:
                log.warning("dashboard_kpis severity falhou: %s", e)

            # --- units: top unidades por volume (janela 30d) -----------------
            try:
                cur = c.execute(
                    """
                    SELECT COALESCE(NULLIF(local_unidade,''),'N/D') AS unidade, COUNT(*) AS n
                    FROM exams
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY 1 ORDER BY n DESC LIMIT 6
                    """
                )
                out["units"] = [{"name": r[0], "value": int(r[1] or 0)} for r in cur.fetchall()]
            except Exception as e:
                log.warning("dashboard_kpis units falhou: %s", e)

            # --- priority_cases: OS abertas por SLA --------------------------
            try:
                # ordens_servico não tem exam_hash/pontuacao_calculada/sla_due_at.
                # hash/pontuação DERIVAM de exams; vencimento de sla_inicio + prazo.
                cur = c.execute(
                    """
                    SELECT os.numero_os, e.hash,
                           e.candidato_nome, e.local_unidade,
                           COALESCE(e.pontuacao_calculada, e.pontuacao_total, 0) AS pontos,
                           (os.sla_inicio + (os.sla_prazo_auditor_h || ' hours')::interval) AS sla_due_at
                    FROM ordens_servico os
                    LEFT JOIN exams e ON e.id = os.exam_id
                    WHERE os.status NOT IN ('encerrada','decisao_final')
                    ORDER BY sla_due_at ASC NULLS LAST, os.criada_em ASC
                    LIMIT 5
                    """
                )
                rows = cur.fetchall()
                cases = []
                for r in rows:
                    pontos = int(r[4] or 0)
                    sev = _SEV_BY_PONTOS(pontos)
                    cases.append(
                        {
                            "id": r[0] or (r[1][:12] if r[1] else "OS-?"),
                            "name": r[2] or "—",
                            "unit": r[3] or "N/D",
                            "score": pontos,
                            "sev": sev,
                            "sla": _fmt_sla(r[5]),
                        }
                    )
                out["priority_cases"] = cases
            except Exception as e:
                log.warning("dashboard_kpis priority_cases falhou: %s", e)

            # --- totals ------------------------------------------------------
            try:
                row = c.execute(
                    """
                    SELECT
                      COUNT(*) FILTER (WHERE e.created_at >= date_trunc('day', NOW()))                       AS rec_hoje,
                      COUNT(*) FILTER (WHERE e.created_at >= date_trunc('day', NOW()) - INTERVAL '1 day'
                                         AND e.created_at <  date_trunc('day', NOW()))                        AS rec_ontem,
                      COUNT(*) FILTER (WHERE e.status = 'processed'
                                         AND e.created_at >= date_trunc('day', NOW()))                        AS proc_hoje,
                      COUNT(*) FILTER (WHERE d.exam_id IS NOT NULL
                                         AND e.created_at >= date_trunc('day', NOW()))                        AS indicio_hoje
                    FROM exams e
                    LEFT JOIN exam_divergencias d ON d.exam_id = e.id
                    """
                ).fetchone()
                rec_hoje = int(row[0] or 0)
                rec_ontem = int(row[1] or 0)
                proc_hoje = int(row[2] or 0)
                indicio_hoje = int(row[3] or 0)
                t = out["totals"]
                t["recebidos_hoje"] = rec_hoje
                if rec_ontem > 0:
                    delta = round(100.0 * (rec_hoje - rec_ontem) / rec_ontem)
                    t["recebidos_sub"] = f"{'+' if delta >= 0 else ''}{delta}% vs ontem"
                else:
                    t["recebidos_sub"] = "sem base ontem"
                t["processados"] = proc_hoje
                t["processados_sub"] = (
                    f"{round(100.0 * proc_hoje / rec_hoje)}% do volume" if rec_hoje else "—"
                )
                t["indicio"] = indicio_hoje
                t["indicio_sub"] = (
                    f"{round(100.0 * indicio_hoje / rec_hoje, 1)}% dos casos" if rec_hoje else "—"
                )
            except Exception as e:
                log.warning("dashboard_kpis totals(exames) falhou: %s", e)

            # criticos = OS abertas com SLA vencido; sla = % OS abertas no prazo.
            try:
                # sla_due_at não existe → vencimento derivado de sla_inicio + prazo.
                row = c.execute(
                    """
                    SELECT
                      COUNT(*)                                                          AS abertas,
                      COUNT(*) FILTER (
                        WHERE sla_inicio IS NOT NULL
                          AND sla_inicio + (sla_prazo_auditor_h || ' hours')::interval < NOW()
                      )                                                                 AS vencidas
                    FROM ordens_servico
                    WHERE status NOT IN ('encerrada','decisao_final')
                    """
                ).fetchone()
                abertas = int(row[0] or 0)
                vencidas = int(row[1] or 0)
                t = out["totals"]
                t["criticos"] = vencidas
                t["criticos_sub"] = "SLA ameaçado" if vencidas else "nenhum vencido"
                if abertas:
                    no_prazo = round(100.0 * (abertas - vencidas) / abertas, 1)
                    t["sla"] = f"{no_prazo}%"
                    t["sla_sub"] = "meta 90%"
                else:
                    t["sla"] = "100%"
                    t["sla_sub"] = "sem OS abertas"
            except Exception as e:
                log.warning("dashboard_kpis totals(os) falhou: %s", e)

            # tempo_medio = média de gemini_elapsed_s nos processados (30d).
            try:
                row = c.execute(
                    """
                    SELECT COALESCE(AVG(gemini_elapsed_s), 0)
                    FROM exams
                    WHERE gemini_elapsed_s IS NOT NULL
                      AND created_at >= NOW() - INTERVAL '30 days'
                    """
                ).fetchone()
                secs = float(row[0] or 0)
                if secs > 0:
                    m = int(secs // 60)
                    s = int(secs % 60)
                    out["totals"]["tempo_medio"] = f"{m}m {s:02d}s" if m else f"{s}s"
                    out["totals"]["tempo_medio_sub"] = "média 30d"
            except Exception as e:
                log.warning("dashboard_kpis tempo_medio falhou: %s", e)

            # --- insights derivados ------------------------------------------
            try:
                insights: list[dict] = []
                units = out.get("units") or []
                if units and units[0]["value"] > 0:
                    top = units[0]
                    insights.append(
                        {
                            "title": "Unidade com maior volume",
                            "text": f"<b>{top['name']}</b> lidera com <b>{top['value']} exames</b> nos últimos 30 dias.",
                            "color": "#06B6D4",
                            "icon": "trending",
                        }
                    )
                t = out["totals"]
                if t.get("recebidos_hoje"):
                    insights.append(
                        {
                            "title": "Taxa de divergência hoje",
                            "text": f"<b>{t['indicio']}</b> de <b>{t['recebidos_hoje']}</b> exames com indício ({t.get('indicio_sub', '')}).",
                            "color": "#F59E0B" if t["indicio"] else "#10B981",
                            "icon": "alert-circle",
                        }
                    )
                if t.get("criticos"):
                    insights.append(
                        {
                            "title": "OS com SLA vencido",
                            "text": f"<b>{t['criticos']}</b> ordens de serviço passaram do prazo — priorizar atendimento.",
                            "color": "#EF4444",
                            "icon": "alert-triangle",
                        }
                    )
                out["insights"] = insights[:3]
            except Exception as e:
                log.warning("dashboard_kpis insights falhou: %s", e)

        return out
    except Exception as e:
        log.exception("db.dashboard_kpis falhou: %s", e)
        return zero
