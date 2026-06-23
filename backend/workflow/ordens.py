"""Ordens de Serviço + fluxo humano de 4 níveis (spec §11-§12).

Regra de negócio (definida pelo produto):

  • CADA VÍDEO É UMA ORDEM DE SERVIÇO. A OS é aberta já no ``init_upload`` —
    não só quando há divergência.
  • O NÚMERO DA OS é o ID gerado no ``init_upload`` (``numero_os``).
  • O SLA COMEÇA A CONTAR no ``init_upload`` (``sla_inicio``), não quando a
    divergência aparece.

Ciclo: a OS nasce ``criada`` no upload; a análise da IA + Comitê a ATUALIZAM —
sem divergência ela é ``encerrada`` (arquivada sem humano); com divergência vai
para ``aguardando_auditor`` e percorre Auditor → Supervisor (sem atalho; o
supervisor analisa TODA divergência — spec §11).

A trilha ``os_eventos`` é append-only. Persistência best-effort (no-op sem DB).
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import settings
from backend.core.db import (
    db_enabled,
    exam_id_from_hash,
    execute,
    fetch_all,
    fetch_one,
    to_jsonb,
)
from backend.models import Encaminhamento

log = logging.getLogger("valbot.os")

# Prioridade da OS por tipo de divergência (1 = mais urgente — spec §12).
_PRIORIDADE_POR_DIVERGENCIA: dict[str, int] = {
    "1_resultado": 1,
    "2_pontuacao": 2,
    "5_evidencia_insuficiente": 2,
    "3_infracao": 3,
    "4_enquadramento": 3,
}
_PRIORIDADE_DEFAULT = 3

# Colunas calculadas de SLA (relógio desde sla_inicio = init_upload). Para OS
# encerradas o prazo é "infinito" (não há estouro após o encerramento).
_SLA_COLS = """
    numero_os,
    sla_inicio,
    ROUND((EXTRACT(EPOCH FROM (NOW() - COALESCE(sla_inicio, criada_em))) / 3600.0)::numeric, 2)
        AS sla_horas_decorridas,
    (EXTRACT(EPOCH FROM (NOW() - COALESCE(sla_inicio, criada_em))) / 3600.0 >
        CASE
            WHEN status IN ('encerrada', 'decisao_final') THEN 1e9
            WHEN status IN ('aguardando_supervisor', 'em_analise_supervisor')
                THEN COALESCE(sla_prazo_supervisor_h, 48)
            ELSE COALESCE(sla_prazo_auditor_h, 24)
        END) AS sla_estourado
"""


def _log(
    os_id: str,
    nivel: str,
    actor: str | None,
    action: str,
    details: dict | None = None,
    ip: str | None = None,
) -> None:
    """Evento na trilha de auditoria append-only (``os_eventos``). Nunca levanta."""
    if not db_enabled():
        return
    try:
        execute(
            "INSERT INTO os_eventos (os_id, nivel, actor, action, details, ip) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (os_id, nivel, actor, action, to_jsonb(details or {}), ip),
        )
    except Exception as e:  # pragma: no cover
        log.exception("os._log falhou (os_id=%s action=%s): %s", os_id, action, e)


# ---------------------------------------------------------------------------
# Abertura no init_upload (nível 1) — cada vídeo é uma OS
# ---------------------------------------------------------------------------


def abrir_os_no_upload(
    numero_os: str, *, hash_exame: str, external_id: int | None = None
) -> str | None:
    """Abre a OS do vídeo no momento do init_upload. Inicia o relógio do SLA.

    ``numero_os`` é o ID gerado no init_upload (analysis_id/hash ou external_id)
    e vira o número de negócio da OS. Idempotente: 1 OS por exame
    (UNIQUE(exam_id)). Retorna o os_id (UUID interno) ou None.
    """
    if not db_enabled():
        return None
    exam_id = exam_id_from_hash(hash_exame)
    if not exam_id:
        log.warning("abrir_os_no_upload: exame não encontrado para hash=%s", hash_exame)
        return None
    try:
        row = fetch_one(
            """
            INSERT INTO ordens_servico
                (exam_id, numero_os, status, sla_inicio, criada_em,
                 sla_prazo_auditor_h, sla_prazo_supervisor_h)
            VALUES (%s, %s, 'criada', NOW(), NOW(), %s, %s)
            ON CONFLICT (exam_id) DO NOTHING
            RETURNING id::text AS id
            """,
            (exam_id, numero_os, settings.sla_prazo_auditor_h, settings.sla_prazo_supervisor_h),
        )
    except Exception as e:  # pragma: no cover
        log.exception("abrir_os_no_upload: INSERT falhou hash=%s: %s", hash_exame, e)
        return None

    if row:
        os_id = row["id"]
        _log(
            os_id,
            "1_ia_principal",
            "sistema",
            "os_criada_upload",
            {"numero_os": numero_os, "external_id": external_id},
        )
        return os_id
    existente = fetch_one(
        "SELECT id::text AS id FROM ordens_servico WHERE exam_id = %s", (exam_id,)
    )
    return existente["id"] if existente else None


# ---------------------------------------------------------------------------
# Atualização após a análise (níveis 1→2): define o destino da OS
# ---------------------------------------------------------------------------


def atualizar_pos_analise(hash_exame: str, comparacao) -> str | None:
    """Atualiza a OS após o Motor de Comparação.

    Sem divergência (``encerramento``) → OS ``encerrada`` (arquivada sem humano).
    Com divergência (``comite_de_ia``) → OS ``aguardando_auditor`` + prioridade.

    Se a OS ainda não existir (ex.: fluxo que não passou pelo init_upload),
    abre-a aqui usando o hash como número — garante o invariante "1 vídeo = 1 OS".
    """
    if not db_enabled():
        return None
    exam_id = exam_id_from_hash(hash_exame)
    if not exam_id:
        return None

    os_row = fetch_one("SELECT id::text AS id FROM ordens_servico WHERE exam_id = %s", (exam_id,))
    os_id = os_row["id"] if os_row else abrir_os_no_upload(hash_exame, hash_exame=hash_exame)
    if not os_id:
        return None

    tipo = comparacao.tipo_divergencia.value

    if comparacao.encaminhamento != Encaminhamento.COMITE_DE_IA:
        # Sem divergência → encerra sem trabalho humano (spec §2.3).
        execute(
            """
            UPDATE ordens_servico
               SET tipo_divergencia = %s, status = 'encerrada',
                   encerrada_em = NOW(), atualizada_em = NOW()
             WHERE id = %s AND status NOT IN ('encerrada')
            """,
            (tipo, os_id),
        )
        _log(os_id, "2_comite", "sistema", "encerrada_sem_divergencia", {"tipo_divergencia": tipo})
        return os_id

    prioridade = _PRIORIDADE_POR_DIVERGENCIA.get(tipo, _PRIORIDADE_DEFAULT)
    execute(
        """
        UPDATE ordens_servico
           SET tipo_divergencia = %s, prioridade = %s,
               status = 'aguardando_auditor', atualizada_em = NOW()
         WHERE id = %s AND status IN ('criada', 'em_analise_ia')
        """,
        (tipo, prioridade, os_id),
    )
    _log(
        os_id,
        "2_comite",
        "sistema",
        "divergencia_confirmada",
        {"tipo_divergencia": tipo, "prioridade": prioridade},
    )
    return os_id


# ---------------------------------------------------------------------------
# Consulta (inclui SLA calculado)
# ---------------------------------------------------------------------------


def listar_os(
    status: str | None = None, auditor: str | None = None, limit: int = 200
) -> list[dict]:
    """Lista OS com SLA, ordenadas por prioridade e antiguidade (fila do pool)."""
    if not db_enabled():
        return []
    clausulas: list[str] = []
    params: list[Any] = []
    if status is not None:
        clausulas.append("status = %s")
        params.append(status)
    if auditor is not None:
        clausulas.append("auditor_email = %s")
        params.append(auditor)
    where = ("WHERE " + " AND ".join(clausulas)) if clausulas else ""
    params.append(int(limit))
    return fetch_all(
        f"""
        SELECT id::text AS id, exam_id::text AS exam_id, tipo_divergencia, status,
               auditor_email, supervisor_email, prioridade,
               criada_em, atualizada_em, encerrada_em,
               {_SLA_COLS}
          FROM ordens_servico
          {where}
         ORDER BY prioridade ASC, criada_em ASC
         LIMIT %s
        """,
        tuple(params),
    )


def get_os(os_id: str) -> dict | None:
    """OS (com SLA) + último parecer, última decisão e trilha completa."""
    if not db_enabled():
        return None
    os_row = fetch_one(
        f"""
        SELECT id::text AS id, exam_id::text AS exam_id, tipo_divergencia, status,
               auditor_email, supervisor_email, prioridade,
               criada_em, atualizada_em, encerrada_em,
               {_SLA_COLS}
          FROM ordens_servico WHERE id = %s
        """,
        (os_id,),
    )
    if not os_row:
        return None
    os_row["parecer"] = fetch_one(
        "SELECT id, auditor_email, decisao, justificativa, referencia_mbedv, created_at "
        "FROM auditor_pareceres WHERE os_id = %s ORDER BY created_at DESC LIMIT 1",
        (os_id,),
    )
    os_row["decisao"] = fetch_one(
        "SELECT id, supervisor_email, decisao_final, concorda_auditor, justificativa, created_at "
        "FROM supervisor_decisoes WHERE os_id = %s ORDER BY created_at DESC LIMIT 1",
        (os_id,),
    )
    os_row["eventos"] = fetch_all(
        "SELECT id, nivel, actor, action, details, ip, created_at "
        "FROM os_eventos WHERE os_id = %s ORDER BY created_at ASC, id ASC",
        (os_id,),
    )
    return os_row


# ---------------------------------------------------------------------------
# Transições do fluxo humano (níveis 3 e 4)
# ---------------------------------------------------------------------------


def atribuir(os_id: str, auditor_email: str) -> bool:
    """Atribui a OS a um auditor (pool aberto, nível 3). Guard otimista no WHERE."""
    if not db_enabled():
        return False
    rows = execute(
        "UPDATE ordens_servico SET auditor_email = %s, status = 'em_analise_auditor', "
        "atualizada_em = NOW() WHERE id = %s AND status = 'aguardando_auditor'",
        (auditor_email, os_id),
    )
    if rows > 0:
        _log(os_id, "3_auditor", auditor_email, "atribuida", {"auditor_email": auditor_email})
        return True
    return False


def registrar_parecer(parecer) -> bool:
    """Parecer do Auditor (nível 3) → encaminha ao Supervisor (sem atalho)."""
    if not db_enabled():
        return False
    inserido = execute(
        "INSERT INTO auditor_pareceres (os_id, auditor_email, decisao, justificativa, referencia_mbedv) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            parecer.os_id,
            parecer.auditor_email,
            parecer.decisao,
            parecer.justificativa,
            parecer.referencia_mbedv,
        ),
    )
    if inserido <= 0:
        return False
    execute(
        "UPDATE ordens_servico SET status = 'aguardando_supervisor', atualizada_em = NOW() WHERE id = %s",
        (parecer.os_id,),
    )
    _log(
        parecer.os_id,
        "3_auditor",
        parecer.auditor_email,
        "parecer_registrado",
        {"decisao": parecer.decisao, "referencia_mbedv": parecer.referencia_mbedv},
    )
    return True


def registrar_decisao(decisao) -> bool:
    """Decisão final do Supervisor (nível 4) → encerra a OS."""
    if not db_enabled():
        return False
    inserido = execute(
        "INSERT INTO supervisor_decisoes (os_id, supervisor_email, decisao_final, concorda_auditor, justificativa) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            decisao.os_id,
            decisao.supervisor_email,
            str(decisao.decisao_final),
            decisao.concorda_auditor,
            decisao.justificativa,
        ),
    )
    if inserido <= 0:
        return False
    execute(
        "UPDATE ordens_servico SET supervisor_email = %s, status = 'encerrada', "
        "encerrada_em = NOW(), atualizada_em = NOW() WHERE id = %s",
        (decisao.supervisor_email, decisao.os_id),
    )
    _log(
        decisao.os_id,
        "4_supervisor",
        decisao.supervisor_email,
        "decisao_final",
        {"decisao_final": str(decisao.decisao_final), "concorda_auditor": decisao.concorda_auditor},
    )
    return True
