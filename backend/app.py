"""Aplicação FastAPI do backend v2 do Val Auditor Exames.

Monta os routers da cadeia de auditoria. Pensado para rodar lado a lado com o
servidor atual durante a transição (prefixo ``/api/v2``), permitindo migração
incremental sem derrubar o fluxo de produção.

    uvicorn backend.app:app --port 8001
"""

from __future__ import annotations

from fastapi import FastAPI

from backend import __version__
from backend.api.routers import (
    compliance_router,
    dashboard_router,
    exams_router,
    os_router,
)

app = FastAPI(
    title="Val Auditor Exames — Backend v2",
    version=__version__,
    description="Plataforma de auditoria técnico-regulatória (CONTRAN 1.020/2025 + MBEDV).",
)


@app.get("/api/v2/health", tags=["infra"])
async def health() -> dict:
    from backend.core import db

    return {"ok": True, "version": __version__, "db": db.db_enabled()}


app.include_router(exams_router)
app.include_router(os_router)
app.include_router(compliance_router)
app.include_router(dashboard_router)
