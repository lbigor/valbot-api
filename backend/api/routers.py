"""Routers FastAPI do backend v2.

Expõe os fluxos da spec organizados por área:

  /api/v2/exams      — ingestão (Motor de Evidências) e laudo explicável
  /api/v2/os         — Ordens de Serviço + fluxo humano (Auditor/Supervisor)
  /api/v2/dashboard  — indicadores operacionais e regulatórios

Streaming/upload de vídeo permanecem no servidor atual; aqui o foco é a cadeia
de auditoria, OS e laudo, consumindo ``backend.pipeline`` e ``backend.workflow``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend import persistence
from backend.api.deps import require_api_key, require_role
from backend.compliance import repositorio as compliance_repo
from backend.dashboard import metrics
from backend.engines import evidencias
from backend.models import DecisaoSupervisor, ParecerAuditor
from backend.workflow import ordens

log = logging.getLogger("valbot.api")

# --- Ingestão / laudo -------------------------------------------------------

exams_router = APIRouter(prefix="/api/v2/exams", tags=["exames"])


class IngestItem(BaseModel):
    hash: str
    payload: dict  # shape A/B do init-upload OU já estruturado (spec §5.4)


@exams_router.post("/ingest")
async def ingest(item: IngestItem, _auth: dict = Depends(require_api_key("exams:create"))):
    """Motor de Evidências: normaliza e valida o payload, persiste o que falta.

    A análise pesada (download + Gemini) é disparada pelo worker; aqui validamos
    e registramos o resultado oficial / campos da spec §5.4.
    """
    payload = evidencias.normalizar(item.payload)
    validacao = evidencias.validar(payload, duracao_seg=payload.duracao_video_seg)
    if not validacao.ok:
        raise HTTPException(
            status_code=422, detail={"erros": validacao.erros, "tipo": validacao.falha_tipo}
        )
    persistence.salvar_payload(item.hash, payload)
    # Abre a OS já no init_upload (cada vídeo é uma OS; SLA começa aqui).
    numero_os = payload.exame_id or item.hash
    os_id = ordens.abrir_os_no_upload(numero_os, hash_exame=item.hash)
    return {
        "hash": item.hash,
        "ok": True,
        "numero_os": numero_os,
        "os_id": os_id,
        "campos_faltantes": validacao.campos_faltantes,
        "avisos": validacao.avisos,
    }


@exams_router.get("/{hash_}/laudo")
async def laudo(hash_: str, _auth: dict = Depends(require_api_key("exams:read"))):
    """Recupera o laudo explicável (JSON) de um exame já processado."""
    overview = (
        persistence.db.get_overview(hash_) if hasattr(persistence.db, "get_overview") else None
    )
    div = persistence.db.fetch_one(
        "SELECT * FROM exam_divergencias WHERE exam_id = (SELECT id FROM exams WHERE hash=%s)",
        (hash_,),
    )
    if div is None and overview is None:
        raise HTTPException(status_code=404, detail="exame não encontrado ou ainda não processado")
    return {"hash": hash_, "divergencia": div, "overview": overview}


# --- Ordens de Serviço (fluxo humano §11-§12) -------------------------------

os_router = APIRouter(prefix="/api/v2/os", tags=["ordens_servico"])


@os_router.get("")
async def listar(
    status: str | None = None, sess: dict = Depends(require_role("auditor", "supervisor"))
):
    return {"itens": ordens.listar_os(status=status, auditor=None)}


@os_router.get("/{os_id}")
async def detalhe(os_id: str, sess: dict = Depends(require_role("auditor", "supervisor"))):
    os_ = ordens.get_os(os_id)
    if not os_:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return os_


@os_router.post("/{os_id}/atribuir")
async def atribuir(os_id: str, sess: dict = Depends(require_role("auditor"))):
    ok = ordens.atribuir(os_id, sess["email"])
    if not ok:
        raise HTTPException(status_code=409, detail="OS não está aguardando auditor")
    return {"os_id": os_id, "auditor": sess["email"]}


class ParecerIn(BaseModel):
    decisao: str  # concorda_ia | discorda_ia | inconclusivo
    justificativa: str
    referencia_mbedv: str | None = None


@os_router.post("/{os_id}/parecer")
async def parecer(os_id: str, body: ParecerIn, sess: dict = Depends(require_role("auditor"))):
    p = ParecerAuditor(os_id=os_id, auditor_email=sess["email"], **body.model_dump())
    if not ordens.registrar_parecer(p):
        raise HTTPException(status_code=400, detail="não foi possível registrar parecer")
    return {"os_id": os_id, "status": "aguardando_supervisor"}


class DecisaoIn(BaseModel):
    decisao_final: str
    concorda_auditor: bool
    justificativa: str


@os_router.post("/{os_id}/decisao")
async def decisao(os_id: str, body: DecisaoIn, sess: dict = Depends(require_role("supervisor"))):
    d = DecisaoSupervisor(os_id=os_id, supervisor_email=sess["email"], **body.model_dump())
    if not ordens.registrar_decisao(d):
        raise HTTPException(status_code=400, detail="não foi possível registrar decisão")
    return {"os_id": os_id, "status": "encerrada"}


# --- Compliance (tela dedicada de sinais não-pontuáveis) --------------------

compliance_router = APIRouter(prefix="/api/v2/compliance", tags=["compliance"])


@compliance_router.get("")
async def listar_compliance(
    status: str = "pendente",
    tipo: str | None = None,
    sess: dict = Depends(require_role("auditor", "supervisor", "admin")),
):
    """Fila de comentários de compliance para a tela dedicada."""
    return {"itens": compliance_repo.listar(status=status, tipo=tipo)}


@compliance_router.post("/{comentario_id}/analisar")
async def analisar_compliance(
    comentario_id: int,
    status: str = "analisado",
    sess: dict = Depends(require_role("auditor", "supervisor", "admin")),
):
    ok = compliance_repo.marcar_analisado(comentario_id, por=sess.get("email"), status=status)
    if not ok:
        raise HTTPException(status_code=404, detail="comentário não encontrado")
    return {"id": comentario_id, "status": status}


# --- Dashboard --------------------------------------------------------------

dashboard_router = APIRouter(prefix="/api/v2/dashboard", tags=["dashboard"])


@dashboard_router.get("")
async def resumo(
    dias: int = 30, sess: dict = Depends(require_role("auditor", "supervisor", "admin"))
):
    return metrics.resumo(dias)
