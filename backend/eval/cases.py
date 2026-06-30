"""Loader read-only de casos de avaliação (exam_id -> gs_video + training_annotations).

Import do db é LAZY: o módulo importa sem tocar o banco; só a função executa a
query. Usado pela avaliação opt-in / CLI, NUNCA no CI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaseRecord:
    exam_id: str
    gs_uri: str
    training_annotations: list


def carregar_por_ids(ids: list[str]) -> list[CaseRecord]:
    """Carrega casos por lista de exam_id (read-only)."""
    from backend.core import db  # lazy

    if not ids:
        return []
    # = ANY(%s) com array parametrizado (sem concatenar SQL → sem risco de injeção)
    rows = db.fetch_all(
        "SELECT id, gs_video, training_annotations FROM exams "
        "WHERE id::text = ANY(%s) AND gs_video IS NOT NULL",
        (list(ids),),
    )
    return [
        CaseRecord(str(r["id"]), r["gs_video"], r.get("training_annotations") or []) for r in rows
    ]


def carregar_fn_208(data: str, limit: int = 12) -> list[CaseRecord]:
    """Casos de FALSO NEGATIVO de 208 do dia (oficial tem 208, IA não marcou),
    menores primeiro. Para a avaliação dirigida do detector."""
    from backend.core import db  # lazy

    rows = db.fetch_all(
        "SELECT id, gs_video, training_annotations FROM exams e "
        "WHERE categoria='B' AND resultado_exame='R' AND aprovado IS TRUE "
        "AND gs_video IS NOT NULL AND size_bytes IS NOT NULL "
        "AND (created_at AT TIME ZONE 'America/Sao_Paulo')::date = %s "
        "AND EXISTS (SELECT 1 FROM jsonb_array_elements(e.training_annotations) a "
        "            WHERE (a->>'anotacoes') ~* 'Art\\.? ?208') "
        "ORDER BY size_bytes ASC LIMIT %s",
        (data, limit),
    )
    return [
        CaseRecord(str(r["id"]), r["gs_video"], r.get("training_annotations") or []) for r in rows
    ]
