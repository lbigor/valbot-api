"""Resiliência da ingestão (spec §5.6).

Cobre as três lacunas que a spec exige e o backend não tinha:

  • RETRY com backoff para falhas transitórias (vídeo inacessível, timeout).
  • DEAD LETTER QUEUE (``ingest_dlq``) para falhas persistentes — em vez de
    perder o exame, ele fica registrado para reprocessamento, com retenção.
  • ALERTA operacional (webhook configurável; fallback para log) quando algo
    vai para a DLQ ou um lote falha.

Tudo best-effort em relação ao banco (no-op sem DB), mas o retry/alerta
funcionam mesmo sem Postgres.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from backend.core import db
from backend.core.config import settings

log = logging.getLogger("valbot.ingest")

T = TypeVar("T")


def com_retry(
    fn: Callable[[], T],
    *,
    max_retries: int | None = None,
    base_delay: float = 1.0,
    sleep_fn: Callable[[float], None] | None = None,
    descricao: str = "operacao",
) -> T:
    """Executa ``fn`` com retry e backoff linear. Re-levanta a última exceção.

    ``base_delay`` é o passo do backoff (delay = base_delay * tentativa); use
    ``base_delay=0`` em testes para não dormir. ``sleep_fn`` é injetável para
    testabilidade (default: ``time.sleep``).
    """
    import time

    sleep_fn = sleep_fn or time.sleep
    tentativas = max_retries if max_retries is not None else settings.ingest_max_retries
    ultima_exc: Exception | None = None
    for tentativa in range(1, tentativas + 1):
        try:
            return fn()
        except Exception as e:
            ultima_exc = e
            log.warning("%s falhou (tentativa %d/%d): %s", descricao, tentativa, tentativas, e)
            if tentativa < tentativas and base_delay > 0:
                sleep_fn(base_delay * tentativa)
    assert ultima_exc is not None
    raise ultima_exc


def enviar_para_dlq(
    *,
    hash_: str | None,
    payload: dict | None,
    erro: str,
    tipo_falha: str = "desconhecido",
    tentativas: int = 0,
    numero_os: str | None = None,
    alertar_op: bool = True,
) -> bool:
    """Registra uma falha persistente na DLQ (com retenção) e dispara alerta.

    Retorna True se persistiu na DLQ. Mesmo sem DB, o alerta é emitido (log/
    webhook) para não perder o sinal operacional.
    """
    persistido = False
    if db.db_enabled():
        retencao_dias = settings.dlq_retencao_dias
        rows = db.execute(
            f"""
            INSERT INTO ingest_dlq (hash, numero_os, payload, erro, tipo_falha, tentativas, retencao_ate)
            VALUES (%s, %s, %s, %s, %s, %s, NOW() + INTERVAL '{int(retencao_dias)} days')
            """,
            (hash_, numero_os, db.to_jsonb(payload or {}), erro[:4000], tipo_falha, tentativas),
        )
        persistido = rows > 0
    if alertar_op:
        alertar(
            titulo=f"Ingestão falhou ({tipo_falha})",
            detalhes={
                "hash": hash_,
                "numero_os": numero_os,
                "erro": erro[:500],
                "tentativas": tentativas,
            },
        )
    return persistido


def listar_dlq(limit: int = 200) -> list[dict]:
    """Itens pendentes na DLQ (não resolvidos), mais antigos primeiro."""
    return db.fetch_all(
        "SELECT id, hash, numero_os, tipo_falha, tentativas, erro, criada_em, retencao_ate "
        "FROM ingest_dlq WHERE resolvida_em IS NULL ORDER BY criada_em ASC LIMIT %s",
        (int(limit),),
    )


def marcar_resolvida(dlq_id: int) -> bool:
    """Marca um item da DLQ como resolvido (após reprocessamento bem-sucedido)."""
    return db.execute("UPDATE ingest_dlq SET resolvida_em = NOW() WHERE id = %s", (dlq_id,)) > 0


def alertar(titulo: str, detalhes: dict[str, Any] | None = None) -> None:
    """Emite um alerta operacional. Usa webhook se configurado; senão, log WARN.

    Nunca levanta — alertar não pode derrubar a ingestão.
    """
    msg = (
        f"[ALERTA VALBOT] {titulo} | {json.dumps(detalhes or {}, ensure_ascii=False, default=str)}"
    )
    url = settings.alerta_webhook_url
    if not url:
        log.warning(msg)
        return
    try:
        import urllib.request

        req = urllib.request.Request(
            url,
            data=json.dumps({"text": msg, "titulo": titulo, "detalhes": detalhes or {}}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:  # pragma: no cover
        log.warning("%s (falha ao enviar webhook: %s)", msg, e)
