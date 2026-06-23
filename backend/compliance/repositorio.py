"""Repositório da camada de Compliance (tabela ``exam_comentarios_compliance``).

Persiste e consulta os comentários de compliance. Best-effort em relação ao
banco (no-op sem DB). Não toca em pontuação — esta camada é estritamente o
não-pontuável.
"""

from __future__ import annotations

import logging

from backend.core import db
from backend.models import ComentarioCompliance

log = logging.getLogger("valbot.compliance")


def registrar(hash_exame: str, comentario: ComentarioCompliance) -> bool:
    """Insere um comentário de compliance para o exame. Devolve True se persistiu."""
    exam_id = db.exam_id_from_hash(hash_exame)
    if not exam_id:
        return False
    rows = db.execute(
        """
        INSERT INTO exam_comentarios_compliance
            (exam_id, tipo, origem_codigo, descricao, timestamp_s, transcricao,
             classificacao, severidade, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            exam_id,
            comentario.tipo.value,
            comentario.origem_codigo,
            comentario.descricao,
            comentario.timestamp_s,
            comentario.transcricao,
            comentario.classificacao,
            comentario.severidade,
            comentario.status,
        ),
    )
    return rows > 0


def registrar_varios(hash_exame: str, comentarios: list[ComentarioCompliance]) -> int:
    n = 0
    for c in comentarios:
        if registrar(hash_exame, c):
            n += 1
    if comentarios:
        log.info(
            "compliance: %d/%d comentários gravados (hash=%s)", n, len(comentarios), hash_exame[:12]
        )
    return n


def listar(
    *,
    status: str | None = "pendente",
    tipo: str | None = None,
    hash_exame: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Fila/lista de comentários para a tela de compliance."""
    clausulas: list[str] = []
    params: list = []
    if status:
        clausulas.append("status = %s")
        params.append(status)
    if tipo:
        clausulas.append("tipo = %s")
        params.append(tipo)
    if hash_exame:
        clausulas.append("exam_id = (SELECT id FROM exams WHERE hash = %s)")
        params.append(hash_exame)
    where = ("WHERE " + " AND ".join(clausulas)) if clausulas else ""
    params.append(int(limit))
    return db.fetch_all(
        f"""
        SELECT id, exam_id::text AS exam_id, tipo, origem_codigo, descricao,
               timestamp_s, transcricao, classificacao, severidade, status, created_at
        FROM exam_comentarios_compliance
        {where}
        ORDER BY created_at ASC
        LIMIT %s
        """,
        tuple(params),
    )


def marcar_analisado(
    comentario_id: int, *, por: str | None = None, status: str = "analisado"
) -> bool:
    return (
        db.execute(
            "UPDATE exam_comentarios_compliance SET status = %s, analisado_por = %s, updated_at = NOW() "
            "WHERE id = %s",
            (status, por, comentario_id),
        )
        > 0
    )


def resumo() -> dict:
    """Contagem de comentários pendentes por tipo (para o dashboard §15)."""
    rows = db.fetch_all(
        "SELECT tipo, COUNT(*) AS n FROM exam_comentarios_compliance "
        "WHERE status = 'pendente' GROUP BY tipo"
    )
    return {r["tipo"]: r["n"] for r in rows}
