"""Acesso a dados — helpers genéricos sobre psycopg.

Filosofia herdada do backend atual (``tooling/api_stub/db.py``):
  • Em dev sem Postgres, ``VALBOT_DB_DISABLED=1`` torna tudo no-op/leitura vazia
    para que ``import`` e testes rodem sem banco.
  • Conexões em autocommit; cada chamada abre/fecha (volume baixo, simples).
  • Nenhuma função de escrita levanta para o caller — falha é logada
    (telemetria não deve mascarar o resultado de negócio).

Os repositórios de cada domínio (matriz, divergência, OS, …) usam estes
helpers em vez de reabrir conexão na mão.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from backend.core.config import settings

log = logging.getLogger("valbot.db")

try:  # psycopg é opcional em dev
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]
    Jsonb = None  # type: ignore[assignment]


def db_enabled() -> bool:
    return bool(not settings.db_disabled and psycopg is not None and settings.database_url)


def to_jsonb(value: Any) -> Any:
    """Embrulha em Jsonb quando psycopg está disponível; senão devolve cru."""
    return Jsonb(value) if Jsonb is not None else value


@contextmanager
def connection() -> Iterator[Any]:
    """Conexão autocommit. Yields ``None`` quando o DB está desabilitado."""
    if not db_enabled():
        yield None
        return
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        yield conn


def execute(sql: str, params: tuple | list | None = None) -> int:
    """Executa um comando de escrita. Devolve rowcount (0 se DB off ou falha)."""
    if not db_enabled():
        return 0
    try:
        with connection() as conn:
            if conn is None:
                return 0
            cur = conn.execute(sql, params or ())
            return cur.rowcount or 0
    except Exception as e:  # pragma: no cover — telemetria não deve quebrar fluxo
        log.exception("db.execute falhou: %s", e)
        return 0


def fetch_one(sql: str, params: tuple | list | None = None) -> dict | None:
    if not db_enabled():
        return None
    try:
        with connection() as conn:
            if conn is None:
                return None
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params or ())
                return cur.fetchone()
    except Exception as e:
        log.exception("db.fetch_one falhou: %s", e)
        return None


def fetch_all(sql: str, params: tuple | list | None = None) -> list[dict]:
    if not db_enabled():
        return []
    try:
        with connection() as conn:
            if conn is None:
                return []
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params or ())
                return list(cur.fetchall())
    except Exception as e:
        log.exception("db.fetch_all falhou: %s", e)
        return []


def exam_id_from_hash(hash_: str) -> str | None:
    """Resolve o UUID de ``exams`` a partir do hash (chave usada nas FKs)."""
    row = fetch_one("SELECT id::text AS id FROM exams WHERE hash = %s", (hash_,))
    return row["id"] if row else None
