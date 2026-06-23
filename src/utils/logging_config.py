"""Logging estruturado para o valbot.

Em dev: console renderer (legível, com cores). Em prod: JSON renderer (1 linha
por evento, ingerido automaticamente pelo Cloud Logging quando o container
roda no GCP). Também ofusca PII (CPF) em qualquer evento, e propaga
`request_id` via context vars (preenchido pelo middleware FastAPI).

Use:

    from src.utils.logging_config import setup_logging, log
    setup_logging()
    log.info("evento", extra_field="valor")

`log` é um wrapper que respeita `LOG_FORMAT=json` (default em prod, ver
Dockerfile) e o nível em `LOG_LEVEL` (default INFO).
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars
from structlog.types import EventDict

_CPF_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


def _mask_pii(_logger: Any, _name: str, event_dict: EventDict) -> EventDict:
    """Substitui CPF por máscara em qualquer string do event."""
    for k, v in list(event_dict.items()):
        if isinstance(v, str) and _CPF_RE.search(v):
            event_dict[k] = _CPF_RE.sub(lambda m: f"***.{m.group()[4:7]}.***-**", v)
    return event_dict


def setup_logging(level: str | None = None, fmt: str | None = None) -> None:
    """Configura structlog + stdlib logging em uma linha. Idempotente."""
    log_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    log_format = (fmt or os.getenv("LOG_FORMAT") or "console").lower()

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )

    processors: list = [
        merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _mask_pii,
    ]

    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty()))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


# Logger global. `bind` cria child loggers com contexto adicional.
log = structlog.get_logger("valbot")


__all__ = [
    "bind_contextvars",
    "clear_contextvars",
    "log",
    "setup_logging",
]
