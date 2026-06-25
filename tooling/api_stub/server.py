"""
API stub mínima para demonstrar o frontend recebendo seleção de fluxo de análise.
Aceita upload de vídeo + analysis_flow do UploadVideoModal e devolve um analysis_id.

Rodar:
  cd /Users/igorlima/Documents/Valbot
  .venv/bin/python -m tooling.api_stub.server

Endpoint:
  POST /api/exams       — recebe upload + form fields + analysis_flow → retorna analysis_id
  GET  /api/exams/{id}  — retorna metadata do upload
  GET  /api/exams       — lista todos os uploads
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import traceback
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    Body,
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from tooling.api_stub import db  # Postgres helper (no-op se VALBOT_DB_DISABLED=1)


def require_api_key(scope: str):
    """Dependency factory: valida X-API-Key e checa scope. 401 se inválida/sem permissão."""

    def _dep(x_api_key: str | None = Header(None, alias="X-API-Key")):
        if not x_api_key:
            raise HTTPException(401, "X-API-Key header obrigatório")
        info = db.validate_api_key(x_api_key, scope)
        if not info:
            raise HTTPException(401, "API key inválida, revogada ou sem scope")
        return info

    return _dep


def require_admin_token(x_admin_token: str | None = Header(None, alias="X-Admin-Token")):
    """Protege endpoints administrativos via env VALBOT_ADMIN_TOKEN."""
    expected = os.environ.get("VALBOT_ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(503, "VALBOT_ADMIN_TOKEN não configurado")
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(401, "X-Admin-Token inválido")


# =============================================================================
# Sessão de login (cookie httpOnly assinado HMAC) — porta de entrada do SPA.
# Substitui o mock client-side. O cookie carrega email|role|exp e uma
# assinatura HMAC com segredo do servidor → não é forjável sem o segredo.
# =============================================================================
SESSION_COOKIE = "valbot_session"
SESSION_TTL = 60 * 60 * 24 * 90  # 90 dias
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _mask_cpf(cpf: str | None) -> str:
    """Mascara CPF para logs e PDF (LGPD §17) → ***.456.789-**.
    O dado real continua no banco (protegido por sessão); só a exibição é mascarada."""
    if not cpf:
        return cpf or ""
    d = re.sub(r"\D", "", str(cpf))
    if len(d) >= 11:
        return f"***.{d[3:6]}.{d[6:9]}-**"
    return "*" * len(str(cpf))


def _add_hours(value, hours: int) -> str | None:
    """Soma `hours` horas a um instante (datetime ou ISO string) e devolve ISO.
    Usado para o vencimento do SLA (aberta_em + prazo do auditor). None se a
    entrada for vazia/ilegível — nunca inventa um vencimento."""
    if not value:
        return None
    dt = value
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (dt + timedelta(hours=hours)).isoformat()


def _derive_video_ok(row: dict) -> bool | None:
    """Qualidade de câmera/vídeo OK, derivada do que a v_exams_overview já expõe:
    veredito do validador (validator_veredito HOMO/NAO_HOMO) e, na ausência dele,
    a confiança do layout (layout_confianca ≥ 0.7). Sem nenhum dos sinais ⇒ None
    (sem dado, não inventa)."""
    ver = row.get("validator_veredito")
    if ver:
        v = str(ver).strip().upper()
        if v == "HOMO":
            return True
        if v == "NAO_HOMO":
            return False
    conf = row.get("layout_confianca")
    if conf is None:
        conf = row.get("validator_confianca")
    if conf is not None:
        try:
            return float(conf) >= 0.7
        except (TypeError, ValueError):
            return None
    return None


def _mask_renach(renach: str | None) -> str:
    """Mascara RENACH para logs e PDF: mantém 2 primeiros + 2 últimos (UF/dígito)."""
    if not renach:
        return renach or ""
    s = str(renach).strip()
    if len(s) <= 4:
        return "*" * len(s)
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


def _actor_ip(request) -> tuple[str | None, str | None]:
    """Extrai (email_da_sessão, ip_do_cliente) de uma request — p/ trilha de
    auditoria de leitura (LGPD §17.2). Respeita X-Forwarded-For (Cloudflare)."""
    sess = _verify_session(request.cookies.get(SESSION_COOKIE)) if request else None
    actor = sess.get("email") if sess else None
    ip = None
    if request is not None:
        xff = request.headers.get("x-forwarded-for", "")
        ip = xff.split(",")[0].strip() or (request.client.host if request.client else None)
    return actor, ip


def _session_secret() -> str:
    # Reusa o segredo já existente; sem ele, sessão fica indisponível (503).
    return os.environ.get("VALBOT_SESSION_SECRET") or os.environ.get("VALBOT_ADMIN_TOKEN", "")


def _role_for(email: str) -> str:
    """Heurística de papel (mesma do mock antigo, pra paridade de UX)."""
    e = email.lower()
    if "revisor" in e:
        return "revisor"
    if "auditor" in e:
        return "auditor"
    return "admin"


def _sign_session(email: str, role: str, exp: int) -> str:
    secret = _session_secret().encode()
    payload = f"{email}|{role}|{exp}"
    sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def _verify_session(cookie: str | None) -> dict | None:
    """Devolve {email, role, is_admin} se o cookie é válido e não expirou."""
    if not cookie:
        return None
    secret = _session_secret()
    if not secret:
        return None
    try:
        email, role, exp_s, sig = cookie.rsplit("|", 3)
    except ValueError:
        return None
    expected = hmac.new(
        secret.encode(), f"{email}|{role}|{exp_s}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        if int(exp_s) < int(time.time()):
            return None
    except ValueError:
        return None
    return {"email": email, "role": role, "is_admin": role in ("admin", "supervisor")}


def require_session(valbot_session: str | None = Cookie(default=None)) -> dict:
    """Dependency: exige sessão de login válida (cookie assinado). Usada para
    proteger ações da Fila (reanalyze, process-pending) sem expor o
    X-Admin-Token ao front."""
    sess = _verify_session(valbot_session)
    if sess is None:
        raise HTTPException(401, "sessão inválida ou expirada — faça login")
    return sess


def _pode_enviar_laudos(email: str | None) -> bool:
    """Lê a flag por usuário `users.pode_enviar_laudos`. Default False — só quem
    foi explicitamente liberado envia laudos à TechPrático. Lida ao vivo (não
    embutida no cookie) pra que mudança de permissão valha já no próximo /me,
    sem exigir novo login."""
    if not email:
        return False
    try:
        from tooling.api_stub import db as _db

        with _db._conn() as c:  # type: ignore[attr-defined]
            if c is None:
                return False
            row = c.execute(
                "SELECT pode_enviar_laudos FROM users WHERE email = %s",
                (email.strip().lower(),),
            ).fetchone()
            return bool(row and row[0])
    except Exception as e:  # noqa: BLE001 — coluna ausente / DB off → nega
        log.warning("_pode_enviar_laudos falhou (%s)", e)
        return False


def require_envio_laudos(_sess: dict = Depends(require_session)) -> dict:
    """Dependency: exige sessão válida E a permissão `pode_enviar_laudos`.
    403 se logado mas sem a flag — defesa no backend além do gating de UI."""
    if not _pode_enviar_laudos(_sess.get("email")):
        raise HTTPException(403, "sem permissão para enviar laudos")
    return _sess


def require_admin(_sess: dict = Depends(require_session)) -> dict:
    """Dependency: exige sessão com is_admin (role admin|supervisor). 403 caso
    contrário. `is_admin` é recalculado por _verify_session a cada request.
    Definida aqui (e não mais perto de APP SETTINGS) porque rotas anteriores
    àquele ponto — gestão de usuários — também a usam."""
    if not _sess.get("is_admin"):
        raise HTTPException(403, "ação restrita a administradores")
    return _sess


def require_supervisor(_sess: dict = Depends(require_session)) -> dict:
    """Dependency: reserva a ação ao Supervisor (nível 4) — role admin|supervisor.
    Bloqueia o Auditor (nível 3) com 403. Cobre a decisão final de divergência
    (spec §11.2: 'supervisor revisa toda divergência, sem atalho')."""
    if _sess.get("role") not in ("admin", "supervisor"):
        raise HTTPException(403, "decisão final restrita ao supervisor")
    return _sess


try:
    from structlog.contextvars import bind_contextvars, clear_contextvars

    from src.utils.logging_config import log as _struct_log
    from src.utils.logging_config import setup_logging

    setup_logging()
    log = _struct_log.bind(component="api_stub")
except Exception:
    # fallback se structlog não estiver instalado (dev sem deps completas)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("valbot.api")
    bind_contextvars = lambda **kw: None  # noqa: E731
    clear_contextvars = lambda: None  # noqa: E731

PROJECT_ROOT = Path(__file__).parent.parent.parent
STORAGE = PROJECT_ROOT / "storage" / "analyses_demo"
STORAGE.mkdir(parents=True, exist_ok=True)

# Diretório oficial de análises Gemini (uploads via /api/exams). Diferente de
# `STORAGE` (analyses_demo) que guarda runs antigos (Tier A clássico, bench).
ANALYSES_DIR = PROJECT_ROOT / "storage" / "analyses"
ANALYSES_DIR.mkdir(parents=True, exist_ok=True)

PRESET_V25_PATH = (
    PROJECT_ROOT / "tooling" / "bench_demo" / "presets" / "v25" / "valbot-r1-vip-v25.md"
)

USE_MOCK_VLM = os.environ.get("VALBOT_USE_MOCK_VLM", "0") == "1"

GCS_BUCKET = os.environ.get("GCS_BUCKET", "valbot-prod")
GCS_UPLOAD_PREFIX = "uploads"
SIGNED_URL_TTL_MINUTES = 20
MAX_UPLOAD_SIZE_BYTES = 600 * 1024 * 1024  # 600 MB — folga sobre os 500 MB típicos
ALLOWED_EXTENSIONS = (".mp4", ".mov", ".m4v")
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/x-m4v"}

# Custos por fluxo (devem bater com src/types/flow.ts no frontend)
FLOW_COSTS = {
    "qwen3-vl": {"rank": 1, "name": "Qwen3-VL-235B", "cost_usd": 0.025, "latency_s": 45},
    "gemini-3.1-pro": {
        "rank": 2,
        "name": "Gemini 3.1 Pro Preview",
        "cost_usd": 0.180,
        "latency_s": 75,
    },
    "gpt-5.5": {"rank": 3, "name": "GPT-5.5", "cost_usd": 0.190, "latency_s": 105},
}


app = FastAPI(
    title="VALBOT API",
    description="Auditoria automática de exames práticos DETRAN (Res. CONTRAN 1.020/2025).",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


@app.on_event("startup")
def _warm_fila_cache() -> None:
    """Pré-aquece os caches da fila (feed + totais) no boot e mantém quente com
    um refresher em background a cada 5s. Garante que /fila NUNCA espera o
    recompute — todo request lê de cache fresco (<1ms)."""
    import threading as _th

    def _runner():
        while True:
            try:
                _refresh_videos_cache(include_test=False)
                _compute_totais()
            except Exception:
                log.exception("warm fila cache falhou")
            time.sleep(15)

    _th.Thread(target=_runner, daemon=True, name="fila-cache-warm").start()
    log.info("fila cache warm thread disparada (refresh a cada 5s)")


@app.on_event("startup")
def _preload_pdf_stack() -> None:
    """Pré-carrega WeasyPrint + adapter no boot (custa ~150s na primeira vez,
    devido a fontconfig). Sem isso, a primeira chamada a /api/exams trava."""
    try:
        from src.reporting import adapter as _adapter  # noqa: F401
        from src.reporting import pdf as _pdf  # noqa: F401

        log.info("PDF stack preloaded (WeasyPrint + adapter)")
    except Exception:
        log.exception("PDF preload failed — first request will pay the cost")


@app.on_event("startup")
def _warm_backlog_async() -> None:
    """Dispara backfill (enrich upload.json + warm local) em thread separada.

    Não bloqueia o boot — é best-effort. Pra cada análise já streamada
    (`video.gs_path` apontando pro GCS) que ainda não tem `video.mp4` local,
    baixa o blob e popula size/duration. Pode ser desligado com
    `VALBOT_DISABLE_BOOT_WARM=1`.
    """
    import os as _os

    if _os.getenv("VALBOT_DISABLE_BOOT_WARM") == "1":
        log.info("boot warm desabilitado via VALBOT_DISABLE_BOOT_WARM=1")
        return

    def _runner() -> None:
        try:
            from tooling.process_pending_s3 import backfill_one, list_streamed

            ids = list_streamed()
            log.info("boot warm: backfill de %d análises já streamadas", len(ids))
            enriched_n = warmed_n = 0
            for aid in ids:
                try:
                    e, w = backfill_one(aid, warm=True)
                    enriched_n += 1 if e else 0
                    warmed_n += 1 if w else 0
                except Exception:
                    log.exception("boot warm [%s] falhou", aid[:12])
            log.info(
                "boot warm FIM enriched=%d warmed=%d total=%d",
                enriched_n,
                warmed_n,
                len(ids),
            )
        except Exception:
            log.exception("boot warm runner crashed")

    import threading

    threading.Thread(target=_runner, daemon=True, name="boot-warm").start()
    log.info("boot warm thread disparada (background)")


def _claim_next_queued() -> str | None:
    """Reivindica atomicamente o próximo exame CAT B na fila (status->running),
    evitando que dois workers peguem o mesmo (FOR UPDATE SKIP LOCKED)."""
    try:
        from tooling.api_stub import db as _db

        with _db._conn() as c:  # type: ignore[attr-defined]
            if c is None:
                return None
            row = c.execute(
                """
                UPDATE exams SET status='running'
                WHERE hash = (
                    SELECT hash FROM exams
                    WHERE status='queued' AND categoria='B'
                      AND gs_video LIKE 'gs://%'
                      AND renach IS NOT NULL AND renach NOT ILIKE 'MOCK%'
                    ORDER BY updated_at NULLS FIRST
                    LIMIT 1 FOR UPDATE SKIP LOCKED
                )
                RETURNING hash
                """
            ).fetchone()
            return row[0] if row else None
    except Exception as e:
        log.warning("_claim_next_queued falhou: %s", e)
        return None


@app.on_event("startup")
def _auto_queue_worker() -> None:
    """WORKER AUTOMÁTICO da fila — drena os exames CAT B `queued` sozinho,
    de forma contínua e idempotente. Roda DENTRO da API (inicia com o container,
    `restart: unless-stopped` garante que volte). Substitui o worker manual
    (nohup) frágil. Concorrência 1 + backoff em 429 = não estoura quota.

    Também resolve o gap original: vídeo recém-`init_upload` (queued) agora é
    processado automaticamente, sem disparo externo. Desliga com
    VALBOT_AUTO_WORKER=0."""
    if os.environ.get("VALBOT_AUTO_WORKER", "1") != "1":
        log.info("auto-queue worker desabilitado (VALBOT_AUTO_WORKER=0)")
        return
    if USE_MOCK_VLM:
        return
    import threading

    def _runner(idx: int = 0) -> None:
        time.sleep(20 + idx * 4)  # boot estabiliza + escalona o arranque das threads
        backoff = 0
        log.info("auto-queue worker #%d ON — drenando fila CAT B", idx + 1)
        while True:
            try:
                h = _claim_next_queued()
                if not h:
                    time.sleep(30)
                    continue
                out_dir = ANALYSES_DIR / h
                upload = out_dir / "upload.json"
                if not upload.exists():
                    db.update_status(h, "failed", error="upload.json ausente")
                    continue
                meta = json.loads(upload.read_text())
                gs = (meta.get("video") or {}).get("gs_path")
                if not gs:
                    db.update_status(h, "failed", error="sem gs_path")
                    continue
                _run_analysis(h, gs, meta, force_v26=False)
                # 429/quota → re-enfileira e respira (backoff exponencial).
                st = db.fetch_status(h) or ""
                err = ""
                try:
                    from tooling.api_stub import db as _db

                    with _db._conn() as c:  # type: ignore[attr-defined]
                        r = c.execute("SELECT error FROM exams WHERE hash=%s", (h,)).fetchone()
                        err = (r[0] or "") if r else ""
                except Exception:
                    pass
                if st == "failed" and ("429" in err or "exhaust" in err.lower()):
                    db.update_status(h, "queued")  # tenta de novo depois
                    backoff = min(300, (backoff or 20) * 2)
                    log.warning(
                        "auto-queue 429 em %s — backoff %ss, re-enfileirado", h[:12], backoff
                    )
                    time.sleep(backoff)
                else:
                    backoff = 0
                    time.sleep(3)
            except Exception:
                log.exception("auto-queue worker erro")
                time.sleep(15)

    n = max(1, int(os.environ.get("VALBOT_AUTO_WORKERS", "3") or "3"))
    for i in range(n):
        threading.Thread(target=_runner, args=(i,), daemon=True, name=f"auto-queue-{i + 1}").start()
    log.info("auto-queue worker: %d threads disparadas (concorrência)", n)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_PUBLIC_API_PATHS = {
    # Verdadeiramente públicos (sem PII; ou com auth própria no endpoint):
    "/api/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/exams/init-upload",  # auth própria: X-API-Key (require_api_key)
    "/api/admin/api-keys",  # auth própria: X-Admin-Token
}
# Paths do SPA que expõem dados de exame (lista, dashboard) — passam a EXIGIR
# sessão de login válida (cookie). Antes eram públicos: vazavam PII/RENACH e
# KPIs sem login (LGPD §17). Mantidos fora do X-Admin-Token (que é p/ ops).
_SPA_SESSION_PATHS = {
    "/api/videos",
    "/api/exams",
    "/api/dashboard/valbot",
    "/api/dashboard/custos",
    "/api/dashboard/kpis",
    "/api/dashboard/diario",
    "/api/v2/dashboard",
    "/api/os",
}
_FINALIZE_RE = re.compile(r"^/api/exams/[^/]+/finalize$")
# Leitura por id (SPA): /api/exams/<id>, /api/exams/<id>/result,
# /api/laudo/<id>/pdf, /api/analyses/hash/<id>/result, /api/analyses/<id>/annotations.
_SPA_READ_RE = re.compile(
    r"^/api/("
    r"exams/[^/]+(?:/result|/video|/thumbnails|/waveform)?"
    r"|laudo/[^/]+/pdf"
    r"|analyses/hash/[^/]+/result"
    r"|analyses/[^/]+/annotations"
    r"|rubricas/.*"
    r"|videos(?:/totais)?"
    r")$"
)
# Ações disparadas pelo SPA da Fila Operacional (botão "Processar" / "Processar
# pendentes"). Dispensadas do X-Admin-Token aqui no middleware, MAS protegidas
# no endpoint por Depends(require_session) — exigem cookie de login válido.
# Ou seja: não são públicas, só não usam o token admin secreto.
_SPA_ACTION_RE = re.compile(
    r"^/api/exams/(?:"
    r"[^/]+/reanalyze"
    r"|[^/]+/buscar-resultado"  # busca single do resultado oficial (TechPrático)
    r"|buscar-resultados"  # busca em LOTE (botão "Buscar lote" do Kanban)
    r"|process-pending"
    r"|enviar-laudos"
    r"|[^/]+/parecer-auditor"
    r")$"
)
# Telas de Gestão (Usuários, Relatórios, Medição, Cron/Batch, Supervisor) —
# todas protegidas por Depends(require_session) no endpoint; aqui só dispensamos
# o X-Admin-Token (caem na Camada 2 = sessão de login). Cobre:
#   /api/admin/users[...]            (gestão de admins)
#   /api/admin/cron-jobs[...]        (agendamentos + trigger + runs)
#   /api/relatorios/*                (lista, csv, consolidado)
#   /api/exams/<hash>/laudo-json|laudo-pdf|init-upload
#   /api/telemetria                  (POST telemetria do auditor)
#   /api/dashboard/auditor-metrics|supervisor-metrics
#   /api/os/<id>/decisao             (decisão do supervisor)
_SPA_GESTAO_RE = re.compile(
    r"^/api/("
    r"admin/users(?:/[^/]+(?:/reset-password)?)?"
    r"|admin/settings(?:/[^/]+)?"
    r"|admin/cron-jobs(?:/[^/]+(?:/trigger|/runs)?)?"
    r"|relatorios/[^/]+"
    r"|relatorios/export\.csv"
    r"|exams/[^/]+/(?:laudo-json|laudo-pdf|init-upload)"
    r"|telemetria"
    r"|dashboard/(?:auditor-metrics|supervisor-metrics)"
    r"|os/[^/]+/decisao"
    r")$"
)


_INIT_UPLOAD_HINT = (
    "Body deve ser OBJETO único {url, renach, ...} OU ARRAY "
    "[{url, id, renach, processo}, ...] (até 50 itens). Detalhes em /api/docs."
)


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    """422 amigável — substitui o blob Pydantic cru por mensagem em PT-BR
    + apontador pro Swagger. Mantém `details` pra debug.

    Em /api/exams/init-upload o hint é específico do shape dual; outros
    endpoints recebem hint genérico.
    """
    path = request.url.path
    hint = (
        _INIT_UPLOAD_HINT
        if path.endswith("/api/exams/init-upload")
        else "Confira tipos e campos obrigatórios. Schema em /api/docs."
    )

    # Resumo enxuto: pega só (loc, msg) — sem `input`, sem `url`, sem `ctx`.
    fields = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x not in ("body",))
        fields.append({"campo": loc or "body", "erro": err.get("msg", "")})

    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "hint": hint,
            "campos_invalidos": fields,
        },
    )


@app.middleware("http")
async def internal_lockdown(request, call_next):
    """Controle de acesso em 3 camadas:
    1. PÚBLICO (sem auth): health/docs + init-upload/finalize (que têm auth própria
       via X-API-Key) + /api/auth/*.
    2. SESSÃO (cookie de login): tudo que expõe dado de exame — leitura por id
       (_SPA_READ_RE), ações do SPA (_SPA_ACTION_RE) e listas/dashboard
       (_SPA_SESSION_PATHS). Sem cookie válido → 401. Fecha o vazamento de
       PII/RENACH e laudo que antes eram públicos (LGPD §17).
    3. ADMIN (X-Admin-Token): o resto (endpoints internos de operação)."""
    from fastapi.responses import JSONResponse as _JR

    p = request.url.path
    if not p.startswith("/api/"):
        return await call_next(request)

    # Camada 1 — público
    if p in _PUBLIC_API_PATHS or p.startswith("/api/auth/") or _FINALIZE_RE.match(p):
        return await call_next(request)

    # Camada 2 — exige sessão de login válida
    if (
        p in _SPA_SESSION_PATHS
        or _SPA_READ_RE.match(p)
        or _SPA_ACTION_RE.match(p)
        or _SPA_GESTAO_RE.match(p)
    ):
        if _verify_session(request.cookies.get(SESSION_COOKIE)) is None:
            return _JR(
                {"detail": "sessão inválida ou expirada — faça login"},
                status_code=401,
            )
        return await call_next(request)

    # Camada 3 — endpoints internos (operação)
    expected = os.environ.get("VALBOT_ADMIN_TOKEN", "")
    token = request.headers.get("X-Admin-Token", "")
    if not expected or token != expected:
        return _JR({"detail": "X-Admin-Token requerido (endpoint interno)"}, status_code=401)
    return await call_next(request)


@app.middleware("http")
async def request_id_middleware(request, call_next):
    """Propaga X-Request-ID em todos os logs estruturados desta request.
    Preserva o ID se vier do cliente (Cloudflare passa adiante o ray-id)."""
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    bind_contextvars(request_id=rid, method=request.method, path=request.url.path)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        clear_contextvars()


@app.get("/api/health")
def health():
    return {"ok": True, "ts": datetime.utcnow().isoformat() + "Z"}


@app.get("/api/dashboard/custos")
def dashboard_custos(dias: int = 30):
    """Custos de processamento (vídeo/tokens) agregados — acompanhamento e cobrança.

    Quebra cost_usd e tokens da janela (`dias`) por dia/unidade/categoria. DB
    indisponível devolve a estrutura zerada (nunca 500). `dias` limitado a [1, 365].
    """
    dias = max(1, min(int(dias), 365))
    try:
        from tooling.api_stub import db as _db

        data = _db.custos_agregados(dias)
    except Exception as e:
        log.warning("dashboard_custos falhou: %s", e)
        data = None
    if data is None:
        data = {
            "periodo_dias": dias,
            "custo_total_usd": 0.0,
            "num_exames_cobrados": 0,
            "custo_medio_por_exame_usd": 0.0,
            "tokens_in_total": 0,
            "tokens_out_total": 0,
            "serie_diaria": [],
            "por_unidade": [],
            "por_categoria": [],
        }
    return data


# ============================================================================
# Autenticação — login por email com cookie de sessão assinado (httpOnly).
# Porta de entrada do SPA. Substitui o mock client-side antigo.
# ============================================================================
class _EmailIn(BaseModel):
    email: str | None = None  # email OU telefone no mesmo campo (compat frontend)
    login: str | None = None  # alias explícito p/ email-ou-telefone
    telefone: str | None = None  # telefone explícito (opcional)
    password: str | None = None
    senha_atual: str | None = None  # senha vigente (usado em change-password)


def _normalize_telefone(v: str) -> str:
    """Só dígitos. '+55 27 99277-9201' -> '5527992779201'."""
    import re as _re

    return _re.sub(r"\D", "", v or "")


def _verify_password(senha: str, senha_hash: str) -> bool:
    """Valida senha contra hash pbkdf2_sha256$iter$salt$hash."""
    try:
        algo, iters, salt, expected = senha_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), expected)
    except Exception:
        return False


def _hash_password(senha: str) -> str:
    """Gera hash no mesmo formato lido por _verify_password:
    pbkdf2_sha256$<iters>$<salt>$<hex>. Usado no fluxo de 1º acesso
    (usuário cadastrado sem senha define a própria)."""
    import secrets

    iters = 200000
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), iters)
    return f"pbkdf2_sha256${iters}${salt}${dk.hex()}"


def _lookup_user(identifier: str):
    """Busca usuário por EMAIL (contém '@') ou TELEFONE (só dígitos) na
    tabela `users`. Retorna a tupla
    (email, senha_hash, role, nome, ativo, senha_temporaria)
    ou None se não existe / erro de banco.

    `senha_temporaria` (bool) sinaliza que a senha atual foi gerada por um
    reset do admin e precisa ser trocada no 1º login antes de autenticar."""
    ident = (identifier or "").strip().lower()
    is_email = "@" in ident
    tel = _normalize_telefone(ident) if not is_email else None
    try:
        from tooling.api_stub import db as _db

        with _db._conn() as c:  # type: ignore[attr-defined]
            if c is None:
                return None
            if is_email:
                cur = c.execute(
                    "SELECT email, senha_hash, role, nome, ativo, "
                    "COALESCE(senha_temporaria, FALSE) "
                    "FROM users WHERE email = %s",
                    (ident,),
                )
            else:
                cur = c.execute(
                    "SELECT email, senha_hash, role, nome, ativo, "
                    "COALESCE(senha_temporaria, FALSE) "
                    "FROM users WHERE telefone = %s",
                    (tel,),
                )
            return cur.fetchone()
    except Exception as e:
        log.warning("_lookup_user falhou (%s)", e)
        return None


def _auth_user(identifier: str, password: str | None):
    """Autentica por EMAIL ou TELEFONE + senha contra a tabela `users`.
    Retorna {email, role, nome, senha_temporaria} se a senha confere; None
    caso contrário. Sem fallback passwordless — usuário inexistente, inativo,
    sem senha definida ou senha errada → acesso negado.

    NOTA: senha temporária (reset do admin) CONFERE aqui — quem decide barrar
    o cookie e forçar a troca é o caller (auth_email/auth_login), via o campo
    `senha_temporaria` retornado."""
    row = _lookup_user(identifier)
    if not row:
        return None
    db_email, senha_hash, role, nome, ativo, senha_temporaria = row
    if not ativo or not senha_hash:
        return None
    if not password or not _verify_password(password, senha_hash):
        return None
    return {
        "email": db_email,
        "role": role,
        "nome": nome,
        "senha_temporaria": bool(senha_temporaria),
    }


@app.get("/api/auth/me")
def auth_me(valbot_session: str | None = Cookie(default=None)):
    sess = _verify_session(valbot_session)
    if sess is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    # Flag por usuário lida ao vivo (não vem do cookie) — controla o botão
    # "Enviar laudos → TechPrático" na Fila Operacional.
    return {**sess, "pode_enviar_laudos": _pode_enviar_laudos(sess.get("email"))}


@app.get("/api/dashboard/kpis")
def dashboard_kpis(demo: str | None = None):
    """KPIs reais do Painel executivo (tela Dashboard).

    Lê agregações reais do banco via ``db.dashboard_kpis()`` (exams,
    exam_divergencias, exam_infractions, ordens_servico). O parâmetro ``demo``
    é aceito por compat com o frontend mas ignorado — os dados vêm sempre do
    banco. DB indisponível ou erro devolve a estrutura zerada (arrays vazios,
    totais 0/"—"), nunca 500. Shape casa com fixtures/mockKpis.ts.
    """
    zero = {
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
    try:
        data = db.dashboard_kpis()
    except Exception as e:
        log.warning("dashboard_kpis falhou: %s", e)
        data = None
    return data if data is not None else zero


@app.on_event("startup")
def _seed_admin_from_env():
    """Garante o admin definido no .env (VALBOT_ADMIN_EMAIL/VALBOT_ADMIN_PASSWORD)
    na tabela `users`, com senha em hash PBKDF2. Idempotente (cria ou atualiza a
    senha). Sem as duas vars => no-op. Nunca derruba o boot. Acesso break-glass."""
    email = (os.environ.get("VALBOT_ADMIN_EMAIL") or "").strip().lower()
    password = os.environ.get("VALBOT_ADMIN_PASSWORD") or ""
    if not email or not password:
        return
    try:
        from tooling.api_stub import db as _db

        h = _db.hash_password(password)
        with _db._conn() as c:
            if c is None:
                return
            cur = c.execute(
                "UPDATE users SET senha_hash=%s, ativo=TRUE, "
                "role=COALESCE(NULLIF(role,''), 'admin') WHERE LOWER(email)=%s",
                (h, email),
            )
            if getattr(cur, "rowcount", 0) == 0:
                c.execute(
                    "INSERT INTO users (email, senha_hash, role, nome, ativo) "
                    "VALUES (%s, %s, 'admin', %s, TRUE)",
                    (email, h, email.split("@")[0]),
                )
        log.info("seed admin: %s garantido na tabela users (via .env)", email)
    except Exception as e:
        log.warning("seed admin falhou: %s", e)


@app.get("/api/v2/dashboard")
def v2_dashboard(dias: int = 30):
    """Resumo de métricas (shape do protótipo sistema/): operacionais, regulatorios,
    custos, supervisor, compliance. Usa backend.dashboard.metrics.resumo() contra o
    banco real. Resiliente — qualquer falha devolve a estrutura zerada (nunca 500)."""
    zero = {
        "periodo_dias": int(dias),
        "operacionais": {},
        "regulatorios": {},
        "custos": {},
        "supervisor": {},
        "compliance": {},
    }
    try:
        from backend.dashboard import metrics

        res = metrics.resumo(int(dias))
    except Exception as e:
        log.warning("v2_dashboard falhou: %s", e)
        return zero
    # Concordância TechPrático(examinador) × ValBot(IA) — o regulatorios() modular
    # usa exam_divergencias (vazia em prod) e zera. Calculamos do veredito real:
    # concorda = (oficial A & IA aprovou) ou (oficial R & IA reprovou).
    try:
        rows = db.list_resultados(dias=int(dias), limit=20000) or []
        conc = comp = 0
        for r in rows:
            of = (r.get("resultado_exame") or "").strip().upper()
            ap = r.get("aprovado")
            if of in ("A", "R") and ap is not None:
                comp += 1
                if (of == "A" and ap is True) or (of == "R" and ap is False):
                    conc += 1
        if comp:
            reg = res.setdefault("regulatorios", {})
            reg["concordancia_resultado_pct"] = round(100.0 * conc / comp, 1)
            reg["comparaveis"] = comp
            reg["concordantes"] = conc
            reg["divergentes"] = comp - conc
    except Exception as e:
        log.warning("v2_dashboard concordancia falhou: %s", e)
    # Provisão: câmbio USD→BRL dinâmico (app_settings.usd_brl). Default 5.40.
    try:
        raw_usd = db.get_app_setting("usd_brl", "5.40")
        usd_brl = float(raw_usd) if raw_usd else 5.40
    except Exception:
        usd_brl = 5.40
    res.setdefault("custos", {})["usd_brl"] = usd_brl
    res["usd_brl"] = usd_brl
    return res


@app.get("/api/os")
def list_os_v2(status: str | None = None, _sess: dict = Depends(require_session)):
    """Fila de arbitragem do Supervisor. As ordens_servico formais ainda não são
    geradas pelo pipeline em prod (tabela vazia); derivamos a fila das DIVERGÊNCIAS
    reais (exame onde o veredito oficial difere do calculado pela IA), que é
    exatamente o que o supervisor arbitra. Dados 100% reais de v_exams_overview."""
    # Fila do auditor E do supervisor: vídeos a partir da data de corte, apenas
    # da categoria B (1ª habilitação — o que entra no fluxo de auditoria). Não
    # só as divergências; cada exame ganha um sinalizador de status. Corte e
    # categoria configuráveis por env; default 13/06/2026 + B (inclui a semana
    # passada — exames de 13-14/06, já com resultado oficial — além da atual).
    fila_desde = os.environ.get("VALBOT_FILA_DESDE", "2026-06-13")
    fila_categoria = os.environ.get("VALBOT_FILA_CATEGORIA", "B")
    rows = db.list_resultados(desde=fila_desde, categoria=fila_categoria, limit=2000) or []
    # "Sem vídeo disponível" NÃO entra na Operação/fila: ingestão incompleta presa
    # em status='uploading' (o caminho gs_video está gravado, mas o objeto não
    # existe no GCS — download nunca concluiu). Esses não têm o que auditar.
    rows = [r for r in rows if (r.get("status") or "").strip().lower() != "uploading"]
    items = []
    for r in rows:
        # Campos canônicos vêm da view (v_exams_overview, migration 027) — fonte
        # única. Oficial só é definitivo se A/R; None ⇒ pendente. Sem rederivar.
        of = r.get("resultado_oficial")  # 'A' | 'R' | None (None ⇒ oficial pendente)
        diverge = bool(r.get("divergente"))
        rc = r.get("resultado_calculado")
        h = r.get("hash")
        aberta_em = r.get("created_at")
        # SLA: aberta_em + prazo do auditor (default 24h). Null se sem abertura.
        sla_due_at = _add_hours(aberta_em, db.SLA_PRAZO_AUDITOR_H)
        # video_ok agora é canônico da view (migration 028); fallback p/ janela de deploy.
        video_ok = r.get("video_ok") if "video_ok" in r else _derive_video_ok(r)
        # Sinalizador de estágio de processamento do vídeo (sempre presente).
        _st = (r.get("status") or "").strip().lower()
        if r.get("gate_rejected"):
            status_proc = "gate_rejeitado"
        elif _st in ("processed", "done", "concluido", "concluído"):
            status_proc = "processado"
        elif _st in ("running", "processing", "analisando"):
            status_proc = "processando"
        elif _st in ("queued", "pending", "novo", "uploaded", "recebido"):
            status_proc = "aguardando"
        elif _st in ("failed", "error", "erro"):
            status_proc = "falhou"
        else:
            status_proc = _st or "desconhecido"
        items.append(
            {
                "os_id": h,
                "numero_os": f"OS-{(h or '')[:8].upper()}",
                "exam_hash": h,
                "renach": r.get("renach"),
                "candidato_nome": r.get("candidato_nome"),
                "candidato": _mask_cpf(r.get("candidato_cpf")),
                "categoria": r.get("categoria"),
                "unidade": r.get("local_unidade"),
                "examinador": r.get("examinador"),
                # Sem oficial definitivo (pendente) NÃO é concordante nem divergente
                # — é "Aguardando resultado oficial". Concordância só com oficial A/R.
                "tipo_divergencia": (
                    "pendente"
                    if r.get("oficial_pendente")
                    else ("resultado" if diverge else "concordante")
                ),
                "tipo_label": (
                    "Aguardando resultado oficial"
                    if r.get("oficial_pendente")
                    else ("Divergência de resultado" if diverge else "Concordante")
                ),
                "status": "aguardando_supervisor",
                "status_proc": status_proc,
                "gate_rejected": bool(r.get("gate_rejected")),
                "divergente": diverge,
                "resultado_oficial": of,
                "oficial_pendente": bool(r.get("oficial_pendente")),
                "stage": r.get("stage"),
                "resultado_calculado": rc,
                "pontuacao_oficial": None,
                "pontuacao_calculada": r.get("pontuacao_total"),
                "auditor_email": None,
                "supervisor_email": None,
                "aberta_em": aberta_em,
                "sla_due_at": sla_due_at,
                "conf": None,
                # Sinalizadores canônicos da view (migration 027) — comitê e
                # conduta agora saem do core, sem query de enriquecimento à parte.
                "conduta_inadequada": bool(r.get("conduta_inadequada")),
                "video_ok": video_ok,
                "tem_anotacoes": bool(r.get("tem_anotacoes")),
                "comite_concluido": bool(r.get("comite_concluido")),
            }
        )
    if status:
        items = [i for i in items if i["status"] == status]
    return {"count": len(items), "items": items, "source": "db"}


@app.post("/api/auth/email")
def auth_email(data: _EmailIn, response: Response):
    # Aceita email OU telefone — frontend pode mandar em `email`, `login` ou `telefone`.
    identifier = (data.login or data.email or data.telefone or "").strip().lower()
    if not identifier:
        raise HTTPException(400, "informe email ou telefone")
    if not _session_secret():
        raise HTTPException(503, "sessão indisponível (segredo não configurado)")
    # 1º acesso: usuário cadastrado e ativo, mas ainda sem senha definida.
    # Não autentica — sinaliza ao frontend pra exibir "Crie sua senha".
    row = _lookup_user(identifier)
    if row and row[4] and not row[1]:
        return {"needs_password": True, "email": row[0]}
    # Autenticação real por senha contra a tabela `users` (não mais passwordless).
    user = _auth_user(identifier, data.password)
    if user is None:
        raise HTTPException(401, "credenciais inválidas")
    email = user["email"]
    role = user["role"]
    # Senha temporária (reset do admin): senha confere, mas NÃO emitimos cookie.
    # O front recebe o sinal e força a troca antes de entrar.
    if user.get("senha_temporaria"):
        return {"must_change_password": True, "email": email}
    exp = int(time.time()) + SESSION_TTL
    response.set_cookie(
        key=SESSION_COOKIE,
        value=_sign_session(email, role, exp),
        max_age=SESSION_TTL,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return {
        "email": email,
        "role": role,
        "is_admin": role in ("admin", "supervisor"),
        "pode_enviar_laudos": _pode_enviar_laudos(email),
    }


class _LoginIn(BaseModel):
    email: str
    password: str | None = None


@app.post("/api/auth/login")
def auth_login(data: _LoginIn, response: Response):
    """Login com senha p/ o SPA (AdminLogin / login único). Reusa a auth real da
    tabela `users` (mesma de /api/auth/email); o frontend posta aqui com
    {email, password}. Resposta idêntica à do auth/email."""
    identifier = (data.email or "").strip().lower()
    if not identifier:
        raise HTTPException(400, "informe email")
    if not _session_secret():
        raise HTTPException(503, "sessão indisponível (segredo não configurado)")
    user = _auth_user(identifier, data.password)
    if user is None:
        raise HTTPException(401, "credenciais inválidas")
    email = user["email"]
    role = user["role"]
    # Senha temporária (reset do admin): senha confere, mas NÃO emitimos cookie.
    # O front recebe o sinal e força a troca antes de entrar.
    if user.get("senha_temporaria"):
        return {"must_change_password": True, "email": email}
    exp = int(time.time()) + SESSION_TTL
    response.set_cookie(
        key=SESSION_COOKIE,
        value=_sign_session(email, role, exp),
        max_age=SESSION_TTL,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return {
        "email": email,
        "role": role,
        "is_admin": role in ("admin", "supervisor"),
        "pode_enviar_laudos": _pode_enviar_laudos(email),
    }


@app.post("/api/auth/change-password")
def auth_change_password(data: _EmailIn, response: Response):
    """Troca de senha (foco: pós-reset do admin, mas também serve self-service).

    Body: {email|login|telefone, senha_atual, password}. Valida `senha_atual`
    contra o hash (401 se errada), exige `password` (nova) com >=8 chars e
    DIFERENTE da atual (422 senão). Grava a nova senha (hash compatível com o
    login), zera `senha_temporaria` e emite o cookie de sessão — entra direto.
    Mesmo shape de resposta do login. Resiliente: nunca 500 silencioso, nunca
    loga senha em claro."""
    identifier = (data.login or data.email or data.telefone or "").strip().lower()
    if not identifier:
        raise HTTPException(400, "informe email ou telefone")
    if not _session_secret():
        raise HTTPException(503, "sessão indisponível (segredo não configurado)")
    senha_atual = data.senha_atual or ""
    nova = data.password or ""
    if len(nova) < 8:
        raise HTTPException(422, "a nova senha deve ter pelo menos 8 caracteres")
    if nova == senha_atual:
        raise HTTPException(422, "a nova senha deve ser diferente da atual")
    # Valida credencial atual (autentica de fato — senha temp também confere aqui).
    user = _auth_user(identifier, senha_atual)
    if user is None:
        raise HTTPException(401, "senha atual incorreta")
    db_email = user["email"]
    role = user["role"]
    try:
        from tooling.api_stub import db as _db

        novo_hash = _db._hash_password_login(nova)  # compatível com _verify_password
        with _db._conn() as c:  # type: ignore[attr-defined]
            if c is None:
                raise HTTPException(503, "banco indisponível")
            c.execute(
                "UPDATE users SET senha_hash = %s, senha_temporaria = FALSE "
                "WHERE LOWER(email) = %s",
                (novo_hash, db_email.strip().lower()),
            )
    except HTTPException:
        raise
    except Exception as e:
        log.warning("change-password falhou (%s)", e)
        raise HTTPException(500, "não foi possível trocar a senha")
    # Sucesso → loga o usuário (mesmo cookie do login).
    exp = int(time.time()) + SESSION_TTL
    response.set_cookie(
        key=SESSION_COOKIE,
        value=_sign_session(db_email, role, exp),
        max_age=SESSION_TTL,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return {
        "email": db_email,
        "role": role,
        "is_admin": role in ("admin", "supervisor"),
        "pode_enviar_laudos": _pode_enviar_laudos(db_email),
    }


@app.post("/api/auth/set-password")
def auth_set_password(data: _EmailIn, response: Response):
    """1º acesso: usuário JÁ CADASTRADO e ativo, porém sem senha, define a
    própria senha e entra. NÃO faz reset — se o usuário já tem senha, recusa
    (deve usar login normal). Não cria conta nova: identifier precisa existir
    na tabela `users`."""
    identifier = (data.login or data.email or data.telefone or "").strip().lower()
    if not identifier:
        raise HTTPException(400, "informe email ou telefone")
    if not _session_secret():
        raise HTTPException(503, "sessão indisponível (segredo não configurado)")
    senha = data.password or ""
    if len(senha) < 8:
        raise HTTPException(400, "a senha deve ter pelo menos 8 caracteres")
    row = _lookup_user(identifier)
    if not row or not row[4]:
        # Não existe ou inativo — sem autocadastro.
        raise HTTPException(404, "usuário não encontrado ou inativo")
    db_email, senha_hash, role, nome, ativo, _senha_temp = row
    if senha_hash:
        # Já tem senha — 1º acesso não se aplica; nada de reset por aqui.
        raise HTTPException(409, "este usuário já possui senha — faça login normalmente")
    novo = _hash_password(senha)
    try:
        from tooling.api_stub import db as _db

        with _db._conn() as c:  # type: ignore[attr-defined]
            c.execute("UPDATE users SET senha_hash = %s WHERE email = %s", (novo, db_email))
    except Exception as e:
        log.warning("set-password falhou (%s)", e)
        raise HTTPException(500, "não foi possível definir a senha")
    # Senha definida → loga o usuário (mesmo cookie do auth_email).
    exp = int(time.time()) + SESSION_TTL
    response.set_cookie(
        key=SESSION_COOKIE,
        value=_sign_session(db_email, role, exp),
        max_age=SESSION_TTL,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return {
        "email": db_email,
        "role": role,
        "is_admin": role in ("admin", "supervisor"),
        "pode_enviar_laudos": _pode_enviar_laudos(db_email),
    }


@app.post("/api/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "logged_out"}


# ============================================================================
# Rubrica + hints do preset v25 (alimenta a página Regras)
# ============================================================================

GRAVIDADE_LABEL_BR = {
    "gravissima": "GRAVÍSSIMA",
    "grave": "GRAVE",
    "media": "MÉDIA",
    "leve": "LEVE",
}

_PRESET_BLOCK_RE = re.compile(
    r"^###\s+(R1020-[A-Z]+-[a-z])\b[^\n]*\n([\s\S]+?)(?=\n###\s+R1020|\n##\s+|\Z)",
    re.M,
)
_FIELD_RE = re.compile(
    r"\*\*(Definição|Visual|Áudio|Temporal|Evidência válida|Janela):\*\*\s*([^\n]+)"
)


@lru_cache(maxsize=1)
def _preset_v25_hints() -> dict[str, str]:
    """Para cada R1020-X-y no preset markdown v25, monta um hint compacto
    concatenando Definição + Visual + Áudio + Temporal. Cacheado em memória."""
    if not PRESET_V25_PATH.exists():
        return {}
    text = PRESET_V25_PATH.read_text(encoding="utf-8")
    hints: dict[str, str] = {}
    for m in _PRESET_BLOCK_RE.finditer(text):
        rid = m.group(1)
        body = m.group(2)
        parts: list[str] = []
        for label, content in _FIELD_RE.findall(body):
            parts.append(f"**{label}:** {content.strip()}")
        if parts:
            hints[rid] = "\n\n".join(parts)
    return hints


def _to_rubrica_infracao(infra, hint: str) -> dict:
    sev = infra.severidade.value
    return {
        "id": infra.id,
        "gravidade": sev,
        "gravidade_label": GRAVIDADE_LABEL_BR.get(sev, sev.upper()),
        "pontos": infra.pontos,
        "descricao": infra.descricao,
        "base_legal": infra.base_legal,
        "cameras": [c.value for c in infra.cameras_relevantes],
        "parametros": {},
        "vlm_prompt_hint": hint,
    }


@app.get("/api/rubricas/{slug:path}")
def rubrica(slug: str):
    """Devolve a rubrica completa lendo da Matriz MBEDV (tabela `exam_rules`).

    Aceita slugs `1020/2025` e `1020-2025` (path ou query-encoded). Apenas
    1.020/2025 está implementada — pipeline descontinuou 789/2020 em
    2026-04-25. As 80 infrações vêm de `exam_rules` (apenas vigentes:
    `vigencia_fim IS NULL`); códigos canônicos `Art. XXX` (CTB)."""
    slug_norm = slug.replace("-", "/")
    if "1020" not in slug_norm:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Rubrica '{slug}' não disponível neste pipeline. "
                "Apenas 1020/2025 está implementada (789/2020 descontinuada)."
            ),
        )

    LIMITE_APROVACAO = 10
    # Peso default por gravidade quando `peso` é NULL / peso_variavel.
    PESO_POR_GRAVIDADE = {"gravissima": 6, "grave": 4, "media": 2, "leve": 1}
    LABELS = dict(GRAVIDADE_LABEL_BR)
    LABELS.setdefault("variavel", "VARIÁVEL")

    cols = [
        "codigo_val",
        "artigo_ctb",
        "ficha_mbedv",
        "fonte_normativa",
        "natureza",
        "peso",
        "peso_variavel",
        "categorias_aplicaveis",
        "conduta_observavel",
        "descricao",
        "evidencia_necessaria",
        "constatacao",
        "informacoes_complementares",
        "quando_pontuar",
        "quando_nao_pontuar",
        "comentario_juridico",
    ]
    sql = (
        "SELECT "
        + ", ".join(cols)
        + " FROM exam_rules WHERE vigencia_fim IS NULL"
        + " ORDER BY created_at, codigo_val"
    )

    from tooling.api_stub import db as _db

    rows: list = []
    with _db._conn() as c:  # type: ignore[attr-defined]
        if c is None:
            raise HTTPException(503, "banco indisponível para leitura de regras")
        rows = c.execute(sql).fetchall()

    items: list[dict] = []
    for r in rows:
        d = dict(zip(cols, r))
        grav = (d.get("natureza") or "").strip().lower() or "variavel"
        codigo = d.get("artigo_ctb") or d.get("codigo_val") or "—"

        peso = d.get("peso")
        if peso is None:
            peso = PESO_POR_GRAVIDADE.get(grav)  # None se gravidade desconhecida (variavel)
        pontos = int(peso) if peso is not None else 0

        cats_raw = d.get("categorias_aplicaveis")
        if isinstance(cats_raw, str):
            try:
                cats_raw = json.loads(cats_raw)
            except Exception:
                cats_raw = [cats_raw]
        categorias = ", ".join(str(x) for x in cats_raw) if isinstance(cats_raw, list) else ""

        base_legal = d.get("fonte_normativa") or ""
        ficha = d.get("ficha_mbedv")
        if ficha:
            base_legal = (base_legal + " · ficha " + ficha) if base_legal else ("ficha " + ficha)

        definicoes = d.get("comentario_juridico") or d.get("evidencia_necessaria") or ""
        checks = d.get("quando_pontuar") or ""

        items.append(
            {
                "id": codigo,
                "codigo": codigo,
                "gravidade": grav,
                "gravidade_label": LABELS.get(grav, grav.upper()),
                "pontos": pontos,
                "descricao": d.get("descricao") or d.get("conduta_observavel") or "",
                "base_legal": base_legal,
                "categorias": categorias,
                "constatacao": d.get("constatacao") or "",
                "pontua": checks,
                "checks": checks,
                "naoPontua": d.get("quando_nao_pontuar") or "",
                "definicoes": definicoes,
                "compl": d.get("informacoes_complementares") or "",
                "cameras": [],
                "parametros": {},
                "vlm_prompt_hint": "",
            }
        )

    contagem: dict[str, int] = {}
    for it in items:
        contagem[it["gravidade"]] = contagem.get(it["gravidade"], 0) + 1

    return {
        "slug": slug_norm,
        "nome": "Resolução CONTRAN 1.020/2025",
        "limite_pontuacao": LIMITE_APROVACAO,
        "infracoes": items,
        "total_infracoes": len(items),
        "contagem_por_gravidade": contagem,
    }


@app.get("/preset/{version}/{variant}")
def get_preset(version: str, variant: str):
    """Serve preset markdown content (helper p/ upload via Chrome MCP)."""
    from fastapi.responses import PlainTextResponse

    p = (
        PROJECT_ROOT
        / "tooling"
        / "bench_demo"
        / "presets"
        / version
        / f"valbot-r1-{variant}-{version}.md"
    )
    if not p.exists():
        raise HTTPException(404, f"preset {version}/{variant} not found")
    return PlainTextResponse(p.read_text())


@app.post("/api/exams")
async def create_exam(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    candidato_nome: str = Form(""),
    candidato_cpf: str = Form(""),
    renach: str = Form(""),
    processo: str = Form(""),
    categoria: str = Form(""),
    veiculo: str = Form(""),
    local: str = Form(""),
    examinador: str = Form(""),
    auto_escola: str = Form(""),
    rubrica: str = Form("1020/2025"),
    training_annotations: str = Form(
        "[]", description="JSON serializado: array de {timestamp HH:MM:SS, anotacoes}."
    ),
):
    """Recebe upload + metadados, persiste o vídeo em `storage/analyses/<hash>/`
    e dispara `_run_analysis` em background. Retorna `analysis_id = sha256(video)`.

    O frontend faz polling em `/api/exams/{id}` até `status == "processed"`.
    """
    try:
        annotations_parsed = [
            TrainingAnnotation(**a) for a in json.loads(training_annotations or "[]")
        ]
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        raise HTTPException(422, f"training_annotations inválido: {e}") from e
    content = await file.read()
    hash_hex = hashlib.sha256(content).hexdigest()
    out_dir = ANALYSES_DIR / hash_hex
    out_dir.mkdir(parents=True, exist_ok=True)

    video_path = out_dir / (file.filename or "video.mp4")
    video_path.write_bytes(content)

    upload_meta = {
        "analysis_id": hash_hex,
        "received_at": datetime.utcnow().isoformat() + "Z",
        "video": {
            "filename": file.filename,
            "size_bytes": len(content),
            "size_mb": round(len(content) / 1024 / 1024, 2),
            "hash": hash_hex,
        },
        "candidato": {
            "nome": candidato_nome,
            "cpf": candidato_cpf,
            "renach": renach,
            "processo": processo,
            "categoria": categoria,
        },
        "exame": {
            "veiculo": veiculo,
            "local": local,
            "examinador": examinador,
            "auto_escola": auto_escola,
            "rubrica": rubrica,
        },
        "training_annotations": [a.model_dump() for a in annotations_parsed],
        "engine": {
            "backend": "vertex_gemini",
            "model": "gemini-3.1-pro-preview",
            "preset": "v25/valbot-r1-vip-v25",
        },
    }
    (out_dir / "upload.json").write_text(json.dumps(upload_meta, indent=2, ensure_ascii=False))
    _write_status(out_dir, "queued")

    print(
        f"[API] ✅ Upload recebido '{file.filename}' ({upload_meta['video']['size_mb']}MB) "
        f"→ analysis_id={hash_hex[:12]}… (mock={USE_MOCK_VLM})"
    )

    threading.Thread(
        target=_run_analysis,
        args=(hash_hex, str(video_path), upload_meta),
        daemon=True,
        name=f"analyze-{hash_hex[:8]}",
    ).start()

    return {"analysis_id": hash_hex, "status": "queued", **upload_meta}


# ============================================================================
# Upload via GCS Signed URL (Fase C — bypassa Cloudflare 100 MB e tira o
# arquivo da RAM do backend). Fluxo em 3 passos:
#
#   1. POST /api/exams/init-upload     — cria registro + devolve signed PUT URL
#   2. PUT  <signed_url>  (browser → GCS, direto, sem passar pelo backend)
#   3. POST /api/exams/{id}/finalize   — confirma blob no GCS e dispara análise
#
# `analysis_id` aqui é UUID hex (não SHA256 do vídeo) porque o backend não
# tem o conteúdo em memória. O hash real do vídeo (md5 do GCS) é registrado
# no upload.json em `finalize` e usado pra rastreabilidade/cache.
# ============================================================================


class TrainingAnnotation(BaseModel):
    """Anotação humana referenciando um momento específico do vídeo do exame.

    Usada pela skill `avaliador-detran` pra ancorar feedback do examinador
    em pontos exatos do exame. Substitui o campo texto-livre antigo.
    """

    timestamp: str = Field(
        ...,
        description="Offset dentro do vídeo no formato HH:MM:SS (ex: '00:02:35').",
        pattern=r"^([0-9]{1,2}):[0-5][0-9]:[0-5][0-9]$",
        examples=["00:02:35"],
    )
    anotacoes: str = Field(
        ...,
        min_length=1,
        description="Texto livre da anotação humana sobre o momento marcado.",
        examples=["candidato hesitou na baliza"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {"timestamp": "00:02:35", "anotacoes": "candidato hesitou na baliza"}
        }
    }


class InitUploadRequest(BaseModel):
    """Recebe vídeo via URL externa. SÓ `url` e `renach` são obrigatórios.

    O backend baixa o vídeo da URL, salva no GCS Valbot e cria registro em `exams`.
    Demais campos são metadados úteis pro laudo, todos opcionais.

    Schema legado/objeto-único — frontend (`UploadVideoModal.tsx`) ainda envia
    nesse formato. O endpoint também aceita lista de `InitUploadItem` (lote).
    """

    url: str = Field(
        ...,
        description="URL HTTPS do vídeo já hospedado externamente. Backend faz GET e copia pro GCS.",
    )
    renach: str = Field(..., min_length=1, description="RENACH/CNH do candidato")
    id: int | None = Field(
        default=None,
        description=(
            "ID externo / idAgendamento do integrador (ex.: TechPrático). Persiste em "
            "exams.external_id e é a chave para buscar o resultado oficial. Opcional."
        ),
    )
    candidato_nome: str = ""
    candidato_cpf: str = ""
    processo: str = ""
    categoria: str = Field(
        ...,
        pattern="^[A-E]$",
        description=(
            "Categoria da CNH em exame. OBRIGATÓRIO, atrelado a cada vídeo/teste. "
            "Aceita apenas uma categoria de habilitação brasileira simples (maiúscula): "
            "A, B, C, D ou E. Qualquer outro valor → 422."
        ),
    )
    veiculo: str = ""
    local: str = ""
    examinador: str = ""
    auto_escola: str = ""
    rubrica: str = "1020/2025"
    training_annotations: list[TrainingAnnotation] = Field(
        default_factory=list,
        description="Lista de anotações humanas ancoradas em timestamps do vídeo. Cada item exige `timestamp` no formato `HH:MM:SS` e `anotacoes` não vazio. Itens inválidos → 422.",
        examples=[
            [
                {"timestamp": "00:02:35", "anotacoes": "candidato hesitou na baliza"},
                {"timestamp": "00:04:10", "anotacoes": "não olhou retrovisor antes da troca"},
            ]
        ],
    )
    resultado_exame: str | None = Field(
        default=None,
        description="Veredito presencial do examinador. 'A'=Aprovado, 'R'=Reprovado, 'N'=Não Avaliado (exame interrompido/desistência), omitir/null=não informado.",
        pattern="^[ARN]$",
        max_length=1,
    )


class InitUploadItem(BaseModel):
    """Item de lote no `POST /api/exams/init-upload` (shape novo p/ integradores).

    Schema enxuto pra integradores externos (DETRAN, autoescolas) que mandam
    array. Campos `candidato_*` e `exame_*` ficam em iteração 2 — hoje o JSON
    de upload guarda só `renach`/`processo`/`categoria`/`external_id` no lote.
    """

    url: str = Field(..., description="URL HTTPS do vídeo. Backend baixa em background pro GCS.")
    categoria: str = Field(
        ...,
        pattern="^[A-E]$",
        description=(
            "Categoria da CNH em exame. OBRIGATÓRIO, atrelado a cada vídeo/teste do lote. "
            "Aceita apenas uma categoria de habilitação brasileira simples (maiúscula): "
            "A, B, C, D ou E. Qualquer outro valor → 422."
        ),
    )
    id: int | None = Field(
        default=None,
        description="ID externo (ex: 784562 do DETRAN). Persiste em exams.external_id.",
    )
    renach: str = Field(..., min_length=1, description="RENACH/CNH do candidato")
    processo: int | str | None = Field(
        default=None, description="Número do processo (integer ou string)."
    )
    training_annotations: list[TrainingAnnotation] = Field(
        default_factory=list,
        description="Lista de anotações humanas ancoradas em timestamps do vídeo. Cada item exige `timestamp` no formato `HH:MM:SS` e `anotacoes` não vazio. Itens inválidos → 422.",
        examples=[
            [
                {"timestamp": "00:02:35", "anotacoes": "candidato hesitou na baliza"},
                {"timestamp": "00:04:10", "anotacoes": "não olhou retrovisor antes da troca"},
            ]
        ],
    )
    resultado_exame: str | None = Field(
        default=None,
        description="Veredito presencial. 'A'=Aprovado, 'R'=Reprovado, 'N'=Não Avaliado, null=não informado.",
        pattern="^[ARN]$",
        max_length=1,
    )


# Tipo união aceito pelo handler init_upload: objeto único (compat) OU lista (lote).
InitUploadPayload = InitUploadRequest | list[InitUploadItem]


# Limite duro de itens por lote — protege contra DoS acidental (HEAD x 50 já
# é 50s de blocking). Integrador deve paginar acima disso.
MAX_BATCH_SIZE = 50

# Limite global de downloads concorrentes em background. VM e2-standard-2 = 2
# vCPU + 8GB RAM, vídeo até 600MB pro tempfile. 3 simultâneos = ~1.8GB de
# /tmp no pior caso, ainda confortável.
MAX_CONCURRENT_DOWNLOADS = 3


@lru_cache(maxsize=1)
def _download_semaphore() -> asyncio.Semaphore:
    """Singleton lazy do semáforo — instanciado no event-loop do FastAPI."""
    return asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)


class FinalizeRequest(BaseModel):
    sha256_client: str | None = None


def _gcs_client():
    """Lazy import — só carrega google-cloud-storage quando necessário."""
    from google.cloud import storage as _storage

    return _storage.Client()


def _signing_creds():
    """Devolve (service_account_email, access_token) para gerar V4 signed URLs
    em ambientes onde a credential ativa não expõe private key (Compute Engine,
    Cloud Run, GKE Workload Identity). Requer que o SA ativo tenha
    `roles/iam.serviceAccountTokenCreator` em si mesmo."""
    from google.auth import default as _default
    from google.auth.transport import requests as _auth_requests

    credentials, _ = _default()
    credentials.refresh(_auth_requests.Request())
    sa_email = getattr(credentials, "service_account_email", None) or os.environ.get(
        "GCS_SIGNER_EMAIL"
    )
    if not sa_email:
        raise RuntimeError(
            "Service account email não disponível na credential ativa. "
            "Defina GCS_SIGNER_EMAIL no ambiente."
        )
    return sa_email, credentials.token


def _validate_url_video(url: str) -> tuple[str, int]:
    """No-op: aceita a URL como veio. O download em background é quem descobre
    se a URL responde; aqui só devolvemos default pro caller."""
    return "video/mp4", 0


def _is_aws_s3_url(url: str) -> bool:
    """Detecta URL S3 — bucket privado AWS exige autenticação SigV4 (boto3).
    Cobre o padrão virtual-hosted-style (`<bucket>.s3.amazonaws.com`),
    path-style (`s3.amazonaws.com/<bucket>`) e regional (`s3-region.amazonaws.com`).
    """
    if not url:
        return False
    u = url.lower()
    return "amazonaws.com" in u or u.startswith("s3://")


def _stream_url_to_gcs(url: str, blob) -> int:
    """Baixa o vídeo da URL externa e sobe pro GCS. Retorna size escrito.

    Roteamento:
      • URL AWS S3 (privada) → boto3 com AWS_ACCESS_KEY/SECRET do env
        (autenticação SigV4 via assinatura). Senão estoura 403 em bucket privado.
      • Qualquer outra URL → httpx anônimo (presigned URL, GCS público,
        signed URL avulsa, etc — auth já vem na própria URL ou bucket é público).

    O fix do roteamento mata o erro 403 do techpratico (problema do briefing).
    """
    import tempfile

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp_path = tmp.name

        if _is_aws_s3_url(url):
            # AWS S3: precisa SigV4. Parseia bucket+key, usa boto3.
            from urllib.parse import unquote, urlparse

            import boto3

            parsed = urlparse(url)
            host = parsed.hostname or ""
            path = unquote(parsed.path.lstrip("/"))
            if url.lower().startswith("s3://"):
                bucket = host
                key = path
            elif host.startswith("s3.") or host.startswith("s3-"):
                # path-style: s3.amazonaws.com/<bucket>/<key>
                parts = path.split("/", 1)
                bucket, key = (parts[0], parts[1] if len(parts) > 1 else "")
            else:
                # virtual-hosted-style: <bucket>.s3.amazonaws.com/<key>
                bucket = host.split(".s3", 1)[0]
                key = path
            log.info("S3 download via boto3: bucket=%s key=%s", bucket, key[:80])
            s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
            s3.download_file(bucket, key, tmp_path)
            ct = "video/mp4"  # boto3 não devolve content-type fácil; default seguro
        else:
            # Não-AWS: httpx anônimo (URL já é pública ou tem token na própria URL)
            import httpx

            with httpx.Client(follow_redirects=True, timeout=600.0) as c, c.stream("GET", url) as r:
                r.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=8 * 1024 * 1024):
                        f.write(chunk)
                ct = (r.headers.get("content-type") or "video/mp4").split(";")[0].strip()

        size = os.path.getsize(tmp_path)
        blob.upload_from_filename(tmp_path, content_type=ct)
        return size
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _ext_for(ct: str) -> str:
    """Mapeia content-type aceito pra extensão do blob no GCS."""
    return ".mp4" if ct == "video/mp4" else (".mov" if ct == "video/quicktime" else ".m4v")


def _build_meta_legacy(req: InitUploadRequest, analysis_id: str, ct: str, blob_name: str) -> dict:
    """Constrói upload.json no formato rico (legado/objeto-único)."""
    return {
        "analysis_id": analysis_id,
        # idAgendamento do integrador — chave p/ buscar o resultado oficial no TechPrático.
        "external_id": req.id,
        # Payload BRUTO completo recebido — nunca mais perder campo que o integrador mande.
        "raw": req.model_dump(mode="json"),
        "received_at": datetime.utcnow().isoformat() + "Z",
        "video": {
            "source_url": req.url,
            "size_bytes": None,
            "size_mb": None,
            "gs_path": f"gs://{GCS_BUCKET}/{blob_name}",
            "content_type": ct,
        },
        "candidato": {
            "nome": req.candidato_nome,
            "cpf": req.candidato_cpf,
            "renach": req.renach,
            "processo": req.processo,
            "categoria": req.categoria,
        },
        "exame": {
            "veiculo": req.veiculo,
            "local": req.local,
            "examinador": req.examinador,
            "auto_escola": req.auto_escola,
            "rubrica": req.rubrica,
        },
        "training_annotations": [a.model_dump() for a in req.training_annotations],
        # Veredito presencial do examinador (vem da integração — COFRE imutável).
        "resultado_exame": req.resultado_exame,
        "engine": {
            "backend": "vertex_gemini",
            "model": "gemini-3.1-pro-preview",
            "preset": "v25/valbot-r1-vip-v25",
        },
    }


def _build_meta_batch(item: InitUploadItem, analysis_id: str, ct: str, blob_name: str) -> dict:
    """Constrói upload.json no formato enxuto (lote — só campos do schema novo)."""
    return {
        "analysis_id": analysis_id,
        "received_at": datetime.utcnow().isoformat() + "Z",
        "video": {
            "source_url": item.url,
            "size_bytes": None,
            "size_mb": None,
            "gs_path": f"gs://{GCS_BUCKET}/{blob_name}",
            "content_type": ct,
        },
        "candidato": {
            "nome": "",
            "cpf": "",
            "renach": item.renach,
            "processo": "" if item.processo is None else str(item.processo),
            "categoria": item.categoria,
        },
        "exame": {
            "veiculo": "",
            "local": "",
            "examinador": "",
            "auto_escola": "",
            "rubrica": "1020/2025",
        },
        "training_annotations": [a.model_dump() for a in item.training_annotations],
        "external_id": item.id,
        # Payload BRUTO completo do item recebido — paridade com _build_meta_legacy.
        # Nunca mais perder campo que o integrador mande (idAgendamento, etc.).
        "raw": item.model_dump(mode="json"),
        # Veredito presencial do examinador (vem da integração — COFRE imutável).
        "resultado_exame": item.resultado_exame,
        "engine": {
            "backend": "vertex_gemini",
            "model": "gemini-3.1-pro-preview",
            "preset": "v25/valbot-r1-vip-v25",
        },
    }


async def _download_one_async(
    url: str, analysis_id: str, blob_name: str, upload_meta: dict
) -> None:
    """Background: baixa URL→GCS sob semáforo global, promove status uploading→queued,
    dispara `_run_analysis` em thread. Erros marcam status `failed` em status.json.
    """
    sem = _download_semaphore()
    out_dir = ANALYSES_DIR / analysis_id
    async with sem:
        try:
            client = _gcs_client()
            bucket = client.bucket(GCS_BUCKET)
            blob = bucket.blob(blob_name)
            actual_size = await asyncio.to_thread(_stream_url_to_gcs, url, blob)

            if actual_size > MAX_UPLOAD_SIZE_BYTES:
                try:
                    await asyncio.to_thread(blob.delete)
                except Exception:
                    pass
                raise RuntimeError(f"Vídeo baixado excedeu limite ({actual_size} bytes)")

            # atualiza upload.json com o tamanho real + promove status
            upload_meta["video"]["size_bytes"] = actual_size
            upload_meta["video"]["size_mb"] = round(actual_size / 1024 / 1024, 2)
            upload_meta["video"]["downloaded_at"] = datetime.utcnow().isoformat() + "Z"
            (out_dir / "upload.json").write_text(
                json.dumps(upload_meta, indent=2, ensure_ascii=False)
            )
            _write_status(out_dir, "queued")
            db.update_status(analysis_id, "queued")

            log.info(
                "download done analysis_id=%s size_mb=%s — dispatching analysis",
                analysis_id[:12],
                upload_meta["video"]["size_mb"],
            )

            threading.Thread(
                target=_run_analysis,
                args=(analysis_id, f"gs://{GCS_BUCKET}/{blob_name}", upload_meta),
                daemon=True,
                name=f"analyze-{analysis_id[:8]}",
            ).start()
        except Exception as e:
            log.exception("download failed analysis_id=%s", analysis_id[:12])
            _write_status(out_dir, "failed", error=f"download: {e}")
            db.update_status(analysis_id, "failed")


def _prepare_one(item: InitUploadItem, *, legacy_req: InitUploadRequest | None = None) -> dict:
    """Valida HEAD da URL + cria registro 'uploading' + retorna ficha pro response e pro task.

    Lança {error: str, external_id: int|None} via raise via HTTPException p/ erro
    de URL — chamador captura e devolve no array de resposta como item de erro.
    """
    ct, _declared = _validate_url_video(item.url)
    analysis_id = uuid.uuid4().hex
    blob_name = f"{GCS_UPLOAD_PREFIX}/{analysis_id}/video{_ext_for(ct)}"

    upload_meta = (
        _build_meta_legacy(legacy_req, analysis_id, ct, blob_name)
        if legacy_req is not None
        else _build_meta_batch(item, analysis_id, ct, blob_name)
    )

    out_dir = ANALYSES_DIR / analysis_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "upload.json").write_text(json.dumps(upload_meta, indent=2, ensure_ascii=False))
    _invalidate_source_url_cache(analysis_id)
    _write_status(out_dir, "uploading")

    db.insert_exam(
        analysis_id,
        analysis_id,
        upload_meta,
        f"gs://{GCS_BUCKET}/{blob_name}",
        external_id=item.id,
        initial_status="uploading",
    )

    return {
        "analysis_id": analysis_id,
        "blob_name": blob_name,
        "upload_meta": upload_meta,
        "url": item.url,
        "external_id": item.id,
    }


@app.post("/api/exams/init-upload")
async def init_upload(
    background: BackgroundTasks,
    body: InitUploadPayload = Body(
        ..., description="Objeto único (legado) ou array de itens (lote)."
    ),
    _auth: dict = Depends(require_api_key("exams:create")),
):
    """Recebe URL externa do vídeo + renach + metadados.

    **Dois shapes aceitos:**

    * **Objeto único** (legado, compat com frontend): retorna `{analysis_id, status, gs_path}`.
    * **Array** (lote, até 50 itens) `[{url, categoria, id, renach, processo}]`: retorna lista
      `[{external_id, analysis_id, status, gs_path?, error?}]` na **mesma ordem** do request.

    `categoria` (A|B|C|D|E) é **obrigatória** em ambos os shapes, atrelada a cada vídeo/teste.

    O download da URL pro GCS roda em **background** (até 3 simultâneos). Resposta
    chega em <1s mesmo com vídeos grandes. Status segue `uploading → queued →
    running → processed`/`failed`. Use `GET /api/exams/{analysis_id}` pra polling.
    """
    is_batch = isinstance(body, list)
    legacy_req = body if isinstance(body, InitUploadRequest) else None

    if is_batch:
        if len(body) == 0:
            raise HTTPException(422, "Lote vazio.")
        if len(body) > MAX_BATCH_SIZE:
            raise HTTPException(422, f"Lote excede {MAX_BATCH_SIZE} itens (recebeu {len(body)}).")
        items: list[InitUploadItem] = list(body)
    else:
        items = [
            InitUploadItem(
                url=legacy_req.url,
                categoria=legacy_req.categoria,
                id=legacy_req.id,
                renach=legacy_req.renach,
                processo=legacy_req.processo or None,
            )
        ]

    results: list[dict] = []
    for item in items:
        try:
            prepared = _prepare_one(item, legacy_req=legacy_req if not is_batch else None)
        except HTTPException as e:
            # URL inválida/inacessível — registra erro per-item, segue o lote.
            log.warning(
                "init-upload item rejeitado: external_id=%s renach=%s err=%s",
                item.id,
                _mask_renach(item.renach),
                e.detail,
            )
            results.append(
                {
                    "external_id": item.id,
                    "renach": item.renach,
                    "analysis_id": None,
                    "status": "error",
                    "error": str(e.detail),
                }
            )
            continue

        background.add_task(
            _download_one_async,
            prepared["url"],
            prepared["analysis_id"],
            prepared["blob_name"],
            prepared["upload_meta"],
        )
        log.info(
            "init-upload queued analysis_id=%s external_id=%s renach=%s",
            prepared["analysis_id"][:12],
            prepared["external_id"],
            _mask_renach(item.renach),
        )
        results.append(
            {
                "external_id": prepared["external_id"],
                "renach": item.renach,
                "analysis_id": prepared["analysis_id"],
                "status": "uploading",
                "gs_path": f"gs://{GCS_BUCKET}/{prepared['blob_name']}",
            }
        )

    if is_batch:
        return results
    # Shape legado: devolver objeto único (frontend antigo nem percebe a mudança).
    r0 = results[0]
    if r0["status"] == "error":
        raise HTTPException(422, r0["error"])
    return {
        "analysis_id": r0["analysis_id"],
        "status": r0["status"],
        "gs_path": r0["gs_path"],
    }


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["exams:create"])


@app.post("/api/admin/api-keys")
def admin_create_api_key(req: CreateApiKeyRequest, _admin: None = Depends(require_admin_token)):
    """Cria nova API key. Retorna `key` plaintext UMA VEZ — armazenar agora, não dá pra recuperar."""
    try:
        key_id, raw = db.create_api_key(req.name, req.scopes)
    except Exception as e:
        raise HTTPException(409 if "duplicate" in str(e).lower() else 500, str(e)) from e
    return {
        "id": key_id,
        "name": req.name,
        "scopes": req.scopes,
        "key": raw,
        "warning": "Esta key não será mostrada novamente. Salve agora.",
    }


@app.post("/api/exams/{analysis_id}/finalize", deprecated=True)
def finalize_upload(
    analysis_id: str,
    req: FinalizeRequest,
    background: BackgroundTasks,
    response: Response,
    _auth: dict = Depends(require_api_key("exams:create")),
):
    """**DEPRECATED** — desde que `init-upload` passou a baixar a URL pro GCS
    em background, `finalize` virou no-op idempotente. Mantido pra compat com
    integradores antigos que ainda chamam após signed-URL PUT.

    Continua válido: confirma blob no GCS + dispara análise se ainda não rodou.
    Idempotente: se já está `queued`/`running`/`processed`, retorna sem
    re-disparar. Se ainda está `uploading`, valida `blob.exists()` e o tamanho
    bate com `size_bytes` declarado no init-upload.
    """
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Wed, 31 Dec 2026 23:59:59 GMT"
    response.headers["Link"] = '</api/exams/init-upload>; rel="successor-version"'
    out_dir = ANALYSES_DIR / analysis_id
    upload_path = out_dir / "upload.json"
    if not upload_path.exists():
        raise HTTPException(404, f"analysis_id {analysis_id} não encontrado")

    upload_meta = json.loads(upload_path.read_text())
    current_status = _read_status(out_dir)
    if current_status in ("queued", "running", "processed", "processed_no_pdf"):
        return {"analysis_id": analysis_id, "status": current_status, "idempotent": True}

    gs_path = upload_meta.get("video", {}).get("gs_path")
    if not gs_path or not gs_path.startswith("gs://"):
        raise HTTPException(500, "upload.json sem gs_path — registro corrompido")
    blob_name = gs_path[len(f"gs://{GCS_BUCKET}/") :]

    try:
        bucket = _gcs_client().bucket(GCS_BUCKET)
        blob = bucket.blob(blob_name)
        blob.reload()
    except Exception as e:
        log.exception("blob.reload failed for %s", analysis_id[:12])
        raise HTTPException(404, f"Vídeo não encontrado em GCS ({gs_path}): {e}") from e

    expected_size = upload_meta.get("video", {}).get("size_bytes")
    if expected_size and blob.size and blob.size != expected_size:
        raise HTTPException(
            422,
            f"Tamanho do blob ({blob.size}) difere do declarado ({expected_size}) — upload incompleto?",
        )

    upload_meta["video"]["hash"] = blob.md5_hash
    upload_meta["video"]["actual_size_bytes"] = blob.size
    upload_meta["video"]["finalized_at"] = datetime.utcnow().isoformat() + "Z"
    if req.sha256_client:
        upload_meta["video"]["sha256_client"] = req.sha256_client
    upload_path.write_text(json.dumps(upload_meta, indent=2, ensure_ascii=False))
    _write_status(out_dir, "queued")

    db.update_status(analysis_id, "queued", gs_video=gs_path)

    log.info(
        "finalize analysis_id=%s blob_size=%s md5=%s",
        analysis_id[:12],
        blob.size,
        (blob.md5_hash or "")[:12],
    )

    background.add_task(_run_analysis, analysis_id, gs_path, upload_meta)
    return {"analysis_id": analysis_id, "status": "queued", "gs_path": gs_path}


@app.get("/api/exams/{analysis_id}")
def get_exam(analysis_id: str):
    """Lê metadados + status atual da análise. O frontend faz polling aqui."""
    out_dir = ANALYSES_DIR / analysis_id
    upload = out_dir / "upload.json"
    if not upload.exists():
        # fallback pro caminho legado (analyses_demo)
        legacy = STORAGE / analysis_id / "upload.json"
        if legacy.exists():
            return json.loads(legacy.read_text())
        raise HTTPException(404, f"analysis_id {analysis_id} não encontrado")
    payload = json.loads(upload.read_text())
    payload["status"] = _read_status(out_dir)
    result_path = out_dir / "result.json"
    pdf_path = out_dir / "laudo.pdf"
    if result_path.exists():
        payload["has_result"] = True
        payload["result_url"] = f"/api/exams/{analysis_id}/result"
    if pdf_path.exists():
        payload["has_pdf"] = True
        payload["pdf_url"] = f"/api/laudo/{analysis_id}/pdf"
    return payload


@app.get("/api/exams/{analysis_id}/result")
def get_exam_result(analysis_id: str):
    """Retorna o JSON normalizado da análise (timeline + infrações + layout).

    Resiliente: result.json ausente, vazio ou corrompido devolve 404 (não 500).
    Esses casos (ex.: análise que falhou no meio) serão regenerados quando o
    exame for reprocessado.
    """
    f = ANALYSES_DIR / analysis_id / "result.json"
    if not f.exists():
        raise HTTPException(404, f"result.json não disponível para {analysis_id}")
    try:
        txt = f.read_text()
        if not txt.strip():
            raise ValueError("result.json vazio")
        return json.loads(txt)
    except HTTPException:
        raise
    except Exception as e:
        log.warning("result.json inválido para %s: %s", analysis_id[:12], e)
        raise HTTPException(404, f"result.json inválido para {analysis_id}")


@app.get("/api/laudo/{hash}/pdf")
def get_laudo_pdf(hash: str, request: Request):
    """Serve o PDF do laudo gerado pelo pipeline."""
    f = ANALYSES_DIR / hash / "laudo.pdf"
    if not f.exists():
        raise HTTPException(404, f"laudo.pdf ainda não gerado para {hash}")
    _actor, _ip = _actor_ip(request)
    db.log_access(hash, _actor, _ip, action="read_laudo_pdf")
    return FileResponse(
        path=str(f),
        media_type="application/pdf",
        filename=f"laudo-{hash[:12]}.pdf",
    )


@app.get("/api/exams/{analysis_id}/video")
def get_exam_video(analysis_id: str, request: Request, background: BackgroundTasks):
    """Streama o vídeo do exame com 3 níveis de cache:

      1. **Disco local** — se já foi baixado (storage/analyses/{hash}/video.mp4),
         serve direto via FileResponse (Range nativo, ~100 MB/s).
      2. **Cloudflare CDN** — Cache-Control: public, max-age=86400, immutable.
         Próximos acessos pela mesma URL+Range vêm do edge da Cloudflare (~10ms).
      3. **GCS** — primeira request pega o blob com chunks de 8 MiB E
         agenda um background-task pra clonar o arquivo inteiro pra disco
         local (subsequentes ficam no caso #1, muito mais rápido).

    O hash UUID atua como token de acesso por obscuridade — não vaza em URL
    pública sem login.
    """
    from fastapi.responses import StreamingResponse

    # Trilha de auditoria de leitura (LGPD §17.2): quem/quando/IP acessou o vídeo.
    _actor, _ip = _actor_ip(request)
    db.log_access(analysis_id, _actor, _ip, action="read_video")

    CDN_HEADERS = {
        # Cloudflare e browsers cacheiam por 24h. immutable = não revalida.
        "Cache-Control": "public, max-age=86400, immutable",
        # Permite browser fazer Range requests sem retry.
        "Accept-Ranges": "bytes",
    }

    # 1) Tenta o cache local primeiro (mais rápido)
    local = ANALYSES_DIR / analysis_id / "video.mp4"
    if local.exists():
        return FileResponse(
            path=str(local),
            media_type="video/mp4",
            headers=CDN_HEADERS,
        )

    # 2) Cai no GCS via gs_path do result.json/upload.json
    result_path = ANALYSES_DIR / analysis_id / "result.json"
    upload_path = ANALYSES_DIR / analysis_id / "upload.json"
    gs_uri = None
    for src in (result_path, upload_path):
        if src.exists():
            try:
                doc = json.loads(src.read_text())
                # result.json schema: {"video": {"gs_uri": "...", "gs_path": "..."}}
                # upload.json schema: {"gs_path": "..."}
                v = doc.get("video") if isinstance(doc, dict) else None
                gs_uri = (v or {}).get("gs_uri") or (v or {}).get("gs_path") or doc.get("gs_path")
                if gs_uri:
                    break
            except Exception:
                continue

    if not gs_uri:
        raise HTTPException(404, f"vídeo não encontrado para {analysis_id} (nem local nem GCS)")
    if not gs_uri.startswith("gs://"):
        raise HTTPException(500, f"gs_uri inválido: {gs_uri}")

    # Extrai bucket + blob name de gs://bucket/path/to/blob
    rest = gs_uri[len("gs://") :]
    bucket_name, _, blob_name = rest.partition("/")
    if not bucket_name or not blob_name:
        raise HTTPException(500, f"gs_uri malformado: {gs_uri}")

    client = _gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.reload()  # popula size + content_type

    size = blob.size or 0
    if size == 0:
        raise HTTPException(404, f"vídeo vazio no GCS: {gs_uri}")

    # Parse Range header pra suportar seek do HTML5 video player.
    range_header = request.headers.get("range") or request.headers.get("Range")
    start, end = 0, size - 1
    status = 200
    if range_header and range_header.startswith("bytes="):
        try:
            spec = range_header[len("bytes=") :].strip()
            s, _, e = spec.partition("-")
            start = int(s) if s else 0
            end = int(e) if e else size - 1
            end = min(end, size - 1)
            if start > end or start < 0:
                raise ValueError("bad range")
            status = 206
        except Exception:
            start, end, status = 0, size - 1, 200

    def chunker():
        # Download chunk-by-chunk. 8 MiB equilibra throughput (menos
        # round-trips pra GCS) sem inchar a memória do worker.
        CHUNK = 8 << 20
        cur = start
        while cur <= end:
            stop = min(cur + CHUNK - 1, end)
            data = blob.download_as_bytes(start=cur, end=stop)
            if not data:
                break
            yield data
            cur = stop + 1

    headers = {
        "Content-Length": str(end - start + 1),
        **CDN_HEADERS,
    }
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    # Background: clona o blob inteiro pra disco local pra próximas
    # requests serem direto-FileResponse. Só dispara se ainda não tem.
    def warm_local_cache():
        try:
            if local.exists():
                return
            local.parent.mkdir(parents=True, exist_ok=True)
            tmp = local.with_suffix(".mp4.partial")
            blob.download_to_filename(str(tmp))
            tmp.rename(local)
        except Exception:
            # cache miss não bloqueia requests — silencioso.
            pass

    background.add_task(warm_local_cache)

    return StreamingResponse(
        chunker(),
        status_code=status,
        media_type=blob.content_type or "video/mp4",
        headers=headers,
    )


def _local_video_for(analysis_id: str) -> Path | None:
    """Resolve o MP4 local de um exame reusando a convenção do endpoint /video.

    Procura storage/analyses/{hash}/video.mp4 e, em fallback, o primeiro *.mp4
    do diretório (uploads legados com nome de arquivo original). Não baixa do
    GCS — a timeline só opera sobre o cache local já materializado pelo player.
    Devolve None se nada existir.
    """
    base = ANALYSES_DIR / analysis_id
    local = base / "video.mp4"
    if local.exists() and local.is_file():
        return local
    if base.exists():
        for cand in sorted(base.glob("*.mp4")):
            if cand.is_file():
                return cand
    return None


@app.get("/api/exams/{hash}/thumbnails")
def get_exam_thumbnails(hash: str, n: int = 48):
    """Filmstrip: N miniaturas JPEG (data URLs) uniformemente espaçadas no vídeo.

    `{"n": N, "frames": ["data:image/jpeg;base64,...", ...]}`. Cacheia em
    storage/analyses/{hash}/thumbnails_{n}.json (gera 1x, reusa). Limite n<=120.
    Sempre 200; lista vazia se vídeo ausente, ffmpeg indisponível ou erro.
    """
    EMPTY = {"n": 0, "frames": []}
    try:
        n = max(1, min(int(n), 120))
    except Exception:
        return EMPTY

    cache = ANALYSES_DIR / hash / f"thumbnails_{n}.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except Exception:
            pass  # cache corrompido — regenera

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return EMPTY

    video = _local_video_for(hash)
    if not video:
        return EMPTY

    try:
        # Duração via ffprobe pra distribuir N frames uniformemente.
        dur_out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        duration = float((dur_out.stdout or "").strip() or 0.0)
        if duration <= 0:
            return EMPTY

        frames: list[str] = []
        # Centro de cada bucket: ts = dur * (i + 0.5) / n.
        for i in range(n):
            ts = duration * (i + 0.5) / n
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-ss",
                    f"{ts:.3f}",
                    "-i",
                    str(video),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=80:-1",
                    "-q:v",
                    "12",  # qualidade baixa (1=melhor..31=pior) → JPEG pequeno
                    "-f",
                    "image2pipe",
                    "-vcodec",
                    "mjpeg",
                    "pipe:1",
                ],
                capture_output=True,
                timeout=30,
            )
            if proc.returncode != 0 or not proc.stdout:
                continue
            b64 = base64.b64encode(proc.stdout).decode("ascii")
            frames.append(f"data:image/jpeg;base64,{b64}")

        result = {"n": len(frames), "frames": frames}
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(result))
        except Exception:
            pass  # cache best-effort
        return result
    except Exception as e:  # noqa: BLE001
        log.warning("thumbnails falhou para %s: %s", hash, e)
        return EMPTY


@app.get("/api/exams/{hash}/waveform")
def get_exam_waveform(hash: str, buckets: int = 400):
    """Waveform: peaks de áudio normalizados 0..1 em `buckets` baldes.

    `{"buckets": K, "peaks": [0.0..1.0, ...]}`. Decodifica o áudio pra PCM
    s16le mono 8kHz via ffmpeg, fatia em buckets baldes e pega o pico (|amp|)
    de cada. Cacheia em storage/analyses/{hash}/waveform_{buckets}.json.
    Limite buckets<=2000. Sempre 200; lista vazia em qualquer falha.
    """
    EMPTY = {"buckets": 0, "peaks": []}
    try:
        buckets = max(1, min(int(buckets), 2000))
    except Exception:
        return EMPTY

    cache = ANALYSES_DIR / hash / f"waveform_{buckets}.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except Exception:
            pass

    if not shutil.which("ffmpeg"):
        return EMPTY

    video = _local_video_for(hash)
    if not video:
        return EMPTY

    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(video),
                "-ac",
                "1",
                "-ar",
                "8000",
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                "pipe:1",
            ],
            capture_output=True,
            timeout=120,
        )
        if proc.returncode != 0 or not proc.stdout:
            return EMPTY

        raw = proc.stdout
        # s16le little-endian → array de int16. (len par garantido pelo formato.)
        import array

        samples = array.array("h")
        usable = len(raw) - (len(raw) % 2)
        samples.frombytes(raw[:usable])
        total = len(samples)
        if total == 0:
            return EMPTY

        peaks: list[float] = []
        per = total / buckets
        for b in range(buckets):
            lo = int(b * per)
            hi = int((b + 1) * per) if b < buckets - 1 else total
            if hi <= lo:
                peaks.append(0.0)
                continue
            peak = 0
            for s in samples[lo:hi]:
                a = -s if s < 0 else s
                if a > peak:
                    peak = a
            peaks.append(peak / 32768.0)

        result = {"buckets": len(peaks), "peaks": peaks}
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(result))
        except Exception:
            pass
        return result
    except Exception as e:  # noqa: BLE001
        log.warning("waveform falhou para %s: %s", hash, e)
        return EMPTY


def _enqueue_reanalysis(
    analysis_id: str, background: BackgroundTasks, force_v26: bool = False
) -> dict:
    """Resolve o vídeo de um exame e enfileira a (re)análise. Reusado pelo
    endpoint individual (/reanalyze) e pelo lote (/process-pending).

    Aceita uploads do fluxo legado (vídeo em disco local) e do fluxo signed
    URL (vídeo em `gs://...`). Procura primeiro o `gs_path`; se não existir,
    cai no path local. Levanta HTTPException quando não há vídeo recuperável.
    """
    out_dir = ANALYSES_DIR / analysis_id
    upload = out_dir / "upload.json"
    if not upload.exists():
        raise HTTPException(404, f"analysis_id {analysis_id} não encontrado")
    upload_meta = json.loads(upload.read_text())

    # Reanálise LIMPA: zera resultado + apaga infrações/validações ANTES de
    # re-rodar. Sem isso as infrações antigas sobrevivem (upsert_infractions é
    # ON CONFLICT DO NOTHING e nunca deleta) e corrompem a pontuação recomputada
    # — uma regra que DEIXA de marcar uma falta não removia a linha velha, então
    # o exame continuava reprovado mesmo com result.json novo aprovando.
    try:
        db.reset_exam_derivatives(analysis_id)
    except Exception:
        log.exception("reset_exam_derivatives falhou no reenqueue de %s", analysis_id)

    gs_path = upload_meta.get("video", {}).get("gs_path")
    if gs_path:
        video_ref = gs_path
    else:
        video_name = upload_meta.get("video", {}).get("filename", "video.mp4")
        video_path = out_dir / video_name
        if not video_path.exists():
            candidates = list(out_dir.glob("*.mp4"))
            if not candidates:
                raise HTTPException(
                    500, "vídeo original não encontrado (sem gs_path nem arquivo em disco)"
                )
            video_path = candidates[0]
        video_ref = str(video_path)

    _write_status(out_dir, "queued")
    background.add_task(_run_analysis, analysis_id, video_ref, upload_meta, force_v26)
    return {"analysis_id": analysis_id, "status": "queued", "video_ref": video_ref}


def _buscar_resultado_techpratico(hash_: str) -> dict:
    """Busca o resultado OFICIAL do exame no TechPrático (inbound) e persiste.

    POST /conversao/dados-exame-analise-ia {idAgendamento=external_id, id_analise=hash}.
    Salva `resultado_exame` (cofre — COALESCE, nunca apaga) + `training_annotations`
    em `exams`. Devolve o status por exame (ok | sem_idagendamento | erro*).
    """
    import urllib.error
    import urllib.request

    # Lê o external_id (idAgendamento) via _conn() — db não tem fetch_one.
    with db._conn() as _c:  # type: ignore[attr-defined]
        if _c is None:
            return {"hash": hash_, "status": "db_off"}
        _r = _c.execute("SELECT external_id FROM exams WHERE hash = %s", (hash_,)).fetchone()
    if _r is None:
        return {"hash": hash_, "status": "nao_encontrado"}
    ext = _r[0]
    if not ext:
        # idAgendamento não foi salvo na ingestão (exame antigo) — nada a buscar.
        return {"hash": hash_, "status": "sem_idagendamento"}

    base = os.environ.get("VALBOT_TECHPRATICO_BASE", "https://convert.se.techpratico.net")
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("VALBOT_TECHPRATICO_API_KEY", "")
    if key:
        headers["X-API-Key"] = key
    payload = json.dumps({"idAgendamento": int(ext), "id_analise": hash_}).encode()
    req = urllib.request.Request(
        base + "/conversao/dados-exame-analise-ia",
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        return {
            "hash": hash_,
            "status": "erro_http",
            "code": e.code,
            "msg": e.read().decode()[:200],
        }
    except Exception as e:
        return {"hash": hash_, "status": "erro", "msg": str(e)[:200]}

    resultado = resp.get("resultado_exame")
    annots = resp.get("training_annotations") or []
    # db não tem to_jsonb — serializa e faz cast ::jsonb no UPDATE.
    sets = ["training_annotations = %s::jsonb"]
    vals: list = [json.dumps(annots)]
    if resultado:
        sets.append("resultado_exame = COALESCE(%s, resultado_exame)")
        vals.append(resultado)
    vals.append(hash_)
    try:
        with db._conn() as c:  # type: ignore[attr-defined]
            if c is not None:
                c.execute(f"UPDATE exams SET {', '.join(sets)} WHERE hash = %s", vals)
    except Exception as e:
        return {"hash": hash_, "status": "erro_persist", "msg": str(e)[:200]}
    return {
        "hash": hash_,
        "status": "ok",
        "resultado_exame": resultado,
        "n_annotations": len(annots),
    }


@app.post("/api/exams/{hash}/buscar-resultado")
def exam_buscar_resultado(hash: str, _sess: dict = Depends(require_session)):
    """Busca o resultado oficial do exame no TechPrático e persiste (single)."""
    return _buscar_resultado_techpratico(hash)


class _BuscarResultadosIn(BaseModel):
    hashes: list[str] = Field(default_factory=list, description="Hashes dos exames a buscar.")


@app.post("/api/exams/buscar-resultados")
def exams_buscar_resultados(body: _BuscarResultadosIn, _sess: dict = Depends(require_session)):
    """Busca em LOTE o resultado oficial no TechPrático (usado pelo Kanban)."""
    res = [_buscar_resultado_techpratico(h) for h in body.hashes[:500]]
    ok = sum(1 for r in res if r.get("status") == "ok")
    return {"total": len(res), "ok": ok, "resultados": res}


@app.post("/api/exams/{analysis_id}/reanalyze")
def reanalyze_exam(
    analysis_id: str,
    background: BackgroundTasks,
    force_v26: bool = False,
    _sess: dict = Depends(require_session),
):
    """Re-roda a análise de UM exame sem novo upload. Útil pra ajustar
    prompt/preset ou recuperar um exame que falhou. Exige sessão de login.

    `?force_v26=1` força o pipeline modular v26 SÓ neste exame (testes do
    conserto v26 sem religar a env global VALBOT_USE_MODULAR_V26)."""
    return _enqueue_reanalysis(analysis_id, background, force_v26=force_v26)


@app.post("/api/exams/process-pending")
def process_pending_exams(
    background: BackgroundTasks,
    _sess: dict = Depends(require_session),
):
    """Enfileira a (re)análise de TODOS os exames pendentes/parados — status
    `pending`, `queued` ou `failed`. Pula os que estão `running` (já em curso)
    e `processed` (já têm laudo). Erros por exame (ex: vídeo sumiu) não
    derrubam o lote: são contados e reportados.

    Alimenta o botão "Processar pendentes" da Fila Operacional.
    """
    pending_statuses = ("pending", "queued", "failed")
    seen: set[str] = set()
    enfileirados: list[str] = []
    erros: list[dict] = []
    for st in pending_statuses:
        for row in db.list_overview(status=st, limit=500):
            h = row.get("hash")
            if not h or h in seen:
                continue
            seen.add(h)
            try:
                _enqueue_reanalysis(h, background)
                enfileirados.append(h)
            except Exception as e:  # noqa: BLE001 — isola falha por exame
                erros.append({"hash": h, "erro": str(e)[:200]})
    return {
        "enfileirados": len(enfileirados),
        "erros": len(erros),
        "hashes": enfileirados,
        "detalhe_erros": erros,
    }


@app.post("/api/exams/enviar-laudos")
def enviar_laudos(_sess: dict = Depends(require_envio_laudos)):
    """Envia à TechPrático os laudos dos exames FINALIZADOS (ValBot e examinador
    concordam, com laudo gerado) que ainda não foram enviados.

    Integração real quando `TECHPRATICO_LAUDO_URL` está configurado (POST JSON,
    Bearer `TECHPRATICO_LAUDO_TOKEN`). Sem isso, retorna quantos estão elegíveis
    e o que falta configurar — nunca marca como enviado sem realmente enviar.

    Alimenta o botão "Enviar laudos → TechPrático" da coluna Finalizados.
    """
    import json as _json
    import urllib.request

    url = os.environ.get("TECHPRATICO_LAUDO_URL", "").strip()
    token = os.environ.get("TECHPRATICO_LAUDO_TOKEN", "").strip()

    sel = (
        "SELECT hash, external_id, renach, aprovado "
        "FROM exams WHERE gs_video LIKE 'gs://%' AND status='processed' "
        "AND aprovado IS NOT NULL AND resultado_exame IN ('A','R') "
        "AND (resultado_exame='A') = aprovado "
        "AND (pdf_path IS NOT NULL OR gs_laudo_pdf IS NOT NULL) "
        "AND (laudo_envio_status IS DISTINCT FROM 'enviado')"
    )
    try:
        from tooling.api_stub import db as _db

        with _db._conn() as c:  # type: ignore[attr-defined]
            if c is None:
                raise RuntimeError("sem conexão DB")
            elegiveis = c.execute(sel).fetchall()
    except Exception as e:
        raise HTTPException(500, f"falha ao listar laudos: {e}")

    if not url:
        return {
            "configurado": False,
            "elegiveis": len(elegiveis),
            "enviados": 0,
            "detalhe": "Configure TECHPRATICO_LAUDO_URL (e TECHPRATICO_LAUDO_TOKEN) no .env para enviar.",
        }

    base = os.environ.get("PUBLIC_BASE_URL", "https://valbot.com.br").rstrip("/")
    enviados = erros = 0
    detalhe_erros: list[dict] = []
    for row in elegiveis:
        h, ext, renach, aprovado = row[0], row[1], row[2], row[3]
        payload = {
            "external_id": ext,
            "renach": renach,
            "resultado": "A" if aprovado else "R",
            "laudo_pdf_url": f"{base}/api/laudo/{h}/pdf",
        }
        try:
            req = urllib.request.Request(
                url,
                data=_json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    **({"Authorization": f"Bearer {token}"} if token else {}),
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                ok = 200 <= resp.status < 300
                body = resp.read(500).decode("utf-8", "ignore")
            from tooling.api_stub import db as _db

            with _db._conn() as c:  # type: ignore[attr-defined]
                c.execute(
                    "UPDATE exams SET laudo_envio_status=%s, laudo_enviado_em=NOW(), "
                    "laudo_envio_resultado=%s, laudo_envio_resposta=%s, "
                    "laudo_envio_tentativas=COALESCE(laudo_envio_tentativas,0)+1 WHERE hash=%s",
                    ("enviado" if ok else "erro", "A" if aprovado else "R", body[:480], h),
                )
            if ok:
                enviados += 1
            else:
                erros += 1
                detalhe_erros.append({"hash": h, "erro": body[:120]})
        except Exception as e:
            erros += 1
            detalhe_erros.append({"hash": h, "erro": str(e)[:120]})
            try:
                from tooling.api_stub import db as _db

                with _db._conn() as c:  # type: ignore[attr-defined]
                    c.execute(
                        "UPDATE exams SET laudo_envio_status='erro', "
                        "laudo_envio_resposta=%s, "
                        "laudo_envio_tentativas=COALESCE(laudo_envio_tentativas,0)+1 WHERE hash=%s",
                        (str(e)[:480], h),
                    )
            except Exception:
                pass
    return {
        "configurado": True,
        "elegiveis": len(elegiveis),
        "enviados": enviados,
        "erros": erros,
        "detalhe_erros": detalhe_erros[:10],
    }


# ============================================================================
# Pipeline: status + background task de análise
# ============================================================================


def _write_status(out_dir: Path, status: str, **extra) -> None:
    payload = {"status": status, "updated_at": datetime.utcnow().isoformat() + "Z"}
    payload.update(extra)
    (out_dir / "status.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def _read_status(out_dir: Path) -> str:
    """Lê status do exame priorizando o DB (single source of truth).

    Ordem:
      1. `db.fetch_status(analysis_id)` — autoritativo.
      2. Fallback pro `status.json` no disco — só pra dev local sem DB ou
         pra exames legados antes da Fase A do refactor de rotinas.

    Resolve o caso zombie do `418a43fe9525` (DB queued, status.json running):
    DB sempre vence. status.json se torna artefato debug-only.
    """
    analysis_id = out_dir.name  # nome do diretório == analysis_id
    db_status = db.fetch_status(analysis_id)
    if db_status:
        return db_status
    # Fallback (DB indisponível ou exame não existe na tabela):
    f = out_dir / "status.json"
    if not f.exists():
        return "unknown"
    try:
        return json.loads(f.read_text()).get("status", "unknown")
    except Exception:
        return "unknown"


def _run_analysis(
    analysis_id: str, video_ref: str, upload_meta: dict, force_v26: bool = False
) -> None:
    """Worker em background: chama Gemini, salva result.json, gera laudo.pdf,
    atualiza status.json. Idempotente — pode ser chamado novamente.

    `video_ref` aceita caminho local ('/opt/.../video.mp4') ou GCS URI
    ('gs://bucket/path/video.mp4'). Quando vem do fluxo signed URL, é gs://;
    quando vem do `POST /api/exams` legado, é caminho local.
    `analysis_id` é UUID hex (signed URL flow) ou SHA256 (legado).
    """
    out_dir = ANALYSES_DIR / analysis_id
    is_gcs = isinstance(video_ref, str) and video_ref.startswith("gs://")
    rubrica_slug = upload_meta.get("exame", {}).get("rubrica", "1020/2025")
    filename_for_record = video_ref.rsplit("/", 1)[-1] if is_gcs else Path(video_ref).name

    try:
        # Fase A: DB é fonte única de status. status.json continua sendo
        # escrito mas só pra debug local — nunca lido como autoritativo.
        # Fix do zombie 418a43fe9525 (DB queued + disk running, processo morto).
        db.update_status(analysis_id, "running")
        _write_status(out_dir, "running")
        log.info(
            "running analysis: id=%s rubrica=%s mock=%s gcs=%s",
            analysis_id[:12],
            rubrica_slug,
            USE_MOCK_VLM,
            is_gcs,
        )

        # 1. Gemini (ou mock pra dev sem GCP configurado)
        if USE_MOCK_VLM:
            # Mock só funciona com path local (precisa abrir o arquivo).
            if is_gcs:
                raise RuntimeError(
                    "VALBOT_USE_MOCK_VLM=1 não suporta gs:// — desabilite o mock pra usar signed URL"
                )
            result = _mock_analyze_result(Path(video_ref), rubrica_slug)
        else:
            from src.analysis.gemini_analyzer import AnalysisOptions, analyze_video

            # Pipeline v26 modular (discovery de layout + composição por câmera,
            # com o código de conduta MBEDV). Ativado pela env VALBOT_USE_MODULAR_V26.
            # Antes essa flag era ignorada aqui — o reanalyze caía sempre no v25.
            # O v26 só liga de fato com categoria resolvida; senão cai no v25.
            use_v26 = force_v26 or os.environ.get("VALBOT_USE_MODULAR_V26", "0") == "1"
            categoria = (
                (
                    (upload_meta.get("candidato") or {}).get("categoria")
                    or upload_meta.get("categoria")
                    or _parse_categoria_from_s3_path(
                        (upload_meta.get("video") or {}).get("gs_path_original_s3") or ""
                    )
                    or ""
                )
                .strip()
                .upper()
            )
            log.info(
                "analyze: use_modular_v26=%s categoria=%r (exame %s)",
                use_v26,
                categoria,
                analysis_id,
            )
            # GATE BARATO de categoria B (1-2 frames, ~US$0,001): roda ANTES do
            # pipeline completo. Se não for exame prático cat B (com confiança),
            # rejeita sem gastar os ~US$0,07 da análise inteira. Fail-open: erro
            # no gate → segue pra análise normal. Liga/desliga via VALBOT_GATE_CATB.
            gate = None
            if is_gcs and os.environ.get("VALBOT_GATE_CATB", "1") == "1":
                try:
                    from src.analysis.gemini_analyzer import gate_categoria_b

                    gate = gate_categoria_b(video_ref)
                    log.info(
                        "gate cat-B id=%s is_cat_b=%s conf=%.2f custo=%.4f motivo=%r",
                        analysis_id[:12],
                        gate.get("is_cat_b"),
                        gate.get("confianca"),
                        gate.get("cost_usd"),
                        gate.get("motivo"),
                    )
                except Exception as e:
                    log.warning("gate cat-B erro (%s) — segue p/ análise", e)
                    gate = None

            if (
                gate
                and not gate.get("erro")
                and not gate.get("is_cat_b")
                and gate.get("confianca", 0) >= 0.85
            ):
                # Reprova barata: não é categoria B → não roda o pipeline completo.
                result = {
                    "schema_version": "tier_a/0.1",
                    "rubrica": str(rubrica_slug).replace("/", "_"),
                    "rejected": True,
                    "rejection_reason": "nao_e_cat_b",
                    "rejection_details": gate.get("motivo")
                    or "Gate de 1 frame: não é exame prático categoria B.",
                    "aprovado": None,
                    "pontuacao_total": None,
                    "infracoes_detectadas": [],
                    "gate_categoria_b": gate,
                    "cost": {
                        "usd": gate.get("cost_usd") or 0.0,
                        "prompt_tokens": gate.get("tokens_in") or 0,
                        "output_tokens": gate.get("tokens_out") or 0,
                        "elapsed_s": gate.get("elapsed_s") or 0.0,
                    },
                }
            else:
                result = analyze_video(
                    video_ref,
                    rubrica_slug=rubrica_slug,
                    options=AnalysisOptions(
                        rubrica_slug=rubrica_slug,
                        use_modular_v26=use_v26,
                        categoria=categoria or None,
                    ),
                )
                # Soma o custo do gate ao custo total da análise (transparência).
                if gate and not gate.get("erro"):
                    result["gate_categoria_b"] = gate
                    c = result.get("cost")
                    if isinstance(c, dict) and isinstance(c.get("usd"), (int, float)):
                        c["usd"] = round(c["usd"] + (gate.get("cost_usd") or 0.0), 6)

        # 2. enriquece com metadados do upload
        result.setdefault("video", {})
        result["video"]["hash"] = upload_meta.get("video", {}).get("hash") or analysis_id
        result["video"]["filename"] = filename_for_record
        result["video"].setdefault("gs_path", upload_meta.get("video", {}).get("gs_path"))
        result["exam"] = upload_meta.get("exame", {})
        result["candidato"] = upload_meta.get("candidato", {})
        (out_dir / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False, default=str)
        )

        # 2b. PERSISTE resultado + infrações no DB. A reanálise não fazia isso —
        # só o tooling/process_pending_s3.py persistia, então re-rodar gravava
        # result.json em disco mas o dashboard (que lê do DB) nunca via o
        # resultado novo. Espelha o padrão do process_pending_s3.
        try:
            db.update_result(analysis_id, result, cost=result.get("cost"), upload_meta=upload_meta)
            infs = result.get("infracoes_detectadas") or []
            if infs:
                db.upsert_infractions(analysis_id, infs)
        except Exception:
            log.exception("persistência DB falhou para %s", analysis_id[:12])

        # 3. Renderiza PDF
        try:
            _render_laudo_pdf(out_dir, result, upload_meta)
            # Fase A: DB primeiro, status.json depois (cache derivado).
            db.update_status(analysis_id, "processed")
            (out_dir / "status.json").write_text(
                json.dumps(
                    {
                        "status": "processed",
                        "updated_at": datetime.utcnow().isoformat() + "Z",
                        "pontuacao_total": result.get("pontuacao_total"),
                        "aprovado": result.get("aprovado"),
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        except Exception as e:
            log.exception("PDF rendering failed for %s", analysis_id[:12])
            db.update_status(analysis_id, "processed_no_pdf", error=f"PDF: {e}"[:500])
            _write_status(out_dir, "processed_no_pdf", error=f"PDF: {e}")

        log.info(
            "analysis done: id=%s pontos=%s aprovado=%s",
            analysis_id[:12],
            result.get("pontuacao_total"),
            result.get("aprovado"),
        )

    except Exception as e:
        log.exception("analysis failed for %s", analysis_id[:12])
        # Fase A: DB primeiro, status.json depois.
        db.update_status(analysis_id, "failed", error=str(e)[:500])
        _write_status(
            out_dir,
            "failed",
            error=str(e),
            traceback=traceback.format_exc()[-2000:],
        )


def _render_laudo_pdf(out_dir: Path, result: dict, upload_meta: dict) -> None:
    """Converte o `result` Gemini para `LaudoContext` e renderiza o PDF."""
    from src.reporting.adapter import build_context
    from src.reporting.pdf import render_pdf

    detectadas = []
    for d in result.get("infracoes_detectadas", []):
        ts = d.get("timestamp_s")
        if ts is None:
            ts = d.get("ts_seconds") or 0
        detectadas.append(
            {
                "id": d["id"],
                "timestamp_inicio": float(ts or 0),
                "duracao_s": float(d.get("duracao_s") or 1.0),
                "evidencia": d.get("evidence") or d.get("evidencia") or "",
                "descricao_longa": d.get("evidence") or "",
                "occurrences": 1,
            }
        )

    candidato = dict(upload_meta.get("candidato", {}))
    candidato["veiculo"] = upload_meta.get("exame", {}).get("veiculo", "—")
    # LGPD §17 — mascara PII na renderização do laudo (audiência ampla: DETRAN,
    # jurídico, candidato). O dado real fica só no banco, atrás de sessão.
    if candidato.get("cpf"):
        candidato["cpf"] = _mask_cpf(candidato.get("cpf"))
    if candidato.get("renach"):
        candidato["renach"] = _mask_renach(candidato.get("renach"))

    metadata = {
        "laudo_id": f"LAU-{result['video']['hash'][:8].upper()}",
        "rubrica": "1020_2025",
        "video_hash": result["video"]["hash"],
        "modelo_versao": result.get("engine", {}).get("model", "gemini-3.1-pro-preview"),
        "duracao_seg": float(result.get("video", {}).get("duration_s") or 240.0),
        "limite_pontuacao": 10,
        "local": upload_meta.get("exame", {}).get("local", "—"),
        "examinador": upload_meta.get("exame", {}).get("examinador", "—"),
        "data_exame": datetime.now().strftime("%d/%m/%Y"),
        "result_hash": hashlib.sha1(
            json.dumps(result, sort_keys=True, default=str).encode()
        ).hexdigest()[:12],
        "analysis_version": "valbot-vertex-v25",
    }

    ctx = build_context(detectadas, candidato, metadata)
    # Template espera `contagem.eliminatoria` (R1020 não tem essa categoria, fica 0).
    ctx_dict = dict(ctx)
    ctx_dict["contagem"] = {"eliminatoria": 0, **ctx_dict.get("contagem", {})}
    render_pdf(ctx_dict, out_dir / "laudo.pdf")


def _mock_analyze_result(video_path: Path, rubrica_slug: str) -> dict:
    """Resultado fake pra desenvolvimento sem GCP. Ativado por
    `VALBOT_USE_MOCK_VLM=1`. Cobre os mesmos campos do schema real."""
    from src.rubrics.taxonomia import CATALOGO, Rubrica

    canon = {i.id: i for i in CATALOGO if i.rubrica == Rubrica.RES_1020_2025}
    layout = {
        "TL": "frontal",
        "TR": "lateral_direita",
        "BL": "interna",
        "BR": "traseira_esq",
        "confianca_layout": 0.92,
        "fabricante_provavel": "VIP",
    }
    sample_detectadas = [
        {
            "id": "R1020-G-c",
            "status": "detectada",
            "ts_seconds": 14,
            "duracao_s": 510.0,
            "canal_evidencia": "ambos",
            "quadrante_origem": "BL",
            "camera_origem": "interna",
            "evidence": "BL [interna]: candidato visivelmente sem cinto desde 00:14. Sem som de cinto travando no áudio.",
            "confidence": 0.95,
        },
        {
            "id": "R1020-M-c",
            "status": "detectada",
            "ts_seconds": 134,
            "duracao_s": 1.8,
            "canal_evidencia": "ambos",
            "quadrante_origem": "BL",
            "camera_origem": "interna",
            "evidence": "BL [interna] + áudio: motor calou em arrancada, candidato leva 1.8s para religar.",
            "confidence": 0.78,
        },
    ]

    infracoes_avaliadas: list[dict] = []
    detectadas: list[dict] = []
    for sid, info in canon.items():
        match = next((s for s in sample_detectadas if s["id"] == sid), None)
        if match:
            it = {
                "id": sid,
                "descricao": info.descricao,
                "severidade": info.severidade.value,
                "pontos": info.pontos,
                "tier": info.tier.value,
                **match,
                "timestamp_s": match["ts_seconds"],
                "base_legal": info.base_legal,
                "cameras_relevantes": [c.value for c in info.cameras_relevantes],
            }
            infracoes_avaliadas.append(it)
            detectadas.append(it)
        else:
            infracoes_avaliadas.append(
                {
                    "id": sid,
                    "descricao": info.descricao,
                    "severidade": info.severidade.value,
                    "pontos": info.pontos,
                    "tier": info.tier.value,
                    "status": "nao_detectada",
                    "timestamp_s": None,
                    "ts_seconds": None,
                    "duracao_s": None,
                    "canal_evidencia": "visao",
                    "quadrante_origem": None,
                    "camera_origem": None,
                    "evidence": "",
                    "confidence": 0.0,
                    "base_legal": info.base_legal,
                    "cameras_relevantes": [c.value for c in info.cameras_relevantes],
                }
            )

    pontuacao = sum(i["pontos"] for i in detectadas)
    return {
        "schema_version": "tier_a/0.1",
        "rubrica": "1020_2025",
        "video": {
            "filename": video_path.name,
            "duration_s": 521.0,
            "fps": None,
            "layout": layout,
        },
        "escopo_avaliado": [i["id"] for i in infracoes_avaliadas],
        "escopo_pendente_infraestrutura": [],
        "infracoes_avaliadas": infracoes_avaliadas,
        "infracoes_pendentes_infraestrutura": [],
        "infracoes_detectadas": detectadas,
        "pontuacao_total": pontuacao,
        "aprovado": pontuacao <= 10,
        "elapsed_s": 1.0,
        "engine": {
            "backend": "mock",
            "model": "mock-vlm",
            "preset": "v25/valbot-r1-vip-v25",
        },
    }


@app.get("/api/exams")
def list_exams():
    items = []
    for d in sorted(STORAGE.iterdir(), reverse=True):
        f = d / "upload.json"
        if f.exists():
            items.append(json.loads(f.read_text()))
    return {"count": len(items), "items": items}


# ============================================================================
# /api/videos — lista vídeos reais em storage/videos/ no formato VideoItem
# ============================================================================

VIDEOS_DIR = PROJECT_ROOT / "storage" / "videos"


def _hash_path(p: Path) -> str:
    """Hash determinístico curto baseado no path (não conteúdo, pra ser rápido)."""
    return hashlib.sha256(str(p.resolve()).encode()).hexdigest()[:16]


def _video_filename_to_slug(filename: str) -> str:
    """Replica tooling/bench_demo/preprocess.py::slug()."""
    stem = Path(filename).stem
    return stem.replace(" ", "_").replace("-", "").replace("__", "_").lower()[:40]


_S3_PATH_CATEGORIA_RE = re.compile(r"/(ACC|AB|AC|AD|AE|[A-E])/[A-Z]{2}\d{4,}", re.IGNORECASE)


def _parse_categoria_from_s3_path(s3_path: str) -> str:
    """Extrai categoria CNH (A/B/AB/AC/AD/AE/ACC/C/D/E) do path original do S3.

    Padrão técpratico stream: `s3://.../YYYYMMDD/HHMM/<CAT>/<RENACH>_*.mp4`.
    Ex: `https://techpratico-stream-se-cache.s3.amazonaws.com/20260520/3105/B/SE031249981_0000...`
    """
    if not s3_path:
        return ""
    m = _S3_PATH_CATEGORIA_RE.search(s3_path)
    return m.group(1).upper() if m else ""


def _infer_gate(result: dict) -> tuple[bool | None, str]:
    """Veredito do gate de admissibilidade (PASSO 0 do preset v25).

    Replica a lógica de mockApiInterceptors.ts::transformBackendLaudo:
    se o backend marcou `rejected` explícito, usa; senão, infere por
    escopo_avaliado vazio + infracoes_avaliadas vazio + sinais do layout.
    """
    if not result:
        return (None, "")
    if result.get("rejected") is True:
        return (True, result.get("rejection_reason") or "rejeitado")
    if result.get("rejected") is False:
        return (False, "")
    escopo_empty = not result.get("escopo_avaliado")
    avaliadas_empty = not result.get("infracoes_avaliadas")
    if not (escopo_empty and avaliadas_empty):
        return (False, "")
    layout = (result.get("video") or {}).get("layout") or {}
    fab = str(layout.get("fabricante_provavel") or "")
    try:
        conf = float(layout.get("confianca_layout", 1) or 1)
    except (TypeError, ValueError):
        conf = 1.0
    try:
        dur = float((result.get("video") or {}).get("duration_s", 0) or 0)
    except (TypeError, ValueError):
        dur = 0.0
    if fab == "desconhecido" or conf < 0.7:
        return (True, "fabricante_desconhecido")
    if dur == 0:
        return (True, "video_sem_metadata")
    if dur < 240:
        return (True, "duracao_insuficiente")
    return (True, "nao_e_exame_pratico")


# Cache em memória de source_url por hash. Evita reler upload.json em todo
# poll da fila operacional (5s). Memory cost: ~300 bytes/entry × 5k = 1.5MB
# no pior caso. Invalidado em init_upload (escreve upload.json novo) — vide
# `_invalidate_source_url_cache`.
_SOURCE_URL_CACHE: dict[str, str | None] = {}


def _get_source_url(analysis_id: str) -> str | None:
    """Lê `video.source_url` do upload.json de um exame. Resultado cacheado.

    Retorna None se o arquivo não existe ou não tem source_url — não levanta
    exceção, pra ser barato no caminho hot da listagem.
    """
    if analysis_id in _SOURCE_URL_CACHE:
        return _SOURCE_URL_CACHE[analysis_id]
    upload_path = ANALYSES_DIR / analysis_id / "upload.json"
    if not upload_path.exists():
        _SOURCE_URL_CACHE[analysis_id] = None
        return None
    try:
        upload_meta = json.loads(upload_path.read_text())
        url = (upload_meta.get("video") or {}).get("source_url")
        _SOURCE_URL_CACHE[analysis_id] = url if isinstance(url, str) else None
    except Exception:
        _SOURCE_URL_CACHE[analysis_id] = None
    return _SOURCE_URL_CACHE[analysis_id]


def _invalidate_source_url_cache(analysis_id: str) -> None:
    """Chamado quando upload.json muda (init_upload, finalize, etc)."""
    _SOURCE_URL_CACHE.pop(analysis_id, None)


def _is_real_source_url(url: str | None) -> bool:
    """Classificador de produção vs. teste/dev — lógica inclusiva.

    Default é REAL. Só esconde quando bate em URL de fixture conhecida.
    Cobre estes casos como reais:
      • AWS S3 oficial (techpratico/amazonaws.com)
      • Upload legado sem source_url (envio via /api/exams arquivo direto)
      • URLs desconhecidas (assume real, conservador)

    Esconde apenas:
      • samplelib.com, sample-Ns.mp4 (fixtures que vinha do smoke test)
      • localhost / 127.0.0.1 (dev local)

    Filtro de teste deve ser MAIS específico do que filtro de prod — senão
    perde exames legítimos com origem diferente do mainstream.
    """
    if not url:
        return True  # upload legado, sem source_url ≠ teste
    u = url.lower()
    test_markers = ("samplelib.com", "sample-5s.mp4", "localhost", "127.0.0.1")
    return not any(m in u for m in test_markers)


_STATUS_EM_PROCESSO = {"queued", "uploading", "streaming_s3", "pending", "running", "processing"}

# Cache em memória do feed da fila (TTL curto). A tela é "load de tabela" — não
# recomputa a cada request. Chave = include_test (bool).
_VIDEOS_CACHE: dict = {}
_VIDEOS_CACHE_TTL = 8.0
# Cache dos totais agregados (contadores das colunas do kanban/fila).
_TOTAIS_CACHE: dict = {"ts": 0.0, "data": None}
_TOTAIS_CACHE_TTL = 8.0


def _kanban_bucket(*, status, aprovado, gate_rejected, resultado_exame) -> str:
    """Classifica o exame nas 3 colunas do Kanban da Fila Operacional:

      • "em_processo" — ainda rodando/na fila (sem resultado nosso ainda).
      • "pronto"      — nosso veredito BATE com o do examinador (TechPrático).
      • "a_revisar"   — nosso veredito DIVERGE do examinador, OU não há
                        veredito do examinador pra confirmar (precisa olho humano).

    Comparação: examinador A=aprovado; R/N=reprovado. Nosso aprovado bool.
    """
    if status in _STATUS_EM_PROCESSO:
        return "em_processo"
    # Sem resultado nosso (gate rejeitado ou falha) → revisar.
    if aprovado is None:
        return "a_revisar"
    # Sem veredito do examinador pra comparar → revisar (não dá pra confirmar).
    if resultado_exame not in ("A", "R", "N"):
        return "a_revisar"
    examinador_aprovou = resultado_exame == "A"
    nosso_aprovou = bool(aprovado)
    return "pronto" if (examinador_aprovou == nosso_aprovou) else "a_revisar"


def _list_videos_from_db(*, include_test: bool = False) -> list[dict]:
    """Feed da fila — STALE-WHILE-REVALIDATE: SEMPRE retorna do cache em
    memória (<1ms). Se o cache está velho, dispara o refresh em BACKGROUND e
    devolve o dado antigo na hora — nenhum request espera o recompute (que era
    o que fazia a tela demorar ~4s). Só o 1º request absoluto (cache vazio)
    computa síncrono.
    """
    now = time.time()
    ck = _VIDEOS_CACHE.get(include_test)
    if ck is not None:
        if (now - ck["ts"]) >= _VIDEOS_CACHE_TTL and not ck.get("refreshing"):
            ck["refreshing"] = True
            import threading as _th

            _th.Thread(
                target=_refresh_videos_cache, kwargs={"include_test": include_test}, daemon=True
            ).start()
        return ck["data"]
    return _refresh_videos_cache(include_test=include_test)


def _refresh_videos_cache(*, include_test: bool = False) -> list[dict]:
    """Computa o feed da view e popula o cache. Roda no 1º boot (síncrono) ou
    em background (stale refresh). Não é chamada direto pelos endpoints."""
    now = time.time()

    try:
        from tooling.api_stub import db as _db

        # Volume grande — busca até 10k por vez. Dados vêm 100% do DB (view),
        # SEM leitura de upload.json por item (era o que travava a tela ~26s).
        rows = _db.list_overview(limit=10000)
    except Exception as e:
        log.warning("list_videos_from_db falhou: %s", e)
        return []

    items: list[dict] = []
    for r in rows:
        h = r.get("hash") or ""
        # is_real derivado do gs_video do DB (sem tocar o disco). Vídeo real =
        # tem gs_video apontando pro GCS de produção.
        gs_video = r.get("gs_video") or ""
        is_real = gs_video.startswith("gs://")
        source_url = gs_video
        # Default: vídeos não-reais (test/dev) somem da fila operacional.
        if not include_test and not is_real:
            continue
        # Fila Operacional: apenas exames categoria B (regra de negócio — só
        # categoria B é processada pelo worker). Demais categorias não aparecem.
        if (r.get("categoria") or "").strip().upper() != "B":
            continue
        kanban_bucket = _kanban_bucket(
            status=r.get("status"),
            aprovado=r.get("aprovado"),
            gate_rejected=r.get("gate_rejected"),
            resultado_exame=r.get("resultado_exame"),
        )
        items.append(
            {
                "kanban_bucket": kanban_bucket,
                "path": f"storage/analyses/{h}/video.mp4",
                "source_url": source_url,
                "is_real": is_real,
                "absolute_path": "",
                "filename": "video.mp4",
                "size_mb": float(r["size_mb"]) if r.get("size_mb") is not None else None,
                "mtime": (r.get("updated_at") or r.get("created_at") or "").isoformat() + "Z"
                if hasattr(r.get("updated_at") or r.get("created_at"), "isoformat")
                else (r.get("updated_at") or r.get("created_at") or ""),
                "in_storage": True,
                "hash": h,
                # Identificadores DETRAN + datas (consumidos pela Fila do design).
                "renach": r.get("renach") or "",
                "external_id": r.get("external_id"),
                # isoformat() já inclui o fuso (+00:00) — NÃO anexar "Z" (gera
                # "...+00:00Z", data inválida no navegador → campo some).
                "created_at": r.get("created_at").isoformat()
                if hasattr(r.get("created_at"), "isoformat")
                else (r.get("created_at") or ""),
                "updated_at": r.get("updated_at").isoformat()
                if hasattr(r.get("updated_at"), "isoformat")
                else (r.get("updated_at") or ""),
                "has_result": (r.get("aprovado") is not None) or bool(r.get("gate_rejected")),
                "has_pdf": bool(r.get("pdf_path") or r.get("gs_laudo_pdf")),
                "status": r.get("status"),
                "candidato_nome": r.get("candidato_nome") or "",
                "exam_meta": {
                    "veiculo": r.get("veiculo") or "",
                    "local": r.get("local_unidade") or "",
                    "examinador": r.get("examinador") or "",
                    "auto_escola": r.get("auto_escola") or "",
                },
                "engine": {
                    "backend": r.get("engine_backend"),
                    "model": r.get("engine_model"),
                    "preset": r.get("engine_preset"),
                },
                "result_url": f"/api/exams/{h}/result" if r.get("aprovado") is not None else None,
                "pdf_url": f"/api/laudo/{h}/pdf"
                if r.get("pdf_path") or r.get("gs_laudo_pdf")
                else None,
                "pontuacao_total": r.get("pontuacao_total"),
                "aprovado": r.get("aprovado"),
                "num_infracoes": r.get("num_infracoes") or 0,
                "duration_s": float(r["duration_s"]) if r.get("duration_s") is not None else None,
                "categoria_cnh": r.get("categoria") or "",
                "gate_rejected": r.get("gate_rejected"),
                "gate_motivo": r.get("gate_motivo") or "",
                # F6 — coluna STORED computed (substitui derivação no frontend)
                "resultado": r.get("resultado"),
                # Veredito do examinador DETRAN (A=Aprovado / R=Reprovado / N=Não avaliado)
                "resultado_exame": r.get("resultado_exame"),
                # Validação independente (ground truth Gemini)
                "validator_veredito": r.get("validator_veredito"),
                "validator_confianca": float(r["validator_confianca"])
                if r.get("validator_confianca") is not None
                else None,
                "cost_usd": float(r["cost_usd"]) if r.get("cost_usd") is not None else None,
            }
        )
    # Divergência pós-comitê (feature §10): anexa a decisão do Comitê pra a fila
    # esconder exames cuja divergência foi RESOLVIDA (comitê concordou).
    try:
        from tooling.api_stub import db as _db

        _pos = _db.comite_pos_divergencia_por_hash()
    except Exception:
        _pos = {}
    for _it in items:
        _it["tipo_divergencia_pos_comite"] = _pos.get(_it.get("hash"))
    # Guarda no cache (TTL) — próximos requests dentro da janela reusam.
    # Pré-serializa o JSON AQUI (no background/boot, fora do request path) —
    # a serialização de ~960 itens leva ~2-4s e era o gargalo da tela. Guardando
    # os bytes prontos, o endpoint só os devolve (instantâneo).
    try:
        payload = json.dumps(items, default=str, ensure_ascii=False).encode("utf-8")
    except Exception:
        payload = None
    _VIDEOS_CACHE[include_test] = {
        "ts": time.time(),
        "data": items,
        "json": payload,
        "refreshing": False,
    }
    return items


def _compute_totais() -> dict:
    """Totais agregados das colunas da fila — agregação SQL pura (rápida, sem
    ler disco). É o que a tela precisa pros contadores/kanban. Cacheado."""
    now = time.time()
    if _TOTAIS_CACHE["data"] is not None and (now - _TOTAIS_CACHE["ts"]) < _TOTAIS_CACHE_TTL:
        return _TOTAIS_CACHE["data"]
    out = {"total": 0, "por_status": {}, "por_resultado": {}, "por_categoria": {}, "kanban": {}}
    try:
        from tooling.api_stub import db as _db

        with _db._conn() as c:  # type: ignore[attr-defined]
            if c is not None:
                # só vídeos reais (gs_video no GCS) e categoria B (regra da Fila
                # Operacional — só categoria B é processada).
                base = "FROM exams WHERE gs_video LIKE 'gs://%' AND categoria='B'"
                cur = c.execute(f"SELECT COUNT(*) {base}")
                out["total"] = cur.fetchone()[0]
                for col, key in (("status", "por_status"), ("categoria", "por_categoria")):
                    cur = c.execute(f"SELECT {col}, COUNT(*) {base} GROUP BY {col}")
                    out[key] = {(r[0] or "—"): r[1] for r in cur.fetchall()}
                # kanban buckets (em_processo / pronto / a_revisar) via SQL
                cur = c.execute(f"""
                    SELECT
                      CASE
                        WHEN status IN ('queued','uploading','streaming_s3','pending','running','processing') THEN 'em_processo'
                        WHEN aprovado IS NULL THEN 'a_revisar'
                        WHEN resultado_exame NOT IN ('A','R','N') OR resultado_exame IS NULL THEN 'a_revisar'
                        WHEN (resultado_exame='A') = (aprovado) THEN 'pronto'
                        ELSE 'a_revisar'
                      END AS bucket, COUNT(*)
                    {base} GROUP BY 1
                """)
                out["kanban"] = {r[0]: r[1] for r in cur.fetchall()}
    except Exception as e:
        log.warning("_compute_totais falhou: %s", e)
    _TOTAIS_CACHE.update(ts=now, data=out)
    return out


@app.get("/api/videos/totais")
def videos_totais():
    """Totais agregados pra fila/kanban — load rápido, cacheado (8s)."""
    return _compute_totais()


@app.get("/api/dashboard/valbot")
def dashboard_valbot(
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None, alias="to"),
):
    """KPIs do Dashboard (design claude.ai/design): recebidos, processados,
    custo e ASSERTIVIDADE (concordância TP×ValBot, só A/R — `N` não conta) +
    série de volume. Agregação SQL pura sobre vídeos reais (gs_video no GCS).

    Filtra por período de recebimento (created_at) quando `from`/`to`
    (YYYY-MM-DD) são informados — assim o filtro de data da topbar também
    afeta o Dashboard."""
    import re as _re

    cond = ""
    if from_ and _re.match(r"^\d{4}-\d{2}-\d{2}$", from_):
        cond += f" AND created_at >= '{from_} 00:00:00'"
    if to and _re.match(r"^\d{4}-\d{2}-\d{2}$", to):
        cond += f" AND created_at <= '{to} 23:59:59'"
    has_range = bool(cond)
    out = {
        "recebidos": 0,
        "processados": 0,
        "custo_total_usd": 0.0,
        "custo_por_video_usd": 0.0,
        "assertividade_pct": None,
        "concordantes": 0,
        "divergentes": 0,
        "comparaveis": 0,
        # Indicadores regulatórios (v2.0 §15):
        "interrompidos": 0,
        "taxa_interrupcao_pct": None,
        "divergencia_por_examinador": [],
        "divergencia_por_unidade": [],
        "divergencia_por_categoria": [],
        # Indicador "recebidos × resultado oficial × anotações" (totais do período).
        "recebidos_total": 0,
        "com_oficial_total": 0,
        "oficial_aprovado_total": 0,
        "oficial_reprovado_total": 0,
        "aguardando_oficial_total": 0,
        "com_anotacoes_total": 0,
        "volume_14d": [],
    }
    try:
        from tooling.api_stub import db as _db

        with _db._conn() as c:  # type: ignore[attr-defined]
            if c is None:
                return out
            base = f"FROM exams WHERE gs_video LIKE 'gs://%'{cond}"
            out["recebidos"] = c.execute(f"SELECT COUNT(*) {base}").fetchone()[0]
            out["processados"] = c.execute(
                f"SELECT COUNT(*) {base} AND status='processed'"
            ).fetchone()[0]
            row = c.execute(
                f"SELECT COALESCE(SUM(cost_usd),0), COALESCE(AVG(cost_usd),0) "
                f"{base} AND cost_usd IS NOT NULL"
            ).fetchone()
            out["custo_total_usd"] = float(row[0] or 0)
            out["custo_por_video_usd"] = float(row[1] or 0)
            # Assertividade = concordância sobre os comparáveis A/R (N excluído).
            arow = c.execute(
                f"SELECT "
                f"COUNT(*) FILTER (WHERE (resultado_exame='A')=(aprovado)), "
                f"COUNT(*) FILTER (WHERE (resultado_exame='A')<>(aprovado)) "
                f"{base} AND status='processed' AND aprovado IS NOT NULL "
                f"AND resultado_exame IN ('A','R')"
            ).fetchone()
            conc, div = int(arow[0] or 0), int(arow[1] or 0)
            comp = conc + div
            out["concordantes"], out["divergentes"], out["comparaveis"] = conc, div, comp
            out["assertividade_pct"] = round(100.0 * conc / comp, 1) if comp else None

            # --- Indicadores regulatórios (v2.0 §15) ---
            # Taxa de interrupção = exames 'N' (não avaliado/interrompido) sobre
            # o total com veredito presencial informado (A/R/N).
            irow = c.execute(
                f"SELECT COUNT(*) FILTER (WHERE resultado_exame='N'), "
                f"COUNT(*) FILTER (WHERE resultado_exame IN ('A','R','N')) "
                f"{base}"
            ).fetchone()
            interromp, com_veredito = int(irow[0] or 0), int(irow[1] or 0)
            out["interrompidos"] = interromp
            out["taxa_interrupcao_pct"] = (
                round(100.0 * interromp / com_veredito, 1) if com_veredito else None
            )

            # Divergência (IA × examinador) quebrada por dimensão. Reaproveita o
            # mesmo critério de comparáveis (A/R, processed, aprovado NOT NULL).
            def _div_por(coluna: str, chave: str) -> list[dict]:
                rows = c.execute(
                    f"SELECT COALESCE(NULLIF(TRIM({coluna}), ''), '—') AS k, "
                    f"COUNT(*) FILTER (WHERE (resultado_exame='A')=(aprovado)) AS conc, "
                    f"COUNT(*) FILTER (WHERE (resultado_exame='A')<>(aprovado)) AS div "
                    f"{base} AND status='processed' AND aprovado IS NOT NULL "
                    f"AND resultado_exame IN ('A','R') "
                    f"GROUP BY 1 ORDER BY div DESC, conc DESC"
                ).fetchall()
                res = []
                for k, cc, dd in rows:
                    cc, dd = int(cc or 0), int(dd or 0)
                    tot = cc + dd
                    res.append(
                        {
                            chave: k,
                            "concordantes": cc,
                            "divergentes": dd,
                            "comparaveis": tot,
                            "divergencia_pct": round(100.0 * dd / tot, 1) if tot else None,
                        }
                    )
                return res

            out["divergencia_por_examinador"] = _div_por("examinador", "examinador")
            out["divergencia_por_unidade"] = _div_por("local_unidade", "unidade")
            out["divergencia_por_categoria"] = _div_por("categoria", "categoria")

            # Indicador "recebidos × resultado oficial × anotações" — da view
            # canônica (v_exams_overview, migrations 027/028). Fonte única.
            # MESMO ESCOPO da fila operacional (Kanban): categoria + corte, e
            # "aguardando" = stage='aguardando_oficial' (não inclui processando/
            # falhou) — assim o número bate com a coluna do Kanban.
            _ind_cat = (os.environ.get("VALBOT_FILA_CATEGORIA", "B") or "B").strip().upper()[:1]
            if _ind_cat not in ("A", "B", "C", "D", "E"):
                _ind_cat = "B"
            _ind_desde = os.environ.get("VALBOT_FILA_DESDE", "2026-06-13")
            _ind_desde = (
                _ind_desde if _re.match(r"^\d{4}-\d{2}-\d{2}$", _ind_desde or "") else "2026-06-13"
            )
            vbase = (
                f"FROM v_exams_overview WHERE gs_video LIKE 'gs://%'{cond}"
                f" AND categoria = '{_ind_cat}' AND created_at >= '{_ind_desde}'"
            )
            trow = c.execute(
                f"SELECT COUNT(*), "
                f"COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL), "
                f"COUNT(*) FILTER (WHERE resultado_oficial='A'), "
                f"COUNT(*) FILTER (WHERE resultado_oficial='R'), "
                f"COUNT(*) FILTER (WHERE stage='aguardando_oficial'), "
                f"COUNT(*) FILTER (WHERE tem_anotacoes) "
                f"{vbase}"
            ).fetchone()
            out["recebidos_total"] = int(trow[0] or 0)
            out["com_oficial_total"] = int(trow[1] or 0)
            out["oficial_aprovado_total"] = int(trow[2] or 0)
            out["oficial_reprovado_total"] = int(trow[3] or 0)
            out["aguardando_oficial_total"] = int(trow[4] or 0)
            out["com_anotacoes_total"] = int(trow[5] or 0)

            # Série diária. Com período → dentro do período; senão, últimos 14 dias.
            vol_where = (
                vbase if has_range else f"{vbase} AND created_at >= NOW() - INTERVAL '14 days'"
            )
            vrows = c.execute(
                f"SELECT to_char(date_trunc('day', created_at), 'DD/MM') AS dia, "
                f"COUNT(*), "
                f"COUNT(*) FILTER (WHERE status='processed'), "
                f"COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL), "
                f"COUNT(*) FILTER (WHERE resultado_oficial='A'), "
                f"COUNT(*) FILTER (WHERE resultado_oficial='R'), "
                f"COUNT(*) FILTER (WHERE stage='aguardando_oficial'), "
                f"COUNT(*) FILTER (WHERE tem_anotacoes) "
                f"{vol_where} "
                f"GROUP BY 1, date_trunc('day', created_at) "
                f"ORDER BY date_trunc('day', created_at)"
            ).fetchall()
            out["volume_14d"] = [
                {
                    "dia": r[0],
                    "recebidos": int(r[1]),
                    "processados": int(r[2]),
                    "com_oficial": int(r[3]),
                    "aprovados": int(r[4]),
                    "reprovados": int(r[5]),
                    "aguardando": int(r[6]),
                    "com_anotacoes": int(r[7]),
                }
                for r in vrows
            ]
    except Exception as e:
        log.warning("dashboard_valbot falhou: %s", e)
    return out


@app.get("/api/dashboard/diario")
def dashboard_diario(
    dias: int = 30,
    _sess: dict = Depends(require_session),
):
    """Série DIÁRIA real para o indicador "Auditado × Discordância".

    Agrega a v_exams_overview (fonte canônica, migrations 027/028) por dia de
    RECEBIMENTO (created_at), devolvendo, por dia:

      • recebidos   — exames recebidos no dia.
      • com_oficial — dos recebidos, quantos têm resultado oficial DEFINITIVO
                      do examinador (resultado_oficial ∈ {A,R}; "N"/NULL não
                      conta — a view já normaliza isso em `resultado_oficial`).
      • auditados   — quantos a IA Val avaliou (resultado calculado presente,
                      i.e. `aprovado IS NOT NULL`).
      • divergentes — dos COMPARÁVEIS, quantos o oficial diverge da IA
                      ((resultado_exame='A') <> aprovado). Usa o campo canônico
                      `divergente` da view (só verdadeiro com oficial A/R).
      • comparaveis — têm oficial E foram auditados (base do % de discordância).

    O frontend deriva: % Auditado = auditados/recebidos; % de Discordância =
    divergentes/comparaveis (divisão por zero → "—" na UI).

    Resiliente: DB off / erro de query ⇒ {items: [], source: "mock"}. Protegido
    por require_session, igual aos demais dashboards. NÃO altera endpoints
    existentes — fonte e critérios espelham /api/dashboard/valbot."""
    dias = max(1, min(int(dias), 365))
    out: dict = {"items": [], "source": "mock"}
    try:
        from tooling.api_stub import db as _db

        with _db._conn() as c:  # type: ignore[attr-defined]
            if c is None:
                return out
            # Janela: últimos `dias` dias (inclui hoje) por data de recebimento.
            # gs_video LIKE 'gs://%' = mesmo recorte de vídeos reais do dashboard.
            rows = c.execute(
                "SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS dia, "
                "COUNT(*) AS recebidos, "
                "COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL) AS com_oficial, "
                "COUNT(*) FILTER (WHERE aprovado IS NOT NULL) AS auditados, "
                "COUNT(*) FILTER (WHERE divergente) AS divergentes, "
                "COUNT(*) FILTER (WHERE resultado_oficial IS NOT NULL "
                "                 AND aprovado IS NOT NULL) AS comparaveis "
                "FROM v_exams_overview "
                "WHERE gs_video LIKE 'gs://%' "
                "AND created_at >= (CURRENT_DATE - make_interval(days => %s - 1)) "
                "GROUP BY 1, date_trunc('day', created_at) "
                "ORDER BY date_trunc('day', created_at)",
                (dias,),
            ).fetchall()
            out["items"] = [
                {
                    "dia": r[0],
                    "recebidos": int(r[1] or 0),
                    "com_oficial": int(r[2] or 0),
                    "auditados": int(r[3] or 0),
                    "divergentes": int(r[4] or 0),
                    "comparaveis": int(r[5] or 0),
                }
                for r in rows
            ]
            out["source"] = "db"
    except Exception as e:
        log.warning("dashboard_diario falhou: %s", e)
        return {"items": [], "source": "mock"}
    return out


@app.get("/api/videos")
def list_videos(include_test: bool = False, only_unresolved: bool = False):
    """Lista vídeos disponíveis na UI — F5: DB é fonte ÚNICA no caminho quente.

    Fonte primária: `v_exams_overview` (Postgres). DB vazio devolve lista vazia
    (não cai mais pra file-walking — F4 fez fallback automático; F5 remove).

    Query params:
      • `include_test=true` — devolve TODOS os exames (inclusive fixtures
        de dev/teste cuja origem não é AWS S3). Default `false`: a fila
        operacional só mostra vídeos reais (source_url em amazonaws.com/s3://).
      • `only_unresolved=true` — só entram na fila exames cuja divergência NÃO
        foi resolvida pelo Comitê (tipo_divergencia_pos_comite != "sem_divergencia").

    Toggle de emergência: `VALBOT_USE_DB_VIDEOS=0` ativa o caminho file-based
    legado abaixo. Manter por 1 semana após F5 prod-stable; remover em F7.

    Caminho file-based (legado, atrás da flag):
      1. `storage/analyses/<hash>/` — uploads via POST /api/exams.
      2. `storage/videos/` — vídeos legados (analyses_demo).
    """
    if os.getenv("VALBOT_USE_DB_VIDEOS", "1") != "0":
        # F5: sem fallback automático. DB vazio = resposta vazia.
        # Serve o JSON PRÉ-SERIALIZADO do cache (bytes prontos) quando disponível
        # — pula a serialização cara do FastAPI no request path (<1ms vs ~3s).
        _list_videos_from_db(include_test=include_test)  # garante cache populado
        ck = _VIDEOS_CACHE.get(include_test)
        if only_unresolved:
            # Filtro da fila: SÓ exames com DIVERGÊNCIA real (resultado oficial do
            # examinador != veredito da IA) e cuja divergência o Comitê não
            # resolveu. O Comitê só roda em divergência — sem divergência, o exame
            # nem entra na fila do auditor. (Divergência de resultado A/R; pontuação
            # e infrações exigem o Motor de Comparação, ainda não no caminho quente.)
            data = (ck or {}).get("data", [])

            def _diverge(i):
                of = (i.get("resultado_exame") or "").strip().upper()
                ap = i.get("aprovado")
                return (of == "A" and ap is False) or (of == "R" and ap is True)

            return [
                i
                for i in data
                if i.get("tipo_divergencia_pos_comite") != "sem_divergencia" and _diverge(i)
            ]
        if ck is not None and ck.get("json") is not None:
            return Response(content=ck["json"], media_type="application/json")
        return (ck or {}).get("data", [])

    items: list[dict] = []
    seen_hashes: set[str] = set()

    # 1. Análises novas via /api/exams
    if ANALYSES_DIR.exists():
        for analysis_dir in sorted(ANALYSES_DIR.iterdir(), reverse=True):
            if not analysis_dir.is_dir():
                continue
            upload_path = analysis_dir / "upload.json"
            if not upload_path.exists():
                continue
            try:
                upload = json.loads(upload_path.read_text())
            except Exception:
                continue
            hash_hex = analysis_dir.name
            seen_hashes.add(hash_hex)
            video_meta = upload.get("video", {})
            filename = video_meta.get("filename") or "video.mp4"
            video_file = analysis_dir / filename
            status = _read_status(analysis_dir)
            stat = video_file.stat() if video_file.exists() else None
            result_path = analysis_dir / "result.json"
            result_data: dict = {}
            if result_path.exists():
                try:
                    result_data = json.loads(result_path.read_text())
                except Exception:
                    result_data = {}
            categoria_cnh = (
                (result_data.get("candidato") or {}).get("categoria")
                or (upload.get("candidato") or {}).get("categoria")
                or _parse_categoria_from_s3_path(video_meta.get("gs_path_original_s3") or "")
                or ""
            )
            gate_rejected, gate_motivo = _infer_gate(result_data)
            # size_mb: prioridade (1) upload.video.size_mb se preenchido,
            # (2) stat do arquivo local (warm_local_cache pode ter copiado),
            # (3) result.video.size se algum dia o pipeline preencher.
            size_mb = video_meta.get("size_mb")
            if size_mb is None and stat is not None:
                size_mb = round(stat.st_size / 1024 / 1024, 2)
            if size_mb is None:
                rv_size = (result_data.get("video") or {}).get("size")
                if isinstance(rv_size, (int, float)) and rv_size > 0:
                    size_mb = round(rv_size / 1024 / 1024, 2)
            items.append(
                {
                    "path": f"storage/analyses/{hash_hex}/{filename}",
                    "absolute_path": str(video_file.resolve()) if video_file.exists() else "",
                    "filename": filename,
                    "size_mb": size_mb,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z"
                    if stat
                    else upload.get("received_at", ""),
                    "in_storage": True,
                    "hash": hash_hex,
                    "has_result": result_path.exists(),
                    "has_pdf": (analysis_dir / "laudo.pdf").exists(),
                    "status": status,
                    "candidato_nome": upload.get("candidato", {}).get("nome", ""),
                    "exam_meta": upload.get("exame", {}),
                    "engine": upload.get("engine", {}),
                    "result_url": f"/api/exams/{hash_hex}/result" if result_path.exists() else None,
                    "pdf_url": f"/api/laudo/{hash_hex}/pdf"
                    if (analysis_dir / "laudo.pdf").exists()
                    else None,
                    "pontuacao_total": result_data.get("pontuacao_total", 0),
                    "aprovado": result_data.get("aprovado"),
                    "num_infracoes": len(result_data.get("infracoes_detectadas") or []),
                    "categoria_cnh": categoria_cnh,
                    "gate_rejected": gate_rejected,
                    "gate_motivo": gate_motivo,
                }
            )

    # 2. Vídeos legados (storage/videos/ + analyses_demo)
    if VIDEOS_DIR.exists():
        for video_file in sorted(VIDEOS_DIR.iterdir()):
            if not video_file.is_file() or video_file.suffix.lower() not in {
                ".mp4",
                ".mov",
                ".avi",
                ".mkv",
            }:
                continue
            slug = _video_filename_to_slug(video_file.name)
            slug_dir = STORAGE / slug
            latest = _latest_run(slug_dir) if slug_dir.exists() else None
            if latest is None:
                continue
            file_hash = _hash_path(video_file)
            if file_hash in seen_hashes:
                continue
            stat = video_file.stat()
            items.append(
                {
                    "path": f"storage/videos/{video_file.name}",
                    "absolute_path": str(video_file.resolve()),
                    "filename": video_file.name,
                    "size_mb": round(stat.st_size / 1024 / 1024, 2),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z",
                    "in_storage": True,
                    "hash": file_hash,
                    "has_result": True,
                    "status": "processed",
                    "legacy": True,
                }
            )
    return items


# ============================================================================
# BENCH VIEWER ENDPOINTS — laudos individuais por IA × vídeo
# ============================================================================


def _latest_run(slug_dir: Path) -> Path | None:
    """Retorna o subdir de timestamp mais recente que tenha summary.json.

    Cobre três layouts:
    - Plano (v2.1 run_one_video):  <slug>/<ts>/summary.json
    - Aninhado (v23 run_round1):   <slug>/r1/<ts>/summary.json
    - File API (v25):              <slug>/v25/<ts>/summary.json  ← prioridade
    """
    if not slug_dir.exists() or not slug_dir.is_dir():
        return None
    candidates: list[Path] = []
    v25_candidates: list[Path] = []
    for d in slug_dir.iterdir():
        if not d.is_dir():
            continue
        if (d / "summary.json").exists():
            candidates.append(d)
        # Sub-pastas tipo r1/, r2/, r3/ (v23) e v25/ (Gemini File API)
        if d.name in {"r1", "r2", "r3"}:
            for sub in d.iterdir():
                if sub.is_dir() and (sub / "summary.json").exists():
                    candidates.append(sub)
        if d.name == "v25":
            for sub in d.iterdir():
                # Exige laudo.json (não só summary.json) — runs falhas têm summary mas
                # nenhum laudo, e a UI dá 503 ao tentar usá-las.
                if (
                    sub.is_dir()
                    and (sub / "summary.json").exists()
                    and (sub / "laudo.json").exists()
                ):
                    v25_candidates.append(sub)
    # v25 tem prioridade absoluta — é o pipeline mais novo (audio nativo + ETICA)
    if v25_candidates:
        return sorted(v25_candidates, key=lambda d: d.name, reverse=True)[0]
    if not candidates:
        return None
    return sorted(candidates, key=lambda d: d.name, reverse=True)[0]


def _is_nested_v23(run_dir: Path) -> bool:
    """Detecta se é formato aninhado (run_round1 v23) — tem subdirs round_NN."""
    return any(d.is_dir() and d.name.startswith("round_") for d in run_dir.iterdir())


def _flatten_v23_models(summary: dict, run_dir: Path) -> dict:
    """Achata os models de v23 (que vêm em rounds[round_NN]) num dict plano
    estilo v2.1, agregando custos e usando dados da última rodada por modelo.
    """
    rounds = summary.get("rounds", {})
    flat: dict = {}
    for round_key in sorted(rounds.keys()):
        round_models = rounds[round_key]
        for mid, info in round_models.items():
            if mid not in flat:
                flat[mid] = dict(info)
                flat[mid]["cost_usd"] = info.get("cost_usd", 0)
                flat[mid]["elapsed_s"] = info.get("elapsed_s", 0)
            else:
                flat[mid]["cost_usd"] += info.get("cost_usd", 0)
                flat[mid]["elapsed_s"] = max(flat[mid]["elapsed_s"], info.get("elapsed_s", 0))
                # Sobrescreve infracoes_count com o valor da última rodada (mais recente)
                flat[mid]["infracoes_count"] = info.get(
                    "infracoes_count", flat[mid].get("infracoes_count")
                )
                flat[mid]["status"] = info.get("status", flat[mid].get("status"))
                flat[mid]["tokens_in"] = info.get("tokens_in", 0) + flat[mid].get("tokens_in", 0)
                flat[mid]["tokens_out"] = info.get("tokens_out", 0) + flat[mid].get("tokens_out", 0)
    return flat


def _resolve_summary_models(run_dir: Path, summary: dict) -> dict:
    """Retorna o dict de models compatível com v2.1, achatando v23 se for o caso."""
    if "rounds" in summary and not summary.get("models"):
        return _flatten_v23_models(summary, run_dir)
    return summary.get("models", {})


def _resolve_model_dir(run_dir: Path, model_id: str) -> Path:
    """Retorna o dir do modelo. v2.1: <run_dir>/<m>. v23: <run_dir>/round_00/<m>.
    v25 (File API): laudo.json fica direto em <run_dir>, sem subdir de modelo.
    """
    # v25 File API: laudo.json direto no run_dir
    if (run_dir / "laudo.json").exists():
        return run_dir
    flat = run_dir / model_id.replace("/", "__")
    if flat.exists():
        return flat
    # v23: pega round_00 (primeira rodada — pode ser estendido pra escolher melhor)
    nested = run_dir / "round_00" / model_id.replace("/", "__")
    return nested


@app.get("/api/bench/videos")
def bench_videos():
    """Lista vídeos com laudo bench disponível (último run de cada slug)."""
    items = []
    for slug_dir in sorted(STORAGE.iterdir()):
        if not slug_dir.is_dir():
            continue
        run_dir = _latest_run(slug_dir)
        if not run_dir:
            continue
        try:
            summary = json.loads((run_dir / "summary.json").read_text())
        except Exception:
            continue
        items.append(
            {
                "slug": slug_dir.name,
                "run_id": run_dir.name,
                "video_path": summary.get("video"),
                "models_count": len(_resolve_summary_models(run_dir, summary)),
                "total_cost_usd": summary.get("total_cost_usd", 0),
                "total_elapsed_s": summary.get("total_elapsed_s", 0),
                "started_at": summary.get("started_at"),
            }
        )
    return {"count": len(items), "items": items}


def _detect_actual_modality(model_dir: Path, model_id: str) -> str:
    """Detecta a MODALIDADE REAL enviada na chamada (não a capacidade teórica do modelo).

    Olha o request_body.json salvo. Se tem `image_url` no content → "frames".
    Se tem `video_url` → "video". Se nem um nem outro → "text".
    Fallback (sem request salvo): tenta inferir pela capacidade do modelo.
    """
    req_path = model_dir / "request_body.json"
    if req_path.exists():
        try:
            body = json.loads(req_path.read_text())
            messages = body.get("messages", [])
            for msg in messages:
                content = msg.get("content", [])
                if isinstance(content, list):
                    types = [c.get("type") for c in content if isinstance(c, dict)]
                    if "video_url" in types:
                        return "video"
                    if "image_url" in types:
                        return "frames"
            return "text"
        except Exception:
            pass
    # Fallback heurística: deepseek=texto, demais=frames (assume run sem vídeo)
    if "deepseek" in model_id.lower():
        return "text"
    return "frames"


def _bench_version(run_dir: Path) -> dict:
    """Calcula uma versão leve do estado atual do run pra refetch condicional.
    mtime: maior mtime entre summary.json e qualquer laudo.json.
    count_done: quantos modelos têm laudo.json escrito.
    """
    if not run_dir or not run_dir.exists():
        return {"mtime": 0.0, "count_done": 0}
    files = list(run_dir.rglob("laudo.json")) + list(run_dir.rglob("summary.json"))
    if not files:
        return {"mtime": 0.0, "count_done": 0}
    mtime = max(f.stat().st_mtime for f in files)
    count_done = len([f for f in files if f.name == "laudo.json"])
    return {"mtime": round(mtime, 1), "count_done": count_done}


@app.get("/api/bench/{slug}/version")
def bench_version(slug: str):
    """Retorna versão lightweight (mtime + count) do bench desse slug.
    Usado pelo frontend pra detectar mudança sem refazer fetch pesado dos models.
    """
    slug_dir = STORAGE / slug
    run_dir = _latest_run(slug_dir)
    if not run_dir:
        return {"mtime": 0.0, "count_done": 0, "exists": False}
    v = _bench_version(run_dir)
    v["exists"] = True
    v["run_id"] = run_dir.name
    return v


@app.get("/api/bench/{slug}/models")
def bench_models(slug: str):
    """Lista modelos disponíveis no último run do slug, com modalidade REAL usada."""
    slug_dir = STORAGE / slug
    run_dir = _latest_run(slug_dir)
    if not run_dir:
        raise HTTPException(404, f"slug {slug} não tem run com summary.json")
    summary = json.loads((run_dir / "summary.json").read_text())
    items = []
    for model_id, info in _resolve_summary_models(run_dir, summary).items():
        model_dir = _resolve_model_dir(run_dir, model_id)
        actual_modality = _detect_actual_modality(model_dir, model_id)
        items.append(
            {
                "model_id": model_id,
                "label": info.get("label"),
                "status": info.get("status"),
                "elapsed_s": info.get("elapsed_s"),
                "cost_usd": info.get("cost_usd", 0),
                "infracoes_count": info.get("infracoes_count"),
                "tokens_in": info.get("tokens_in"),
                "tokens_out": info.get("tokens_out"),
                "actual_modality": actual_modality,  # "video" | "frames" | "text"
            }
        )
    return {"slug": slug, "run_id": run_dir.name, "models": items}


# ============================================================================
# /api/analyses/hash/<hash>/result — adapter bench → LaudoResponse pro frontend
# ============================================================================

# Catálogo CONTRAN 1.020/2025 — extraído de src/rubrics/taxonomia.py
# (mantido inline pra evitar imports pesados de cv2/torch via src.ingestion)
RUBRIC_META: dict[str, dict] = {
    # Gravíssimas (6 pts)
    "R1020-G-a": {
        "titulo": "Desobedecer à sinalização semafórica ou de parada obrigatória",
        "gravidade": "gravissima",
        "pontos": 6,
        "cameras": ["frontal"],
        "artigo_ctb": "Art. 208",
        "ficha_mbedv": "MBEDV-FICHA-208",
    },
    "R1020-G-b": {
        "titulo": "Avançar sobre o meio-fio",
        "gravidade": "gravissima",
        "pontos": 6,
        "cameras": ["traseira_esq", "lateral_direita"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "sem ficha CTB dedicada (~Art. 193 calçada); Tier C",
    },
    "R1020-G-c": {
        "titulo": "Não concluir a baliza dentro da área em 3 tentativas",
        "gravidade": "gravissima",
        "pontos": 6,
        "cameras": ["frontal"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "DESCONTINUADA no MBEDV: baliza deixou de ser etapa avaliada",
    },
    "R1020-G-d": {
        "titulo": "Andar na contramão",
        "gravidade": "gravissima",
        "pontos": 6,
        "cameras": ["frontal"],
        "artigo_ctb": "Art. 186-II",
        "ficha_mbedv": "MBEDV-FICHA-186-II",
        "nota_mbedv": "Art. 186-II contramão sentido único (Gravíssima)",
    },
    "R1020-G-e": {
        "titulo": "Desrespeitar preferencial",
        "gravidade": "grave",
        "pontos": 4,
        "cameras": ["frontal"],
        "artigo_ctb": "Art. 215",
        "ficha_mbedv": "MBEDV-FICHA-215",
        "nota_mbedv": "gravidade corrigida p/ oficial: Gravíssima->Grave",
    },
    "R1020-G-f": {
        "titulo": "Provocar acidente",
        "gravidade": "gravissima",
        "pontos": 6,
        "cameras": ["frontal"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "sem ficha CTB (resultado do exame, não infração tipificada)",
    },
    "R1020-G-g": {
        "titulo": "Velocidade incompatível com a via",
        "gravidade": "gravissima",
        "pontos": 6,
        "cameras": ["frontal"],
        "artigo_ctb": "Art. 218",
        "ficha_mbedv": "MBEDV-FICHA-218",
        "nota_mbedv": "Art. 218 é ESCALONADO por % (Média/Grave/Gravíssima); mantido peso atual - revisar",
    },
    # Graves (4 pts)
    "R1020-GR-a": {
        "titulo": "Desobedecer demais sinalizações",
        "gravidade": "grave",
        "pontos": 4,
        "cameras": ["frontal"],
        "artigo_ctb": "Art. 195",
        "ficha_mbedv": "MBEDV-FICHA-195",
    },
    "R1020-GR-b": {
        "titulo": "Ultrapassagem em local proibido",
        "gravidade": "grave",
        "pontos": 4,
        "cameras": ["frontal"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "conduta genérica -> família Art. 199-203; sem ficha única",
    },
    "R1020-GR-c": {
        "titulo": "Não dar preferência a pedestre",
        "gravidade": "gravissima",
        "pontos": 6,
        "cameras": ["frontal"],
        "artigo_ctb": "Art. 214",
        "ficha_mbedv": "MBEDV-FICHA-214",
        "nota_mbedv": "gravidade corrigida p/ oficial: Grave->Gravíssima",
    },
    "R1020-GR-d": {
        "titulo": "Manter porta aberta em movimento",
        "gravidade": "grave",
        "pontos": 4,
        "cameras": ["interna", "lateral_direita"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "porta aberta aparece como exemplo sob Art. 169 (Leve); sem ficha Grave própria",
    },
    "R1020-GR-e": {
        "titulo": "Não sinalizar manobra com antecedência",
        "gravidade": "grave",
        "pontos": 4,
        "cameras": ["traseira_esq", "lateral_direita"],
        "artigo_ctb": "Art. 196",
        "ficha_mbedv": "MBEDV-FICHA-196",
    },
    "R1020-GR-f": {
        "titulo": "Não usar cinto de segurança",
        "gravidade": "grave",
        "pontos": 4,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "cinto NÃO tem ficha no anexo MBEDV",
    },
    "R1020-GR-g": {
        "titulo": "Perder controle da direção",
        "gravidade": "grave",
        "pontos": 4,
        "cameras": ["frontal", "interna"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "sem ficha CTB direta (~Art. 175 manobra perigosa)",
    },
    # Médias (2 pts)
    "R1020-M-a": {
        "titulo": "Não usar freio de mão em estacionamento",
        "gravidade": "media",
        "pontos": 2,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": "MBEDV-MEC-freio-mao",
    },
    "R1020-M-b": {
        "titulo": "Velocidade adversa às condições",
        "gravidade": "grave",
        "pontos": 4,
        "cameras": ["frontal"],
        "artigo_ctb": "Art. 220",
        "ficha_mbedv": "MBEDV-FICHA-220",
        "nota_mbedv": "gravidade corrigida p/ oficial: Média->Grave",
    },
    "R1020-M-c": {
        "titulo": "Motor calar",
        "gravidade": "media",
        "pontos": 2,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": "MBEDV-MEC-estol-motor",
    },
    "R1020-M-d": {
        "titulo": "Conversão sem cautelas",
        "gravidade": "media",
        "pontos": 2,
        "cameras": ["frontal", "lateral_direita"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "genérico; ~Art. 207 (conversão local proibido, Grave) não casa 1:1",
    },
    "R1020-M-e": {
        "titulo": "Buzina sem necessidade",
        "gravidade": "leve",
        "pontos": 1,
        "cameras": ["interna"],
        "artigo_ctb": "Art. 227",
        "ficha_mbedv": "MBEDV-FICHA-227",
        "nota_mbedv": "gravidade corrigida p/ oficial: Média->Leve",
    },
    "R1020-M-f": {
        "titulo": "Descer em declive em ponto morto",
        "gravidade": "media",
        "pontos": 2,
        "cameras": ["frontal"],
        "artigo_ctb": None,
        "ficha_mbedv": "MBEDV-MEC-desengrenar-declive",
        "nota_mbedv": "id MEC novo (sem ficha CTB)",
    },
    "R1020-M-g": {
        "titulo": "Não respeitar cautelas obrigatórias",
        "gravidade": "media",
        "pontos": 2,
        "cameras": ["frontal"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "genérico, sem ficha CTB direta",
    },
    "R1020-M-h": {
        "titulo": "Embreagem mal usada",
        "gravidade": "media",
        "pontos": 2,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": "MBEDV-MEC-embreagem-pre-freio",
    },
    "R1020-M-i": {
        "titulo": "Soltar volante em ponto neutro",
        "gravidade": "media",
        "pontos": 2,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": "MBEDV-MEC-ponto-neutro-curva",
    },
    "R1020-M-j": {
        "titulo": "Não usar marchas adequadamente",
        "gravidade": "media",
        "pontos": 2,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": "MBEDV-MEC-engrenar-incorreto",
    },
    # Leves (1 pt)
    "R1020-L-a": {
        "titulo": "Movimentos irregulares com câmbio",
        "gravidade": "leve",
        "pontos": 1,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": "MBEDV-MEC-movimento-irregular",
        "nota_mbedv": "id MEC novo (sem ficha CTB)",
    },
    "R1020-L-b": {
        "titulo": "Não ajustar banco/encosto",
        "gravidade": "leve",
        "pontos": 1,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "preparação; sem ficha CTB",
    },
    "R1020-L-c": {
        "titulo": "Não ajustar espelhos retrovisores",
        "gravidade": "leve",
        "pontos": 1,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "preparação; sem ficha CTB",
    },
    "R1020-L-d": {
        "titulo": "Pisar embreagem em movimento",
        "gravidade": "leve",
        "pontos": 1,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": "MBEDV-MEC-pe-embreagem",
    },
    "R1020-L-e": {
        "titulo": "Painel — luzes ignoradas",
        "gravidade": "leve",
        "pontos": 1,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": None,
        "nota_mbedv": "preparação; sem ficha CTB",
    },
    "R1020-L-f": {
        "titulo": "Partida com marcha engatada",
        "gravidade": "leve",
        "pontos": 1,
        "cameras": ["interna"],
        "artigo_ctb": None,
        "ficha_mbedv": "MBEDV-MEC-partida-engrenado",
    },
    # Conduta ética (v25) — auditadas pelo Gemini a partir do áudio nativo
    "ETICA-xingamento": {
        "titulo": "Xingamento / palavrão",
        "gravidade": "etica",
        "pontos": 4,
        "cameras": ["interna"],
    },
    "ETICA-ameaca": {
        "titulo": "Ameaça verbal / intimidação",
        "gravidade": "etica",
        "pontos": 4,
        "cameras": ["interna"],
    },
    "ETICA-grito": {
        "titulo": "Grito / escalada de volume",
        "gravidade": "etica",
        "pontos": 4,
        "cameras": ["interna"],
    },
    "ETICA-briga": {
        "titulo": "Discussão acalorada / cross-talk",
        "gravidade": "etica",
        "pontos": 4,
        "cameras": ["interna"],
    },
    "ETICA-comportamento_inadequado": {
        "titulo": "Comportamento antiético",
        "gravidade": "etica",
        "pontos": 4,
        "cameras": ["interna"],
    },
}

GRAVIDADE_LABEL = {
    "eliminatoria": "ELIMINATÓRIA",
    "gravissima": "GRAVÍSSIMA",
    "grave": "GRAVE",
    "media": "MÉDIA",
    "leve": "LEVE",
    "etica": "ÉTICA",
}


def _video_by_hash(target_hash: str) -> Path | None:
    """Reverse lookup: hash → video file."""
    if not VIDEOS_DIR.exists():
        return None
    for v in VIDEOS_DIR.iterdir():
        if v.is_file() and _hash_path(v) == target_hash:
            return v
    return None


def _build_infracao(
    idx: int,
    rubric_id: str,
    video_duration_s: float,
    *,
    raw_item: dict | None = None,
    n_frames_extracted: int = 3,
) -> dict:
    """Constrói item Infracao a partir de uma detecção bench.

    Timestamp:
    - Se raw_item tem `ts`/`timestamp`/`t_start` (v23 prompt rico): usa direto
    - Senão, mapeia raw_item.frame (1-indexed) → ts via fórmula uniforme:
        ts = duration * (frame - 0.5) / n_frames_extracted
      (mesma fórmula de extract_frames em run_one_video.py)
    - Fallback final: distribui uniformemente pelo idx
    """
    meta = RUBRIC_META.get(
        rubric_id,
        {
            "titulo": rubric_id,
            "gravidade": "leve",
            "pontos": 1,
            "cameras": ["frontal"],
        },
    )
    t_sec = None
    t_end = None
    if isinstance(raw_item, dict):
        # v25: ts_seconds explícito (preferido)
        # v23/v24: ts/timestamp/t_start (fallback)
        for k in ("ts_seconds", "ts", "timestamp", "t_start", "ts_start"):
            v = raw_item.get(k)
            if isinstance(v, (int, float)) and v >= 0:
                t_sec = int(v)
                break
            if isinstance(v, str) and ":" in v:
                try:
                    parts = v.split(":")
                    t_sec = int(parts[0]) * 60 + int(parts[1])
                    break
                except Exception:
                    pass
        for k in ("ts_end_seconds", "ts_end", "t_end"):
            v = raw_item.get(k)
            if isinstance(v, (int, float)) and v >= 0:
                t_end = int(v)
                break
        # v24: VLMs (Gemini etc) costumam devolver `frame` como índice nativo
        # do vídeo (assumindo 30fps). v2.1: índice 1-N dos frames extraídos.
        # Heurística: se frame > n_frames_extracted é frame nativo → divide por 30.
        if t_sec is None:
            f = raw_item.get("frame")
            if isinstance(f, int) and f >= 1:
                if f > n_frames_extracted * 2:
                    # frame nativo do vídeo (modelo entendeu que era seq frame)
                    t_sec = min(int(video_duration_s), int(f / 30))
                else:
                    t_sec = int(video_duration_s * (f - 0.5) / max(n_frames_extracted, 1))
        # Última tentativa: extrair timestamp do texto da evidência
        if t_sec is None:
            ev = raw_item.get("ev") or raw_item.get("evidencia") or ""
            if isinstance(ev, str):
                import re as _re

                m = (
                    _re.search(r"\bt\s*=\s*(\d+(?:\.\d+)?)\s*s", ev)
                    or _re.search(r"aos?\s+(\d+(?:\.\d+)?)\s*segundos?", ev, _re.IGNORECASE)
                    or _re.search(r"\bt\s*=\s*(\d+)[m:](\d+)\b", ev)
                )
                if m:
                    if len(m.groups()) == 2:
                        t_sec = int(m.group(1)) * 60 + int(m.group(2))
                    else:
                        t_sec = int(float(m.group(1)))
    if t_sec is None:
        # Fallback final — distribui pelo idx (caso raw_item não tenha frame nem ts)
        t_sec = int(video_duration_s * (0.15 + 0.15 * idx))
    if t_end is None:
        t_end = min(int(video_duration_s), t_sec + 5)
    return {
        "id": rubric_id,
        "timestamp_inicio": f"{t_sec // 60:02d}:{t_sec % 60:02d}",
        "timestamp_fim": f"{t_end // 60:02d}:{t_end % 60:02d}",
        "duracao_seg": t_end - t_sec,
        "duracao_fmt": f"{t_end - t_sec}s",
        "occurrences": 1,
        "gravidade": meta["gravidade"],
        "gravidade_label": GRAVIDADE_LABEL[meta["gravidade"]],
        "pontos": meta["pontos"],
        "confianca": "ALTA",
        "cameras": meta["cameras"],
        "cameras_fmt": " + ".join(c.replace("_", " ").title() for c in meta["cameras"]),
        "titulo": meta["titulo"],
        "descricao": meta["titulo"],
        "descricao_longa": meta["titulo"],
        "evidencia": (raw_item.get("ev") if isinstance(raw_item, dict) else None)
        or "Detecção do bench — modelo VLM acusou o ID conforme catálogo CONTRAN.",
        "base_legal": "Res. CONTRAN 1.020/2025, Anexo II"
        if rubric_id.startswith("R1020-")
        else "Conduta Ética em ambiente DETRAN",
        "veredito": "detectado",
        "origem": "infracoes_detectadas",
        "ator": (raw_item.get("ator") if isinstance(raw_item, dict) else None),
    }


# ---------------------------------------------------------------------------
# _build_response_from_upload — fix do 500 em /api/analyses/hash/{hash}/result
# ---------------------------------------------------------------------------
# Esta função estava sendo CHAMADA por analyses_result() mas nunca fora
# DEFINIDA → NameError → HTTP 500, quebrando a Fila do Auditor e a Análise do
# Supervisor (que dependem do laudo/infrações da IA por exame).
#
# Ela resolve o resultado real do exame na melhor fonte disponível, NA ORDEM:
#   1) result.json local (ANALYSES_DIR/<hash>/result.json) — fluxo de upload
#      via signed URL → análise Gemini (intenção original do nome da função).
#   2) gs_result_json no GCS — quando o banco aponta pro JSON no bucket.
#   3) Banco relacional via db.laudo_dossie(hash) → exam_infractions
#      (bloco 7_analise_detalhada do /laudo-json, que JÁ funciona).
#
# Retorna o MESMO shape que o caminho "bench" de analyses_result produz
# (summary / scored.infracoes / exame / timeline / _paths ...), pro frontend
# não precisar de adaptação.
#
# Se NÃO houver exame nem resultado → retorna None (analyses_result cai no
# fluxo bench → 404 gracioso). NUNCA levanta — qualquer erro vira None.
# ---------------------------------------------------------------------------

# gravidade do exam_infractions (com/sem acento) → chave canônica de
# GRAVIDADE_LABEL / contagem. Normaliza "gravíssima" → "gravissima" etc.
_GRAV_CANON = {
    "eliminatoria": "eliminatoria",
    "eliminatória": "eliminatoria",
    "gravissima": "gravissima",
    "gravíssima": "gravissima",
    "grave": "grave",
    "media": "media",
    "média": "media",
    "leve": "leve",
    "etica": "etica",
    "ética": "etica",
}
# pontos default por gravidade canônica (quando a infração não traz pontos).
_GRAV_PONTOS = {
    "eliminatoria": 0,
    "gravissima": 6,
    "grave": 4,
    "media": 3,
    "leve": 1,
    "etica": 1,
}


def _norm_gravidade(g) -> str:
    s = str(g or "").strip().lower()
    return _GRAV_CANON.get(s, "leve")


# --- Enriquecimento conservador (laudo-json) ------------------------------------
# Campos DERIVADOS dos dados crus. Acrescentam, nunca substituem. Toda função
# devolve None quando o dado de origem não existe → o spread no chamador omite/
# nula o campo, sem inventar valor.

# Mapeamento canônico quadrante (layout VIP/VLM) ⇄ câmera. Espelha o layout
# usado no pipeline (_mock_analyze_result: TL=frontal, TR=lateral_direita,
# BL=interna, BR=traseira_esq).
_QUADRANTE_CAMERA = {
    "TL": "frontal",
    "TR": "lateral_direita",
    "BL": "interna",
    "BR": "traseira_esq",
}
_CAMERA_QUADRANTE = {v: k for k, v in _QUADRANTE_CAMERA.items()}

# Rótulos legíveis por câmera canônica.
_CAMERA_LABEL = {
    "frontal": "Frontal",
    "lateral_direita": "Lateral Direita",
    "lateral_esquerda": "Lateral Esquerda",
    "interna": "Interna",
    "traseira_esq": "Traseira Esquerda",
    "traseira": "Traseira",
}


def _fmt_mmss(seconds) -> str | None:
    """Segundos → "mm:ss" (ou "hh:mm:ss" se >= 1h). None se entrada inválida."""
    try:
        s = int(float(seconds))
    except (TypeError, ValueError):
        return None
    if s < 0:
        return None
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def _conf_pct(raw) -> int | None:
    """Confiança crua → inteiro 0–100. Aceita fração (0–1) ou já-percentual
    (1–100). None se ausente/inválida."""
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v <= 1.0:
        v *= 100.0
    return max(0, min(100, int(round(v))))


def _norm_camera_label(raw) -> str | None:
    """Normaliza um identificador de câmera (snake/quadrante/livre) para a chave
    canônica. None se vazio."""
    s = str(raw or "").strip().lower().replace(" ", "_")
    if not s:
        return None
    if s.upper() in _QUADRANTE_CAMERA:  # veio quadrante (TL/TR/BL/BR)
        return _QUADRANTE_CAMERA[s.upper()]
    return s


def _camera_label_legivel(canon: str | None) -> str | None:
    """Chave canônica de câmera → rótulo legível. Fallback: Title-case do snake."""
    if not canon:
        return None
    return _CAMERA_LABEL.get(canon, str(canon).replace("_", " ").title())


def _enriquecer_infracao(inf: dict, duration_s: float) -> dict:
    """Acrescenta campos derivados a um item de infração (bloco 7), preservando
    todo o conteúdo existente via spread. Campo sem origem → omitido."""
    extra: dict = {}
    # tempo absoluto em segundos (a partir do timestamp_inicio "mm:ss" já montado)
    t_ini = inf.get("timestamp_inicio")
    if isinstance(t_ini, str) and ":" in t_ini:
        try:
            parts = [int(p) for p in t_ini.split(":")]
            seg = parts[-1] + parts[-2] * 60 + (parts[-3] * 3600 if len(parts) == 3 else 0)
            extra["timestamp_inicio_seg"] = seg
            if duration_s and duration_s > 0:
                extra["posicao_pct"] = max(0, min(100, round(seg / duration_s * 100, 1)))
        except (ValueError, IndexError):
            pass
    # confiança normalizada em %
    pct = _conf_pct(inf.get("confianca_raw", inf.get("_confianca_raw")))
    if pct is not None:
        extra["confianca_pct"] = pct
    # câmeras normalizadas + câmera principal + ângulo/quadrante
    cams = inf.get("cameras")
    if isinstance(cams, list) and cams:
        cams_norm = [c for c in (_norm_camera_label(x) for x in cams) if c]
        if cams_norm:
            extra["cameras_norm"] = cams_norm
            principal = cams_norm[0]
            extra["camera_principal"] = principal
            extra["camera_origem"] = principal
            extra["angulo_camera"] = _camera_label_legivel(principal)
            quad = _CAMERA_QUADRANTE.get(principal)
            if quad:
                extra["quadrante_origem"] = quad
    # Conservador: só acrescenta o que ainda não existe (nunca sobrescreve).
    return {**{k: v for k, v in extra.items() if k not in inf}, **inf}


def _enriquecer_evento(ev: dict, duration_s: float) -> dict:
    """Acrescenta campos derivados a um evento bruto (bloco 12b_linha_tempo /
    exam_eventos), preservando o registro cru via spread. Origem ausente → omite.

    Crus em exam_eventos: timestamp_video_seg, timestamp_audio_seg, duracao_seg,
    confianca, camera_origem, quadrante_origem, canal_evidencia, etc.
    """
    if not isinstance(ev, dict):
        return ev
    extra: dict = {}
    ts = ev.get("timestamp_video_seg")
    if ts is None:
        ts = ev.get("timestamp_audio_seg")
    fmt = _fmt_mmss(ts)
    if fmt is not None:
        extra["timestamp_fmt"] = fmt
        try:
            seg = int(float(ts))
            extra["timestamp_seg"] = seg
            fim = seg
            dur = ev.get("duracao_seg")
            if dur is not None:
                try:
                    fim = seg + int(float(dur))
                except (TypeError, ValueError):
                    fim = seg
            if fim != seg:
                extra["timestamp_fim_fmt"] = _fmt_mmss(fim)
            if duration_s and duration_s > 0:
                extra["posicao_pct"] = max(0, min(100, round(seg / duration_s * 100, 1)))
        except (TypeError, ValueError):
            pass
    dur_fmt = _fmt_mmss(ev.get("duracao_seg"))
    if dur_fmt is not None:
        extra["duracao_fmt"] = dur_fmt
    pct = _conf_pct(ev.get("confianca"))
    if pct is not None:
        extra["confianca_pct"] = pct
    # câmera / ângulo / quadrante — preenche o que faltar a partir do que existe.
    cam = _norm_camera_label(ev.get("camera_origem")) or _norm_camera_label(
        ev.get("quadrante_origem")
    )
    if cam:
        extra["camera_norm"] = cam
        extra["angulo_camera"] = _camera_label_legivel(cam)
        if not ev.get("quadrante_origem") and _CAMERA_QUADRANTE.get(cam):
            extra["quadrante_origem"] = _CAMERA_QUADRANTE[cam]
    # Conservador: o registro cru tem precedência; só acrescenta o que falta
    # (exceto quadrante_origem nulo, que aceitamos preencher por inferência).
    merged = {**extra, **ev}
    if "quadrante_origem" in extra and not ev.get("quadrante_origem"):
        merged["quadrante_origem"] = extra["quadrante_origem"]
    return merged


def _infracao_from_db(idx: int, item: dict, duration_s: float) -> dict:
    """Constrói um item Infracao (shape do frontend) a partir de uma linha de
    exam_infractions (via db.laudo_dossie → bloco 7_analise_detalhada)."""
    grav = _norm_gravidade(item.get("gravidade"))
    try:
        pontos = (
            int(item.get("pontos")) if item.get("pontos") is not None else _GRAV_PONTOS.get(grav, 1)
        )
    except (TypeError, ValueError):
        pontos = _GRAV_PONTOS.get(grav, 1)
    # timestamp
    try:
        t_sec = int(float(item.get("timestamp_s"))) if item.get("timestamp_s") is not None else None
    except (TypeError, ValueError):
        t_sec = None
    if t_sec is None:
        t_sec = int(duration_s * (0.15 + 0.15 * idx))
    try:
        dur = int(float(item.get("duracao_s"))) if item.get("duracao_s") is not None else 5
    except (TypeError, ValueError):
        dur = 5
    if dur <= 0:
        dur = 5
    t_end = min(int(duration_s) if duration_s else t_sec + dur, t_sec + dur)
    if t_end <= t_sec:
        t_end = t_sec + dur
    # cameras
    cams = item.get("cameras")
    if isinstance(cams, str):
        try:
            cams = json.loads(cams)
        except Exception:
            cams = [cams] if cams else []
    if not isinstance(cams, list) or not cams:
        cams = ["frontal"]
    # confianca
    conf_raw = item.get("confianca")
    try:
        cf = float(conf_raw) if conf_raw is not None else 0.9
    except (TypeError, ValueError):
        cf = 0.9
    confianca = "ALTA" if cf >= 0.85 else "MÉDIA" if cf >= 0.6 else "BAIXA"
    rid = item.get("regra_id") or item.get("id") or "R1020-L-c"
    descricao = item.get("descricao") or str(rid)
    base_legal = item.get("base_legal") or (
        "Res. CONTRAN 1.020/2025, Anexo II"
        if str(rid).startswith("R1020-")
        else "Conduta no ambiente DETRAN"
    )
    base = {
        "id": rid,
        "timestamp_inicio": f"{t_sec // 60:02d}:{t_sec % 60:02d}",
        "timestamp_fim": f"{t_end // 60:02d}:{t_end % 60:02d}",
        "timestamp_inicio_seg": t_sec,
        "timestamp_fim_seg": t_end,
        "duracao_seg": t_end - t_sec,
        "duracao_fmt": f"{t_end - t_sec}s",
        "occurrences": 1,
        "gravidade": grav,
        "gravidade_label": GRAVIDADE_LABEL.get(grav, grav.upper()),
        "pontos": pontos,
        "confianca": confianca,
        # confiança crua preservada p/ o enriquecedor derivar confianca_pct.
        "confianca_raw": cf,
        "cameras": cams,
        "cameras_fmt": " + ".join(str(c).replace("_", " ").title() for c in cams),
        "titulo": descricao,
        "descricao": descricao,
        "descricao_longa": descricao,
        "evidencia": item.get("evidence") or descricao,
        "base_legal": base_legal,
        "veredito": item.get("status") or "detectado",
        "origem": "exam_infractions",
        "ator": None,
    }
    # Acrescenta campos derivados (ângulo de câmera, % de confiança, posição
    # relativa) sem mexer no que já existe.
    return _enriquecer_infracao(base, duration_s)


def _response_from_db(hash: str):
    """Monta o laudo_response a partir do banco (db.laudo_dossie). None se DB
    off, exame inexistente ou erro. Nunca levanta."""
    try:
        dossie = db.laudo_dossie(hash)
    except Exception as e:  # noqa: BLE001
        try:
            log.warning("_response_from_db laudo_dossie falhou %s: %s", hash[:12], e)
        except Exception:
            pass
        return None
    if not dossie:
        return None
    exam = dossie.get("exam") or {}
    if not exam:
        return None
    infracoes_db = dossie.get("infracoes") or []
    try:
        duration_s = float(exam.get("duration_s") or 0) or 295.0
    except (TypeError, ValueError):
        duration_s = 295.0

    infracoes_list = []
    for i, item in enumerate(infracoes_db):
        if isinstance(item, dict):
            try:
                infracoes_list.append(_infracao_from_db(i, item, duration_s))
            except Exception:
                continue

    pontuacao_total = sum(inf["pontos"] for inf in infracoes_list)
    # Prefere o veredito persistido no exame; senão deriva da pontuação.
    aprovado = exam.get("aprovado")
    if aprovado is None:
        aprovado = pontuacao_total <= 10
    contagem = {"eliminatoria": 0, "gravissima": 0, "grave": 0, "media": 0, "leve": 0, "etica": 0}
    for inf in infracoes_list:
        contagem[inf["gravidade"]] = contagem.get(inf["gravidade"], 0) + 1
    score_risco = min(100, pontuacao_total * 10)
    confianca_media = 90 if infracoes_list else 80
    cameras_envolvidas = sorted({c for inf in infracoes_list for c in inf["cameras"]})
    timeline_entries = [
        {
            "timestamp": inf["timestamp_inicio"],
            "description": inf["titulo"],
            "gravidade": inf["gravidade"],
            "gravidade_label": inf["gravidade_label"],
            "pct": (
                int(inf["timestamp_inicio"].split(":")[0]) * 60
                + int(inf["timestamp_inicio"].split(":")[1])
            )
            / max(duration_s, 1)
            * 100,
        }
        for inf in infracoes_list
    ]
    created_at = exam.get("created_at")
    try:
        created_at = (
            created_at.isoformat() if hasattr(created_at, "isoformat") else (created_at or "")
        )
    except Exception:
        created_at = ""

    laudo_response = {
        "summary": {
            "laudo_id": f"LAU-{(exam.get('external_id') or hash[:8])}",
            "video_path": "",
            "video_hash": hash,
            "result_hash": f"db__{hash[:12]}__{len(infracoes_list)}",
            "pdf_path": "",
            "rubrica": "1020/2025",
            "aprovado": bool(aprovado),
            "pontuacao_total": pontuacao_total,
            "contagem": contagem,
            "duracao_seg": int(duration_s),
            "num_infracoes": len(infracoes_list),
            "num_frames": int(duration_s),
            "elapsed_sec": 0,
            "created_at": created_at,
            "model_version": "db-laudo-dossie",
            "software_version": "db-1.0",
            "score_risco": score_risco,
            "confianca_media": confianca_media,
            "cameras_envolvidas": cameras_envolvidas,
            "duracao_total_infracoes_seg": sum(inf["duracao_seg"] for inf in infracoes_list),
            "densidade_infracoes_por_min": (len(infracoes_list) / max(duration_s, 1)) * 60,
        },
        "scored": {
            "infracoes": infracoes_list,
            "contagem": contagem,
            "pontuacao_total": pontuacao_total,
            "aprovado": bool(aprovado),
            "motivo_reprovacao": None if aprovado else f"{pontuacao_total} pts > 10",
        },
        "vlm": {"events": [], "timeline": [], "positive_aspects": [], "attention_points": []},
        "timeline": timeline_entries,
        "positivos": [],
        "pontos_atencao": [],
        "exame": {
            "candidato": exam.get("candidato_nome") or "—",
            "cpf": exam.get("candidato_cpf") or "—",
            "renach": exam.get("renach") or "—",
            "processo": str(exam.get("external_id") or "—"),
            "categoria": exam.get("categoria") or "—",
            "veiculo": exam.get("veiculo") or "—",
            "local": exam.get("local_unidade") or "—",
            "examinador": exam.get("examinador") or "—",
            "data_exame": (created_at or "")[:10],
        },
        "canonical": {},
        "context_keys": [],
        "_paths": {
            "video_static": "",
            "analysis_hash": hash,
            "base_static": f"/static/analyses/{hash}",
            "pdf_url": None,
        },
        "_source": "db",
    }
    return laudo_response


def _read_training_annotations(hash: str) -> list:
    """Lê os comentários do examinador TechPrático do upload.json daquele hash.

    Fonte: ANALYSES_DIR/<hash>/upload.json, campo `training_annotations`
    (array de {"timestamp": "...", "anotacoes": "..."}). Preenchido em ~1237
    dos 2116 exames. RESILIENTE: qualquer falha (arquivo ausente, JSON
    corrompido, campo não-lista) → devolve [], NUNCA levanta.

    Ordem: upload.json local → gs_path do upload (best-effort). Local basta.
    """
    # 1) upload.json local
    try:
        up = ANALYSES_DIR / hash / "upload.json"
        if up.exists():
            d = json.loads(up.read_text() or "{}")
            ta = d.get("training_annotations")
            if isinstance(ta, list):
                return ta
    except Exception as e:  # noqa: BLE001
        try:
            log.warning("_read_training_annotations local falhou %s: %s", hash[:12], e)
        except Exception:
            pass
    # 2) gs_path do upload (best-effort; local normalmente basta)
    try:
        gs_uri = None
        try:
            dossie_peek = db.laudo_dossie(hash)
            if dossie_peek:
                gs_uri = (dossie_peek.get("exam") or {}).get("gs_upload_json")
        except Exception:
            gs_uri = None
        if gs_uri and str(gs_uri).startswith("gs://"):
            raw = _download_gcs_json(str(gs_uri))
            if isinstance(raw, dict):
                ta = raw.get("training_annotations")
                if isinstance(ta, list):
                    return ta
    except Exception:
        pass
    return []


def _build_response_from_upload(hash: str):
    """Resolve o resultado de um exame na melhor fonte e devolve o shape do
    frontend. None → analyses_result cai no fluxo bench (404 gracioso).

    Ordem: result.json local → gs_result_json (GCS) → banco (laudo_dossie).
    NUNCA levanta exceção (qualquer falha vira None ou cai pra próxima fonte).
    """
    # 1) result.json local (fluxo de upload via signed URL → Gemini)
    try:
        local_result = ANALYSES_DIR / hash / "result.json"
        if local_result.exists():
            raw = json.loads(local_result.read_text() or "{}")
            built = _response_from_result_json(hash, raw)
            if built is not None:
                return built
    except Exception as e:  # noqa: BLE001
        try:
            log.warning("_build_response_from_upload result.json local falhou %s: %s", hash[:12], e)
        except Exception:
            pass

    # 2) gs_result_json no GCS (quando o banco aponta pro JSON no bucket)
    try:
        gs_uri = None
        try:
            dossie_peek = db.laudo_dossie(hash)
            if dossie_peek:
                gs_uri = (dossie_peek.get("exam") or {}).get("gs_result_json")
        except Exception:
            gs_uri = None
        if gs_uri and str(gs_uri).startswith("gs://"):
            raw = _download_gcs_json(str(gs_uri))
            if raw:
                built = _response_from_result_json(hash, raw)
                if built is not None:
                    return built
    except Exception as e:  # noqa: BLE001
        try:
            log.warning("_build_response_from_upload gs_result_json falhou %s: %s", hash[:12], e)
        except Exception:
            pass

    # 3) Banco relacional (exam_infractions via laudo_dossie)
    return _response_from_db(hash)


def _download_gcs_json(gs_uri: str):
    """Baixa e parseia um JSON de gs://bucket/path. None em qualquer falha."""
    try:
        rest = gs_uri[len("gs://") :]
        bucket_name, _, blob_path = rest.partition("/")
        if not bucket_name or not blob_path:
            return None
        client = _gcs_client()
        blob = client.bucket(bucket_name).blob(blob_path)
        data = blob.download_as_bytes()
        return json.loads(data.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        try:
            log.warning("_download_gcs_json falhou %s: %s", gs_uri, e)
        except Exception:
            pass
        return None


def _load_result_raw(hash: str, gs_uri: str | None = None) -> dict | None:
    """Carrega o result.json CRU do Gemini de um exame (sem montar shape).
    Ordem: result.json local → gs_result_json (GCS). None se nenhum. Nunca levanta.
    Usado pra surfaciar campos informativos do result que não viram coluna no DB
    (ex.: `checklist_anexo_k`, `cobertura_integral`)."""
    try:
        local_result = ANALYSES_DIR / hash / "result.json"
        if local_result.exists():
            raw = json.loads(local_result.read_text() or "{}")
            if isinstance(raw, dict):
                return raw
    except Exception:  # noqa: BLE001
        pass
    try:
        if gs_uri and str(gs_uri).startswith("gs://"):
            raw = _download_gcs_json(str(gs_uri))
            if isinstance(raw, dict):
                return raw
    except Exception:  # noqa: BLE001
        pass
    return None


def _response_from_result_json(hash: str, raw: dict):
    """Constrói o shape do frontend a partir de um result.json (Gemini/pipeline).
    Usa as infrações avaliadas/detectadas do JSON. None se sem infrações
    utilizáveis E sem dossiê (deixa cair pra fonte do banco). Nunca levanta."""
    if not isinstance(raw, dict):
        return None
    # infrações: prioriza infracoes_avaliadas (pós-scoring), senão detectadas.
    raw_infracoes = (
        raw.get("infracoes_avaliadas")
        or raw.get("infracoes_detectadas")
        or raw.get("infracoes")
        or []
    )
    if not isinstance(raw_infracoes, list):
        raw_infracoes = []
    video = raw.get("video") or {}
    try:
        duration_s = float(video.get("duration_s") or raw.get("duracao_seg") or 0) or 295.0
    except (TypeError, ValueError):
        duration_s = 295.0
    # Sem infrações no JSON → tenta o banco (que pode ter exam_infractions).
    if not raw_infracoes:
        return None

    infracoes_list = []
    for i, item in enumerate(raw_infracoes):
        try:
            if isinstance(item, dict):
                rid = item.get("id") or item.get("codigo") or item.get("regra_id") or "R1020-L-c"
                inf = _build_infracao(i, rid, duration_s, raw_item=item)
                # O result.json carrega gravidade/pontos POR INFRAÇÃO (pós-scoring
                # do pipeline) — mais confiável que o RUBRIC_META local. Honra
                # `severidade`/`gravidade`/`pontos` do item quando presentes.
                _grav_raw = item.get("gravidade") or item.get("severidade")
                if _grav_raw:
                    g = _norm_gravidade(_grav_raw)
                    inf["gravidade"] = g
                    inf["gravidade_label"] = GRAVIDADE_LABEL.get(g, g.upper())
                if item.get("pontos") is not None:
                    try:
                        inf["pontos"] = int(item.get("pontos"))
                    except (TypeError, ValueError):
                        pass
                infracoes_list.append(inf)
            elif isinstance(item, str):
                infracoes_list.append(_build_infracao(i, item, duration_s))
        except Exception:
            continue
    if not infracoes_list:
        return None

    pontuacao_total = sum(inf["pontos"] for inf in infracoes_list)
    aprovado = raw.get("aprovado")
    if aprovado is None:
        aprovado = pontuacao_total <= 10
    contagem = {"eliminatoria": 0, "gravissima": 0, "grave": 0, "media": 0, "leve": 0, "etica": 0}
    for inf in infracoes_list:
        contagem[inf["gravidade"]] = contagem.get(inf["gravidade"], 0) + 1
    score_risco = min(100, pontuacao_total * 10)
    cameras_envolvidas = sorted({c for inf in infracoes_list for c in inf["cameras"]})
    timeline_entries = [
        {
            "timestamp": inf["timestamp_inicio"],
            "description": inf["titulo"],
            "gravidade": inf["gravidade"],
            "gravidade_label": inf["gravidade_label"],
            "pct": (
                int(inf["timestamp_inicio"].split(":")[0]) * 60
                + int(inf["timestamp_inicio"].split(":")[1])
            )
            / max(duration_s, 1)
            * 100,
        }
        for inf in infracoes_list
    ]
    exame_src = raw.get("exame") or raw.get("candidato") or {}
    return {
        "summary": {
            "laudo_id": f"LAU-{hash[:8].upper()}",
            "video_path": "",
            "video_hash": hash,
            "result_hash": f"json__{hash[:12]}__{len(infracoes_list)}",
            "pdf_path": "",
            "rubrica": "1020/2025",
            "aprovado": bool(aprovado),
            "pontuacao_total": pontuacao_total,
            "contagem": contagem,
            "duracao_seg": int(duration_s),
            "num_infracoes": len(infracoes_list),
            "num_frames": int(duration_s),
            "elapsed_sec": 0,
            "created_at": raw.get("created_at") or "",
            "model_version": raw.get("model_version") or "gemini",
            "software_version": "result-json-1.0",
            "score_risco": score_risco,
            "confianca_media": 90 if infracoes_list else 80,
            "cameras_envolvidas": cameras_envolvidas,
            "duracao_total_infracoes_seg": sum(inf["duracao_seg"] for inf in infracoes_list),
            "densidade_infracoes_por_min": (len(infracoes_list) / max(duration_s, 1)) * 60,
        },
        "scored": {
            "infracoes": infracoes_list,
            "contagem": contagem,
            "pontuacao_total": pontuacao_total,
            "aprovado": bool(aprovado),
            "motivo_reprovacao": None if aprovado else f"{pontuacao_total} pts > 10",
        },
        "vlm": {"events": [], "timeline": [], "positive_aspects": [], "attention_points": []},
        "timeline": timeline_entries,
        "positivos": [],
        "pontos_atencao": [],
        "exame": {
            "candidato": exame_src.get("candidato") or exame_src.get("nome") or "—",
            "cpf": exame_src.get("cpf") or "—",
            "renach": exame_src.get("renach") or "—",
            "processo": str(exame_src.get("processo") or exame_src.get("external_id") or "—"),
            "categoria": exame_src.get("categoria") or "—",
            "veiculo": exame_src.get("veiculo") or "—",
            "local": exame_src.get("local") or "—",
            "examinador": exame_src.get("examinador") or "—",
            "data_exame": (raw.get("created_at") or "")[:10],
        },
        "canonical": {},
        "context_keys": [],
        "_paths": {
            "video_static": "",
            "analysis_hash": hash,
            "base_static": f"/static/analyses/{hash}",
            "pdf_url": None,
        },
        "_source": "result_json",
    }


@app.get("/api/analyses/hash/{hash}/result")
def analyses_result(hash: str, model: str | None = None):
    """Adapter: serve resultado pro frontend.

    Procura primeiro em `ANALYSES_DIR/<hash>/result.json` (uploads via signed
    URL → análise Gemini). Se não existir, cai no fluxo bench (`STORAGE/<slug>`)
    pra back-compat com vídeos de avaliação multi-modelo.

    Query params:
    - model: opcional. Só aplicável ao fluxo bench. Ignorado pro fluxo Gemini.
    """
    # Comentários do examinador TechPrático (upload.json → training_annotations).
    # Resiliente: [] se ausente. Injetado em TODO caminho de retorno (upload,
    # banco e bench) — top-level `training_annotations` E `exame.training_annotations`.
    _train_ann = _read_training_annotations(hash)

    upload_result = _build_response_from_upload(hash)
    if upload_result is not None:
        upload_result["training_annotations"] = _train_ann
        try:
            upload_result.setdefault("exame", {})["training_annotations"] = _train_ann
        except Exception:
            pass
        return upload_result

    video = _video_by_hash(hash)
    if not video:
        raise HTTPException(404, f"hash {hash} não corresponde a nenhum vídeo")
    slug = _video_filename_to_slug(video.name)
    slug_dir = STORAGE / slug
    run_dir = _latest_run(slug_dir)
    if not run_dir:
        raise HTTPException(404, f"sem run bench pra slug {slug}")
    summary = json.loads((run_dir / "summary.json").read_text())

    models = _resolve_summary_models(run_dir, summary)

    # Se usuário escolheu um modelo específico, usa ele direto. Senão,
    # seleciona o "campeão" do run: o que detectou mais infrações com parse OK.
    selected_model_id: str | None = None
    if model and model in models:
        selected_model_id = model
    else:
        best_count = -1
        for mid, info in models.items():
            if info.get("status") != "ok":
                continue
            # v2.1 usa "laudo_parsed_ok"; v23 usa "parse_ok"
            if not (info.get("laudo_parsed_ok") or info.get("parse_ok")):
                continue
            c = info.get("infracoes_count") or 0
            if c > best_count:
                best_count = c
                selected_model_id = mid
    best_model_id = selected_model_id

    if best_model_id is None:
        raise HTTPException(503, "nenhum modelo do bench parseou OK")

    # Carrega laudo do campeão
    model_dir = _resolve_model_dir(run_dir, best_model_id)
    laudo_raw_path = model_dir / "laudo.json"
    laudo_raw = {}
    if laudo_raw_path.exists():
        laudo_raw = json.loads(laudo_raw_path.read_text())

    # Infrações detectadas — pega lista do laudo do campeão
    raw_infracoes = laudo_raw.get("infracoes", [])
    if not isinstance(raw_infracoes, list):
        raw_infracoes = []

    duration_s = 295.0  # fallback; idealmente vir de ffprobe — mas custa tempo
    try:
        import subprocess as _sp

        out = _sp.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video),
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        duration_s = float(out.stdout.strip() or 295)
    except Exception:
        pass

    infracoes_list = []
    for i, item in enumerate(raw_infracoes):
        if isinstance(item, dict):
            rid = item.get("id") or item.get("codigo") or "R1020-L-c"
            infracoes_list.append(_build_infracao(i, rid, duration_s, raw_item=item))
        elif isinstance(item, str):
            infracoes_list.append(_build_infracao(i, item, duration_s))
        else:
            continue

    pontuacao_total = sum(inf["pontos"] for inf in infracoes_list)
    aprovado = pontuacao_total <= 10
    contagem = {"eliminatoria": 0, "gravissima": 0, "grave": 0, "media": 0, "leve": 0, "etica": 0}
    for inf in infracoes_list:
        contagem[inf["gravidade"]] = contagem.get(inf["gravidade"], 0) + 1

    score_risco = min(100, pontuacao_total * 10)
    confianca_media = 95 if infracoes_list else 80
    cameras_envolvidas = sorted({c for inf in infracoes_list for c in inf["cameras"]})

    timeline_entries = [
        {
            "timestamp": inf["timestamp_inicio"],
            "description": inf["titulo"],
            "gravidade": inf["gravidade"],
            "gravidade_label": inf["gravidade_label"],
            "pct": (
                int(inf["timestamp_inicio"].split(":")[0]) * 60
                + int(inf["timestamp_inicio"].split(":")[1])
            )
            / max(duration_s, 1)
            * 100,
        }
        for inf in infracoes_list
    ]

    laudo_response = {
        "summary": {
            "laudo_id": f"LAU-BENCH-{slug.upper()[:8]}",
            "video_path": f"storage/videos/{video.name}",
            "video_hash": hash,
            # Inclui o model_id no result_hash pra invalidar cache do frontend
            # quando trocar a IA selecionada (a checagem prev.result_hash === new
            # dropava a atualização do laudo se mantivesse o mesmo timestamp do run).
            "result_hash": f"{run_dir.name}__{best_model_id.replace('/', '__')}",
            "pdf_path": "",
            "rubrica": "1020/2025",
            "aprovado": aprovado,
            "pontuacao_total": pontuacao_total,
            "contagem": contagem,
            "duracao_seg": int(duration_s),
            "num_infracoes": len(infracoes_list),
            "num_frames": int(duration_s),
            "elapsed_sec": summary.get("total_elapsed_s", 0),
            "created_at": summary.get("started_at", datetime.utcnow().isoformat() + "Z"),
            "model_version": best_model_id,
            "software_version": "bench-v2.1",
            "score_risco": score_risco,
            "confianca_media": confianca_media,
            "cameras_envolvidas": cameras_envolvidas,
            "duracao_total_infracoes_seg": sum(inf["duracao_seg"] for inf in infracoes_list),
            "densidade_infracoes_por_min": (len(infracoes_list) / max(duration_s, 1)) * 60,
        },
        "scored": {
            "infracoes": infracoes_list,
            "contagem": contagem,
            "pontuacao_total": pontuacao_total,
            "aprovado": aprovado,
            "motivo_reprovacao": None if aprovado else f"{pontuacao_total} pts > 10",
        },
        "vlm": {
            "events": [],
            "timeline": [],
            "positive_aspects": [],
            "attention_points": [],
        },
        "timeline": timeline_entries,
        "positivos": [],
        "pontos_atencao": [],
        "exame": {
            "candidato": "—",
            "cpf": "—",
            "renach": "—",
            "processo": "—",
            "categoria": "—",
            "veiculo": "—",
            "local": "—",
            "examinador": "—",
            "data_exame": summary.get("started_at", "")[:10],
        },
        "canonical": {},
        "context_keys": [],
        "_paths": {
            "video_static": f"/static/videos/{video.name}",
            "analysis_hash": hash,
            "base_static": f"/static/analyses/{hash}",
            "pdf_url": None,
        },
        # Lista das IAs disponíveis no run bench, pra popular dropdown
        # de seleção de modelo no AnaliseExame. selected_model_id indica
        # qual está exibido no momento.
        "_bench_models": [
            {
                "model_id": mid,
                "label": info.get("label") or mid,
                "status": info.get("status"),
                "infracoes_count": info.get("infracoes_count"),
                "cost_usd": info.get("cost_usd", 0),
                "actual_modality": _detect_actual_modality(_resolve_model_dir(run_dir, mid), mid),
            }
            for mid, info in models.items()
        ],
        "_selected_model_id": best_model_id,
    }
    laudo_response["training_annotations"] = _train_ann
    laudo_response["exame"]["training_annotations"] = _train_ann
    return laudo_response


@app.get("/api/laudo-atual")
def laudo_atual():
    """Atalho: retorna o laudo do primeiro vídeo com bench disponível."""
    if not VIDEOS_DIR.exists():
        raise HTTPException(404, "Sem vídeos")
    for v in sorted(VIDEOS_DIR.iterdir()):
        if not v.is_file():
            continue
        slug = _video_filename_to_slug(v.name)
        if (STORAGE / slug).exists():
            return analyses_result(_hash_path(v))
    raise HTTPException(404, "Nenhum vídeo com bench disponível")


@app.get("/api/analyses/{hash}/annotations")
def analyses_annotations(hash: str):
    """Stub: sem anotações humanas no bench. Retorna lista vazia."""
    return []


@app.get("/api/bench/{slug}/laudo/{model_id:path}")
def bench_laudo(slug: str, model_id: str):
    """Retorna o laudo cru de um modelo específico do último run do slug."""
    slug_dir = STORAGE / slug
    run_dir = _latest_run(slug_dir)
    if not run_dir:
        raise HTTPException(404, f"slug {slug} sem run")
    model_dir = _resolve_model_dir(run_dir, model_id)
    if not model_dir.exists():
        raise HTTPException(404, f"modelo {model_id} não rodou em {slug}")
    laudo_path = model_dir / "laudo.json"
    raw_path = model_dir / "raw_response.json"
    out: dict = {"slug": slug, "run_id": run_dir.name, "model_id": model_id}
    if laudo_path.exists():
        out["laudo"] = json.loads(laudo_path.read_text())
    if raw_path.exists():
        raw = json.loads(raw_path.read_text())
        out["raw_text"] = raw.get("raw_text", "")
        out["status"] = raw.get("status")
        out["elapsed_s"] = raw.get("elapsed_s")
        out["cost_usd"] = raw.get("cost_usd", 0)
        out["tokens_in"] = raw.get("tokens_in", 0)
        out["tokens_out"] = raw.get("tokens_out", 0)
    return out


# ============================================================================
# /static/videos/{filename} — serve mp4 do storage/videos/ pra <video> tag
# ============================================================================


@app.get("/static/videos/{filename}")
def serve_video(filename: str):
    """Serve mp4 com Accept-Ranges: bytes pra permitir seek do <video> HTML5.

    Sanitiza filename: rejeita paths com '..' ou separadores. Procura só em
    storage/videos/. 404 se não existir, 403 se path tentar escapar.
    """
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(403, "filename inválido")
    target = (VIDEOS_DIR / filename).resolve()
    try:
        target.relative_to(VIDEOS_DIR.resolve())
    except ValueError as e:
        raise HTTPException(403, "path fora de storage/videos") from e
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"vídeo {filename} não encontrado")
    # FileResponse já adiciona Content-Length; FastAPI/Starlette suporta Range
    # nativamente quando o cliente envia Range header.
    return FileResponse(
        path=str(target),
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
        filename=filename,
    )


# ============================================================================
# Parecer-Auditor por HASH (reconciliação) — esteira de auditoria humana.
# Blocos copiados do repo. `_mask_cpf`/`_verify_session` já existem em prod.
# ============================================================================

# Pesos por gravidade (1.020/2025) — fonte: src/rubrics/taxonomia.py::PONTOS.
_PESO_GRAVIDADE = {"leve": 1, "media": 2, "média": 2, "grave": 4, "gravissima": 6, "gravíssima": 6}
_LIMITE_APROVACAO = 10  # ≤ 10 pontos cumulativos = aprovado


def _current_user(cookie: str | None) -> dict | None:
    """Atalho: identidade do requester via cookie de sessão (ou None)."""
    return _verify_session(cookie)


def _pontuacao_de_infracoes(infracoes: list[dict]) -> int:
    """Soma os pesos por gravidade. leve=1 média=2 grave=4 gravíssima=6."""
    total = 0
    for inf in infracoes or []:
        if not isinstance(inf, dict):
            continue
        g = str(inf.get("gravidade") or inf.get("severidade") or "").lower().strip()
        total += _PESO_GRAVIDADE.get(
            g, int(inf.get("pontos") or 0) if str(inf.get("pontos") or "").isdigit() else 0
        )
    return total


def validar_coerencia_laudo(infracoes: list[dict], resultado_final: str | None) -> dict:
    """Valida coerência laudo×veredito: soma pesos e cruza com aprovado≤10.

    Devolve {pontuacao, aprovado_calculado, resultado_informado, coerente, motivo}.
    aprovado quando pontuação ≤ 10 (LIMITE_APROVACAO da 1.020/2025).
    """
    pont = _pontuacao_de_infracoes(infracoes)
    aprovado_calc = pont <= _LIMITE_APROVACAO
    res = (resultado_final or "").lower().strip()
    informado_aprovado = res in ("aprovado", "a")
    informado_reprovado = res in ("reprovado", "r")
    coerente = True
    motivo = ""
    if informado_aprovado and not aprovado_calc:
        coerente = False
        motivo = f"veredito 'aprovado' mas pontuação {pont} > {_LIMITE_APROVACAO}"
    elif informado_reprovado and aprovado_calc:
        coerente = False
        motivo = f"veredito 'reprovado' mas pontuação {pont} ≤ {_LIMITE_APROVACAO}"
    return {
        "pontuacao": pont,
        "limite": _LIMITE_APROVACAO,
        "aprovado_calculado": aprovado_calc,
        "resultado_informado": resultado_final,
        "coerente": coerente,
        "motivo": motivo,
    }


class _ParecerAuditorIn(BaseModel):
    decisao: str = Field(..., description="concorda | discorda")
    resultado_final: str | None = Field(None, description="aprovado | reprovado")
    # `infracoes` é ACEITO mas IGNORADO (retrocompat com o front em rollout): o
    # parecer humano NÃO carrega lista de infrações. Não persistido nem repassado.
    infracoes: list[dict] | None = Field(default=None, description="DEPRECATED — ignorado")
    justificativa: str | None = None
    referencia_mbedv: str | None = None


@app.post("/api/exams/{hash}/parecer-auditor")
def post_parecer_auditor_by_hash(
    hash: str,
    data: _ParecerAuditorIn,
    valbot_session: str | None = Cookie(default=None),
):
    """Grava o parecer do Auditor resolvendo o os_id pelo HASH do exame.

    A Fila do Auditor é indexada por hash (/api/videos), mas o parecer persiste
    por os_id. Este endpoint resolve hash→os_id e delega à MESMA lógica de
    save_parecer_auditor. Resiliente: nunca 500.
      • OS encontrada → grava e devolve {persisted: true, ...}.
      • OS inexistente / DB off → best-effort, devolve 200 {persisted: false}
        (o frontend mantém o fallback localStorage e sincroniza depois).
    """
    if data.decisao not in ("concorda", "discorda"):
        raise HTTPException(422, "decisao deve ser 'concorda' ou 'discorda'")
    user = _current_user(valbot_session)
    auditor = (user or {}).get("email")
    # `data.infracoes` é IGNORADO (retrocompat): o parecer humano não carrega
    # infrações. Coerência avalia só o veredito (sem lista de infrações).
    coerencia = validar_coerencia_laudo([], data.resultado_final)

    os_id = None
    try:
        os_id = db.os_id_por_hash(hash)
    except Exception:  # pragma: no cover - resiliência dura
        os_id = None

    if not os_id:
        # Sem OS mapeada (ou DB off): não falha — best-effort.
        return {
            "exam_hash": hash,
            "os_id": None,
            "persisted": False,
            "auditor": auditor,
            "decisao": data.decisao,
            "resultado_final": data.resultado_final,
            "justificativa": data.justificativa,
            "referencia_mbedv": data.referencia_mbedv,
            "coerencia": coerencia,
            "source": "mock" if db._disabled() else "no-os",
        }

    saved = db.save_parecer_auditor(
        os_id,
        auditor=auditor,
        decisao=data.decisao,
        resultado_final=data.resultado_final,
        justificativa=data.justificativa,
        referencia_mbedv=data.referencia_mbedv,
    )
    if saved is None:
        # OS existe no índice mas o save não persistiu (DB off / falha) → best-effort.
        return {
            "exam_hash": hash,
            "os_id": os_id,
            "persisted": False,
            "auditor": auditor,
            "decisao": data.decisao,
            "resultado_final": data.resultado_final,
            "justificativa": data.justificativa,
            "referencia_mbedv": data.referencia_mbedv,
            "coerencia": coerencia,
            "source": "mock",
        }
    saved["exam_hash"] = hash
    saved["persisted"] = True
    saved["coerencia"] = coerencia
    saved["source"] = "db"
    return saved


# ============================================================================
# >>> TELAS DE GESTÃO (reconciliação) — endpoints copiados do repo api_stub.
# supervisor-metrics reescrito p/ usar db.supervisor_concordancia (metrics.py
# NÃO é montado em prod). Tudo protegido por require_session + _SPA_GESTAO_RE.
# ============================================================================

# ============================================================================
# TELAS DE GESTÃO (5) — Usuários, Relatórios, Medição, Cron/Batch, Supervisor.
# Todas protegidas por Depends(require_session). Resilientes: DB off → 200 com
# placeholder/mock, nunca 500.
# ============================================================================


# ---------------------------------------------------------------------------
# 1. USUÁRIOS — gestão de admins do painel (admin_users / migration 018).
# ---------------------------------------------------------------------------
class _CreateUserIn(BaseModel):
    email: str = Field(..., description="email do novo admin")
    password: str = Field(..., min_length=6, description="senha inicial (>=6 chars)")
    role: str = Field("admin", description="admin | auditor | supervisor")


class _UpdateUserIn(BaseModel):
    role: str | None = Field(None, description="admin | auditor | supervisor")
    revoked: bool | None = Field(None, description="true revoga, false reativa")


@app.get("/api/admin/users")
def admin_list_users(_sess: dict = Depends(require_admin)):
    """Lista os usuários do painel (sem password_hash). Admin-only (is_admin):
    antes usava require_session, o que vazava a lista de usuários/roles para
    qualquer logado (ex.: auditor). DB off → lista vazia."""
    rows = db.list_admin_users()
    if rows is None:
        return {"count": 0, "items": [], "source": "mock"}
    return {"count": len(rows), "items": rows, "source": "db"}


@app.post("/api/admin/users")
def admin_create_user(data: _CreateUserIn, _sess: dict = Depends(require_admin)):
    """Cria (ou reativa) um admin. Reusa db.create_admin_user (PBKDF2)."""
    email = (data.email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "email inválido")
    if data.role not in ("admin", "auditor", "supervisor"):
        raise HTTPException(422, "role deve ser admin | auditor | supervisor")
    try:
        user_id = db.create_admin_user(email, data.password, data.role)
    except RuntimeError as e:
        # DB off — eco mock pra não quebrar a UX em dev.
        return {"id": None, "email": email, "role": data.role, "source": "mock", "warning": str(e)}
    except Exception as e:
        raise HTTPException(500, str(e)) from e
    return {"id": user_id, "email": email, "role": data.role, "source": "db"}


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: str, data: _UpdateUserIn, _sess: dict = Depends(require_admin)):
    """Atualiza role e/ou estado de revogação de um admin."""
    if data.role is not None and data.role not in ("admin", "auditor", "supervisor"):
        raise HTTPException(422, "role deve ser admin | auditor | supervisor")
    if data.role is None and data.revoked is None:
        raise HTTPException(422, "nada para atualizar (informe role e/ou revoked)")
    res = db.update_admin_user(user_id, role=data.role, revoked=data.revoked)
    if res is None:
        if db._disabled():
            return {"id": user_id, "role": data.role, "revoked": data.revoked, "source": "mock"}
        raise HTTPException(404, f"usuário {user_id} não encontrado")
    return {**res, "source": "db"}


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: str, _sess: dict = Depends(require_admin)):
    """Revoga (soft-delete) um admin. Idempotente."""
    ok = db.delete_admin_user(user_id)
    if not ok and not db._disabled():
        raise HTTPException(404, f"usuário {user_id} não encontrado")
    return {"deleted": True, "id": user_id, "source": "mock" if db._disabled() else "db"}


@app.post("/api/admin/users/{user_id}/reset-password")
def admin_reset_password(user_id: str, _sess: dict = Depends(require_admin)):
    """Gera senha temporária. Devolve a senha em claro UMA VEZ — repassar e pedir troca."""
    temp = db.reset_admin_password(user_id)
    if temp is None:
        if db._disabled():
            import secrets

            return {
                "id": user_id,
                "senha_temporaria": secrets.token_urlsafe(9),
                "source": "mock",
                "warning": "DB off — senha não persistida.",
            }
        raise HTTPException(404, f"usuário {user_id} não encontrado")
    return {
        "id": user_id,
        "senha_temporaria": temp,
        "source": "db",
        "warning": "Senha mostrada apenas uma vez. Repasse ao usuário e peça troca.",
    }


# ---------------------------------------------------------------------------
# APP SETTINGS — config chave/valor (provisão de câmbio USD→BRL, etc.).
# GET lista (qualquer sessão); PUT só admin (reusa is_admin do _verify_session).
# `require_admin` está definida no topo (junto de require_session).
# ---------------------------------------------------------------------------


class _SettingIn(BaseModel):
    value: str = Field(..., description="novo valor da config (string)")
    description: str | None = None


@app.get("/api/admin/settings")
def admin_list_settings(_sess: dict = Depends(require_session)):
    """Lista as configs de app (key/value/description). DB off → defaults conhecidos."""
    rows = db.list_app_settings()
    if rows is None:
        return {
            "count": 1,
            "items": [
                {
                    "key": "usd_brl",
                    "value": "5.40",
                    "description": "Cotacao USD->BRL usada para provisao de custos de IA",
                    "updated_at": None,
                    "updated_by": None,
                }
            ],
            "source": "mock",
        }
    return {"count": len(rows), "items": rows, "source": "db"}


@app.put("/api/admin/settings/{key}")
def admin_put_setting(key: str, data: _SettingIn, sess: dict = Depends(require_admin)):
    """Upsert de uma config (admin only). Valida usd_brl como número > 0."""
    key = (key or "").strip().lower()
    if not key:
        raise HTTPException(422, "key obrigatória")
    val = (data.value or "").strip()
    if key == "usd_brl":
        try:
            fv = float(val)
            if fv <= 0:
                raise ValueError
            val = f"{fv:.4f}".rstrip("0").rstrip(".")
        except (TypeError, ValueError):
            raise HTTPException(422, "usd_brl deve ser número > 0 (ex: 5.40)")
    res = db.set_app_setting(key, val, updated_by=sess.get("email"), description=data.description)
    if res is None:
        if db._disabled():
            return {"key": key, "value": val, "source": "mock"}
        raise HTTPException(500, "falha ao gravar a config")
    return {**res, "source": "db"}


# ---------------------------------------------------------------------------
# 2. RELATÓRIOS — lista filtrada, laudo JSON/PDF, consolidado, export CSV.
# ---------------------------------------------------------------------------
@app.get("/api/relatorios/resultados")
def relatorios_resultados(
    dias: int | None = None,
    unidade: str | None = None,
    examinador: str | None = None,
    resultado: str | None = None,
    categoria: str | None = None,
    page: int = 1,
    page_size: int = 50,
    limit: int | None = None,
    _sess: dict = Depends(require_session),
):
    """Lista de exames (v_exams_overview) filtrada e PAGINADA. DB off → vazia (200)."""
    if limit is not None:
        page_size = int(limit)
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 500))
    offset = (page - 1) * page_size
    total = db.count_resultados(
        dias=dias,
        unidade=unidade,
        examinador=examinador,
        resultado=resultado,
        categoria=categoria,
    )
    rows = db.list_resultados(
        dias=dias,
        unidade=unidade,
        examinador=examinador,
        resultado=resultado,
        categoria=categoria,
        limit=page_size,
        offset=offset,
    )
    if rows is None:
        return {
            "count": 0,
            "total": 0,
            "page": page,
            "page_size": page_size,
            "pages": 0,
            "items": [],
            "filtros": {
                "dias": dias,
                "unidade": unidade,
                "examinador": examinador,
                "resultado": resultado,
                "categoria": categoria,
            },
            "source": "mock",
        }
    items = []
    for r in rows:
        ap = r.get("aprovado")
        of = (r.get("resultado_exame") or "").strip().upper()
        # Veredito ValBot (calculado) derivado de `aprovado` (bool da IA).
        rc = "A" if ap is True else ("R" if ap is False else None)
        diverge = (of == "A" and ap is False) or (of == "R" and ap is True)
        items.append(
            {
                "hash": r.get("hash"),
                "candidato_nome": r.get("candidato_nome"),
                "candidato": _mask_cpf(r.get("candidato_cpf")),
                "renach": r.get("renach"),
                "unidade": r.get("local_unidade"),
                "examinador": r.get("examinador"),
                "categoria": r.get("categoria"),
                "status": r.get("status"),
                "resultado": r.get("resultado"),
                "resultado_exame": r.get("resultado_exame"),
                "resultado_calculado": rc,
                "aprovado": r.get("aprovado"),
                "pontuacao_total": r.get("pontuacao_total"),
                "pontuacao_calculada": r.get("pontuacao_total"),
                "pontuacao_oficial": None,
                "tipo_divergencia": "resultado" if diverge else None,
                # Estado do fluxo DERIVADO (informativo). Sem migration: a view
                # v_exams_overview já expõe resultado_exame/aprovado/gate_rejected/
                # layout_confianca. NÃO altera status/pipeline.
                "estado_fluxo": _estado_fluxo(
                    resultado_oficial=r.get("resultado_exame"),
                    resultado_calculado=rc,
                    gate_rejected=r.get("gate_rejected"),
                    layout_confianca=r.get("layout_confianca"),
                ),
                "data_hora_exame": r.get("created_at"),
                "num_infracoes": r.get("num_infracoes"),
                "cost_usd": r.get("cost_usd"),
                "duration_s": r.get("duration_s"),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
                "laudo_enviado_em": r.get("laudo_enviado_em"),
                "laudo_envio_status": r.get("laudo_envio_status"),
            }
        )
    total = total if total is not None else len(items)
    pages = (total + page_size - 1) // page_size if page_size else 1
    return {
        "count": len(items),
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "items": items,
        "filtros": {
            "dias": dias,
            "unidade": unidade,
            "examinador": examinador,
            "resultado": resultado,
            "categoria": categoria,
        },
        "source": "db",
    }


def _res_label(v) -> str | None:
    """Normaliza qualquer representação de veredito → 'APROVADO'|'REPROVADO'|None.

    Aceita: 'A'/'R', bool (True=aprovado), 'aprovado'/'reprovado', 'aprov'/'repr',
    'homologar' (segue resultado, não decide por si → None), variações com acento/
    caixa. Entrada nula/desconhecida → None.
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return "APROVADO" if v else "REPROVADO"
    s = str(v).strip().lower()
    if not s:
        return None
    if s in ("a", "aprovado", "aprov", "aprovada", "approved", "homologado"):
        return "APROVADO"
    if s in ("r", "reprovado", "repr", "reprovada", "reproved", "rejected", "reprov"):
        return "REPROVADO"
    if s.startswith("aprov"):
        return "APROVADO"
    if s.startswith("reprov") or s.startswith("repr"):
        return "REPROVADO"
    return None


def _estado_fluxo(
    *,
    resultado_oficial,
    resultado_calculado,
    gate_rejected=None,
    layout_confianca=None,
) -> str:
    """Deriva (NÃO altera) o estado do fluxo do exame a partir de dados que JÁ
    existem no dossiê. Campo puramente informativo: não muda status real da OS,
    não encerra, não marca inapto — apenas SINALIZA em que ponto o caso está.

    Precedência (do mais restritivo ao mais brando):
      1. "inapto_avaliacao"  — visibilidade/qualidade ruim (gate_rejected OU
         layout_confianca < 0.4). Distinto de "fora_escopo" (categoria não
         suportada), que NÃO é derivado aqui.
      2. "aguardando_oficial" — resultado oficial do examinador ainda 'N'/ausente
         (mesma regra de `resultado_exame` ∈ {A,R}; qualquer outra coisa = pendente).
      3. "consenso"    — oficial E calculado presentes e CONCORDAM (mesmo veredito
         A/R). Só SINALIZA que poderia finalizar direto; NÃO encerra.
      4. "divergencia" — oficial E calculado presentes e DIVERGEM.
      5. ""            — nenhum dos casos acima.
    """
    # 1. Inapto por qualidade/visibilidade (gate ou confiança de layout baixa).
    conf = None
    if layout_confianca is not None:
        try:
            conf = float(layout_confianca)
        except (TypeError, ValueError):
            conf = None
    if bool(gate_rejected) or (conf is not None and conf < 0.4):
        return "inapto_avaliacao"

    # 2. Oficial pendente — usa a MESMA regra de oficialReal/resultado_exame:
    #    só conta como oficial efetivo se normaliza para APROVADO/REPROVADO.
    oficial = _res_label(resultado_oficial)
    if oficial is None:
        return "aguardando_oficial"

    # 3/4. Consenso vs divergência — exige oficial E calculado normalizáveis.
    calculado = _res_label(resultado_calculado)
    if calculado is None:
        return ""
    return "consenso" if oficial == calculado else "divergencia"


def _laudo_blocos_14_2(hash_: str) -> dict:
    """Monta os 14 blocos do §14.2 a partir do dossiê do DB (exam + comitê +
    parecer + decisão + eventos). DB off → placeholder com os 14 blocos vazios.

    Os 14 blocos: 1 identificação, 2 candidato, 3 examinador, 4 resultado
    oficial, 5 resultado calculado, 6 cobertura, 7 análise detalhada (infrações),
    8 divergência, 9 comitê de IA, 10 parecer auditor, 11 decisão supervisor,
    12 eventos/trilha OS, 13 envio à unidade gestora, 14 integridade.
    """
    d = db.laudo_dossie(hash_)
    if d is None:
        # placeholder resiliente — os 14 blocos presentes, vazios. Mesmo sem DB,
        # tenta os comentários do examinador do upload.json local.
        return {
            "exame_hash": hash_,
            "laudo_versao": "laudo/2.0",
            "fonte": "placeholder",
            # Sem dossiê não há veredito oficial → fluxo aguardando o oficial.
            "estado_fluxo": "aguardando_oficial",
            "blocos": {
                "1_identificacao": {},
                "2_candidato": {},
                "3_examinador": {},
                "4_resultado_oficial": {},
                "5_resultado_calculado": {},
                "6_cobertura": {},
                "7_analise_detalhada": [],
                "7b_comentarios_examinador": _read_training_annotations(hash_),
                "7c_enquadramentos": [],
                "7d_eventos_sem_enquadramento": [],
                "7e_compliance": [],
                "8_divergencia": {},
                "9_comite_ia": {},
                "10_parecer_auditor": {},
                "11_decisao_supervisor": {},
                "12_eventos_os": [],
                "12b_linha_tempo": [],
                "13_envio_unidade_gestora": {},
                "14_integridade": {},
            },
        }
    e = d.get("exam") or {}
    os_ = d.get("ordem_servico") or {}
    comite = d.get("laudo_comite") or {}
    comite_meta = d.get("comite_meta") or {}
    parecer = d.get("parecer_auditor") or {}
    decisao = d.get("decisao_supervisor") or {}
    # Converte as infrações cruas (exam_infractions: timestamp_s numérico, regra_id,
    # cameras[]) pro shape que o frontend espera (timestamp_inicio "mm:ss", id,
    # gravidade_label, cameras_fmt, confianca textual). Sem isso o timestamp (que o
    # Gemini SEMPRE aponta e está salvo) e os demais campos apareciam "—".
    _dur_infr = float((d.get("exam") or {}).get("duration_s") or 0)
    infracoes = [
        _infracao_from_db(i, item, _dur_infr) for i, item in enumerate(d.get("infracoes") or [])
    ]
    eventos = d.get("os_eventos") or []
    divergencia = d.get("divergencia") or {}
    eventos_brutos = d.get("eventos") or []
    enquadramentos = d.get("enquadramentos") or []
    infracoes_oficiais = d.get("infracoes_oficiais") or []
    compliance = d.get("compliance") or []
    matriz_vigente = d.get("matriz_vigente") or {}
    # Comentários do examinador TechPrático (upload.json → training_annotations).
    _train_ann_pdf = _read_training_annotations(hash_)

    # --- Fallbacks do BUG confirmado (ordem_servico VAZIA em prod) -------------
    # resultado_oficial    ⇐ e.resultado_exame      (A/R/N do examinador presencial)
    # resultado_calculado  ⇐ exam.resultado_calculado → derivar de e.aprovado
    # pontuacao_oficial    ⇐ exam.pontuacao_oficial
    # pontuacao_calculada  ⇐ exam.pontuacao_calculada → e.pontuacao_total
    _aprov = e.get("aprovado")
    _resultado_calc_derivado = None
    if _aprov is True:
        _resultado_calc_derivado = "A"
    elif _aprov is False:
        _resultado_calc_derivado = "R"
    resultado_oficial = (
        os_.get("resultado_oficial")
        or divergencia.get("resultado_oficial")
        or e.get("resultado_exame")
    )
    resultado_calculado = (
        os_.get("resultado_calculado")
        or divergencia.get("resultado_calculado")
        or e.get("resultado_calculado")
        or _resultado_calc_derivado
    )
    pontuacao_oficial = (
        os_.get("pontuacao_oficial")
        if os_.get("pontuacao_oficial") is not None
        else (
            divergencia.get("pontuacao_oficial")
            if divergencia.get("pontuacao_oficial") is not None
            else e.get("pontuacao_oficial")
        )
    )
    pontuacao_calculada = (
        os_.get("pontuacao_calculada")
        if os_.get("pontuacao_calculada") is not None
        else (
            divergencia.get("pontuacao_calculada")
            if divergencia.get("pontuacao_calculada") is not None
            else (
                e.get("pontuacao_calculada")
                if e.get("pontuacao_calculada") is not None
                else e.get("pontuacao_total")
            )
        )
    )

    # --- Vereditos A/R normalizados (EXIBIÇÃO; não substituem campos existentes) -
    # Bloco 9: o Comitê não emite veredito próprio — deriva-se da conclusão.
    #   concorda_com_examinador          → segue o resultado oficial (bloco 4).
    #   manter_divergencia_com_fundamentacao → o oposto (o que a IA sustenta, b.5).
    _concl_comite = str(comite.get("conclusao_comite") or "").strip().lower()
    if _concl_comite.startswith("concorda"):
        _veredito_comite = _res_label(resultado_oficial)
    elif _concl_comite.startswith("manter_diverg") or "diverg" in _concl_comite:
        _veredito_comite = _res_label(resultado_calculado)
    else:
        _veredito_comite = None

    # Bloco 10: veredito do auditor = resultado_final (já 'aprovado'/'reprovado').
    _veredito_auditor = _res_label(parecer.get("resultado_final"))

    # Bloco 11: veredito do supervisor. 'homologar' segue o parecer do auditor;
    # 'reformar' sobrepõe (o oposto do parecer). resultado_final explícito tem
    # precedência quando presente.
    _dec_sup = str(decisao.get("decisao") or "").strip().lower()
    _sup_final_explicit = _res_label(decisao.get("resultado_final"))
    if _sup_final_explicit is not None:
        _veredito_supervisor = _sup_final_explicit
    elif _dec_sup.startswith("homolog"):
        _veredito_supervisor = _veredito_auditor
    elif _dec_sup.startswith("reform"):
        _veredito_supervisor = (
            "REPROVADO"
            if _veredito_auditor == "APROVADO"
            else ("APROVADO" if _veredito_auditor == "REPROVADO" else None)
        )
    else:
        _veredito_supervisor = None

    blocos = {
        # 1 — IDENTIFICAÇÃO DO LAUDO
        "1_identificacao": {
            "hash": e.get("hash"),
            "external_id": e.get("external_id"),
            "unidade": e.get("local_unidade"),
            "categoria": e.get("categoria"),
            "veiculo": e.get("veiculo"),
            "auto_escola": e.get("auto_escola"),
            "rubrica": "1020/2025",
            "criado_em": e.get("created_at"),
            # Identificação do laudo (modelo §1)
            "resolucao": "CONTRAN 1.020/2025",
            "manual_mbedv": e.get("rubrica"),
            "matriz_nacional": (matriz_vigente.get("versao") or e.get("matriz_versao")),
            "matriz_descricao": matriz_vigente.get("descricao"),
            "modelo_ia_principal": e.get("engine_model"),
            "engine_backend": e.get("engine_backend"),
            "engine_preset": e.get("engine_preset"),
            "modelo_comite": comite_meta.get("comite_versao"),
            "tempo_processamento_s": e.get("gemini_elapsed_s"),
            "data_emissao": e.get("created_at"),
            "data_hora_exame": e.get("data_hora_exame"),
        },
        # 2 — SUMÁRIO EXECUTIVO + 3 (candidato)
        "2_candidato": {
            "nome": e.get("candidato_nome"),
            "cpf_mascarado": _mask_cpf(e.get("candidato_cpf")),
            "renach": e.get("renach"),
            "processo": e.get("processo"),
            "categoria": e.get("categoria"),
            "tipo_exame": e.get("tipo_exame"),
        },
        # 3 — EXAMINADOR
        "3_examinador": {
            "nome": e.get("examinador"),
            "matricula": e.get("examinador_matricula"),
            "eh_preposto": e.get("examinador_eh_preposto"),
            "comentarios_count": len(_train_ann_pdf),
        },
        # 4 — RESULTADO OFICIAL (com fallbacks)
        "4_resultado_oficial": {
            "resultado_exame": e.get("resultado_exame"),
            "resultado_oficial": resultado_oficial,
            "pontuacao_oficial": pontuacao_oficial,
            "houve_interrupcao": e.get("houve_interrupcao"),
            "motivo_interrupcao": e.get("motivo_interrupcao"),
            # GAP: nenhuma coluna registra quem lançou o resultado oficial.
            "registrado_por": None,
            "data_hora_exame": e.get("data_hora_exame"),
            "anotacoes_tpa": _train_ann_pdf,
            "infracoes_oficiais": infracoes_oficiais,
        },
        # 5 — RESULTADO CALCULADO (com fallbacks)
        "5_resultado_calculado": {
            "aprovado": e.get("aprovado"),
            "resultado_calculado": resultado_calculado,
            "pontuacao_total": e.get("pontuacao_total"),
            "pontuacao_calculada": pontuacao_calculada,
            "limite_normativo": _LIMITE_APROVACAO,
            "num_infracoes": e.get("num_infracoes"),
            "infracoes_ia": len(infracoes),
            "eventos_sem_enquadramento": sum(
                1 for q in enquadramentos if q.get("enquadrado") is False
            ),
            "matriz_versao": e.get("matriz_versao"),
            "gate_rejected": e.get("gate_rejected"),
            "gate_motivo": e.get("gate_motivo"),
        },
        # 6 — COBERTURA / camadas técnicas
        "6_cobertura": {
            "duration_s": e.get("duration_s"),
            "layout_confianca": e.get("layout_confianca"),
            "fabricante_provavel": e.get("fabricante_provavel"),
            "validator_veredito": e.get("validator_veredito"),
            "total_infracoes": len(infracoes),
            "total_eventos_brutos": len(eventos_brutos),
            "total_enquadramentos": len(enquadramentos),
        },
        # 7 — DETALHAMENTO DAS INFRAÇÕES
        "7_analise_detalhada": infracoes,
        "7b_comentarios_examinador": _train_ann_pdf,
        "7c_enquadramentos": enquadramentos,
        "7d_eventos_sem_enquadramento": [q for q in enquadramentos if q.get("enquadrado") is False],
        "7e_compliance": compliance,
        # 8 — ANÁLISE DE DIVERGÊNCIA (motor de comparação) + OS
        "8_divergencia": {
            # OS (quando existe)
            "tipo_divergencia": (
                divergencia.get("tipo_divergencia") or os_.get("tipo_divergencia")
            ),
            "status_os": os_.get("status"),
            "numero_os": os_.get("numero_os"),
            # Motor de comparação (exam_divergencias)
            "subtipos_associados": divergencia.get("subtipos_associados"),
            "concorda_resultado": divergencia.get("concorda_resultado"),
            "concorda_pontuacao": divergencia.get("concorda_pontuacao"),
            "concorda_infracoes": divergencia.get("concorda_infracoes"),
            "evidencia_suficiente": divergencia.get("evidencia_suficiente"),
            "encaminhamento": divergencia.get("encaminhamento"),
            "detalhes": divergencia.get("detalhes"),
        },
        # 9 — COMITÊ DE IA. veredito_comite ACRESCENTADO (derivado, EXIBIÇÃO);
        # conclusao_comite e demais campos preservados intactos.
        "9_comite_ia": {**comite, **comite_meta, "veredito_comite": _veredito_comite},
        # 10 — PARECER AUDITOR. veredito_auditor ACRESCENTADO; decisao/
        # resultado_final preservados.
        "10_parecer_auditor": {**parecer, "veredito_auditor": _veredito_auditor},
        # 11 — DECISÃO SUPERVISOR. veredito_supervisor ACRESCENTADO; decisao
        # preservada.
        "11_decisao_supervisor": {**decisao, "veredito_supervisor": _veredito_supervisor},
        # 12 — LINHA DO TEMPO: trilha da OS + cronologia de eventos brutos.
        # Cada evento bruto é ENRIQUECIDO (tempo fmt, duração, % confiança,
        # ângulo de câmera) preservando o registro cru via spread.
        "12_eventos_os": eventos,
        "12b_linha_tempo": [_enriquecer_evento(ev, _dur_infr) for ev in eventos_brutos],
        "13_envio_unidade_gestora": {
            "laudo_enviado_em": e.get("laudo_enviado_em"),
            "laudo_envio_status": e.get("laudo_envio_status"),
            "laudo_envio_resultado": e.get("laudo_envio_resultado"),
            "laudo_envio_tentativas": e.get("laudo_envio_tentativas"),
        },
        "14_integridade": {
            "video_hash": e.get("hash"),
            "gs_video": e.get("gs_video"),
            "gs_result_json": e.get("gs_result_json"),
            "gs_laudo_pdf": e.get("gs_laudo_pdf"),
        },
    }
    # Checklist técnico Anexo K (12 itens) — informativo, emitido pelo Gemini no
    # result_json (sem coluna dedicada no DB). Surfaciado em 6_cobertura. Best-
    # effort: qualquer falha mantém o bloco sem o checklist (frontend mostra "—").
    try:
        _res = _load_result_raw(hash_, e.get("gs_result_json"))
        _chk = (_res or {}).get("checklist_anexo_k")
        if isinstance(_chk, list) and _chk:
            blocos["6_cobertura"]["checklist_anexo_k"] = _chk
    except Exception:  # noqa: BLE001
        pass
    # Estado do fluxo DERIVADO (informativo) — não altera pipeline/status/OS.
    # Reusa o veredito oficial/calculado já resolvido acima (com os mesmos
    # fallbacks) + sinais de qualidade do bloco 6 (gate_rejected/layout_confianca).
    estado_fluxo = _estado_fluxo(
        resultado_oficial=resultado_oficial,
        resultado_calculado=resultado_calculado,
        gate_rejected=e.get("gate_rejected"),
        layout_confianca=e.get("layout_confianca"),
    )
    laudo = {
        "exame_hash": hash_,
        "laudo_versao": "laudo/2.0",
        "emitido_em": datetime.utcnow().isoformat() + "Z",
        "fonte": "db",
        "estado_fluxo": estado_fluxo,
        "blocos": blocos,
    }
    # Integridade — hash do conteúdo (reusa o helper do backend.reporting.laudo).
    try:
        from backend.reporting import laudo as _laudo_mod

        laudo["blocos"]["14_integridade"]["hash_relatorio"] = _laudo_mod.hash_relatorio(laudo)
    except Exception:
        pass
    return laudo


@app.get("/api/exams/{hash}/laudo-json")
def get_laudo_json(hash: str, _sess: dict = Depends(require_session)):
    """Laudo explicável em JSON com os 14 blocos do §14.2. DB off → placeholder (200)."""
    return _laudo_blocos_14_2(hash)


def _init_upload_inicial(hash_: str) -> dict:
    """Reconstrói o **payload inicial** do `POST /api/exams/init-upload` a partir
    do `upload.json` gravado na recepção.

    O body cru enviado pelo integrador (TechPrático) **não é persistido** — o
    backend monta direto o `upload.json` enriquecido e descarta o original. Mas o
    `upload.json` é um snapshot fiel que carrega todos os campos do POST,
    reorganizados em `candidato`/`exame`/`video`. Aqui projetamos de volta para o
    shape `InitUploadRequest` (o "JSON inicial"). Levanta 404 se não houver
    `upload.json` (nem no diretório atual nem no storage legado).
    """
    upload_path = ANALYSES_DIR / hash_ / "upload.json"
    if not upload_path.exists():
        legacy = STORAGE / hash_ / "upload.json"
        if not legacy.exists():
            raise HTTPException(404, f"upload.json não encontrado para {hash_[:12]}")
        upload_path = legacy
    try:
        meta = json.loads(upload_path.read_text())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"upload.json ilegível: {e}") from e

    c = meta.get("candidato", {}) or {}
    ex = meta.get("exame", {}) or {}
    v = meta.get("video", {}) or {}
    # source_url é o `url` original; runs antigos (via sweep S3) guardam em gs_path_original_s3.
    url = v.get("source_url") or v.get("gs_path_original_s3") or ""
    return {
        "url": url,
        "renach": c.get("renach", ""),
        "candidato_nome": c.get("nome", ""),
        "candidato_cpf": c.get("cpf", ""),
        "processo": c.get("processo", ""),
        "categoria": c.get("categoria", ""),
        "veiculo": ex.get("veiculo", ""),
        "local": ex.get("local", ""),
        "examinador": ex.get("examinador", ""),
        "auto_escola": ex.get("auto_escola", ""),
        "rubrica": ex.get("rubrica", "1020/2025"),
        "training_annotations": meta.get("training_annotations", []),
        "resultado_exame": meta.get("resultado_exame"),
    }


@app.get("/api/exams/{hash}/init-upload")
def get_init_upload(hash: str, _sess: dict = Depends(require_session)):
    """Payload inicial do `init_upload` (o JSON que o integrador enviou no POST),
    reconstruído a partir do `upload.json`. Consumido pela tela Relatórios no
    grupo `init_upload`. 404 quando o exame não tem `upload.json`."""
    return _init_upload_inicial(hash)


def _laudo_pdf_html(laudo: dict) -> str:
    """HTML de um LAUDO OFICIAL ValBot (auto-contido, sem template externo).

    Estrutura de documento oficial: cabeçalho institucional, identificação do
    candidato/processo, comparativo Resultado Oficial (TechPrático) × Veredito
    ValBot (IA), tabela de infrações detectadas pela IA, comentários do
    examinador (training_annotations), parecer/decisão (quando houver), e rodapé
    com versão da matriz e hash de integridade. Aceita um laudo ou lista (consolidado).
    """
    import html as _html

    def esc(v):
        return _html.escape("" if v is None else str(v))

    def g(b, chave, k, default="—"):
        v = (b.get(chave) or {}).get(k)
        return v if v not in (None, "") else default

    def _res_label(r):
        s = str(r or "").strip().upper()
        return {
            "A": "APROVADO",
            "R": "REPROVADO",
            "APROVADO": "APROVADO",
            "REPROVADO": "REPROVADO",
        }.get(s, r or "—")

    def render_doc(laudo: dict) -> str:
        b = laudo.get("blocos") or {}
        ident, cand, exmn = (
            b.get("1_identificacao") or {},
            b.get("2_candidato") or {},
            b.get("3_examinador") or {},
        )
        r_of, r_calc = b.get("4_resultado_oficial") or {}, b.get("5_resultado_calculado") or {}
        cobertura = b.get("6_cobertura") or {}
        infracoes = b.get("7_analise_detalhada") or []
        comentarios = b.get("7b_comentarios_examinador") or []
        diverg = b.get("8_divergencia") or {}
        parecer = b.get("10_parecer_auditor") or {}
        decisao = b.get("11_decisao_supervisor") or {}
        integ = b.get("14_integridade") or {}

        resultado_oficial = _res_label(r_of.get("resultado_oficial") or r_of.get("resultado_exame"))
        aprovado = r_calc.get("aprovado")
        veredito_valbot = (
            "APROVADO" if aprovado is True else ("REPROVADO" if aprovado is False else "—")
        )
        pont = r_calc.get("pontuacao_total")
        concorda = resultado_oficial == veredito_valbot and veredito_valbot != "—"
        conc_label = (
            "CONCORDÂNCIA" if concorda else ("DIVERGÊNCIA" if veredito_valbot != "—" else "—")
        )
        conc_cls = "ok" if concorda else ("div" if veredito_valbot != "—" else "")

        # Cabeçalho institucional
        parts = [
            "<div class='doc'>",
            "<div class='hdr'>",
            "<div class='brand'>ValBot</div>",
            "<div class='subt'>LAUDO OFICIAL DE AVALIAÇÃO — EXAME PRÁTICO DE DIREÇÃO VEICULAR</div>",
            f"<div class='ref'>Res. CONTRAN 1.020/2025 · Matriz MBEDV · {esc(laudo.get('laudo_versao'))} · "
            f"emitido em {esc(laudo.get('emitido_em'))}</div>",
            "</div>",
        ]
        # Identificação
        parts.append("<h2>1. Identificação do Exame e do Candidato</h2>")
        parts.append(
            "<table class='kv'>"
            f"<tr><th>Candidato</th><td>{esc(cand.get('nome') or '—')}</td>"
            f"<th>RENACH</th><td>{esc(cand.get('renach') or '—')}</td></tr>"
            f"<tr><th>CPF</th><td>{esc(cand.get('cpf_mascarado') or '—')}</td>"
            f"<th>Processo / ID</th><td>{esc(ident.get('external_id') or '—')}</td></tr>"
            f"<tr><th>Categoria</th><td>{esc(ident.get('categoria') or '—')}</td>"
            f"<th>Veículo</th><td>{esc(ident.get('veiculo') or '—')}</td></tr>"
            f"<tr><th>Unidade</th><td>{esc(ident.get('unidade') or '—')}</td>"
            f"<th>Auto-escola</th><td>{esc(ident.get('auto_escola') or '—')}</td></tr>"
            f"<tr><th>Examinador</th><td>{esc(exmn.get('nome') or '—')}</td>"
            f"<th>Data do exame</th><td>{esc(ident.get('criado_em') or '—')}</td></tr>"
            f"<tr><th>Duração do vídeo</th><td>{esc(cobertura.get('duration_s') or '—')} s</td>"
            f"<th>Hash do exame</th><td class='mono'>{esc(laudo.get('exame_hash'))}</td></tr>"
            "</table>"
        )
        # Comparativo de resultado
        parts.append("<h2>2. Resultado Oficial × Veredito ValBot</h2>")
        parts.append(
            "<table class='cmp'>"
            "<tr><th>Resultado Oficial (Examinador / TechPrático)</th>"
            "<th>Veredito ValBot (IA)</th><th>Concordância</th></tr>"
            f"<tr><td class='big'>{esc(resultado_oficial)}</td>"
            f"<td class='big'>{esc(veredito_valbot)}</td>"
            f"<td class='big {conc_cls}'>{esc(conc_label)}</td></tr>"
            "</table>"
            f"<p class='note'>Pontuação calculada pela IA: <b>{esc(pont if pont is not None else '—')}</b> "
            f"· nº de infrações detectadas: <b>{len(infracoes)}</b> "
            f"· limite de aprovação: ≤ 10 pontos cumulativos.</p>"
        )
        # Infrações IA
        parts.append("<h2>3. Infrações Detectadas pela IA</h2>")
        if not infracoes:
            parts.append("<p class='vazio'>Nenhuma infração detectada pela IA.</p>")
        else:
            linhas = [
                "<table class='inf'><tr><th>#</th><th>Tempo</th><th>Regra</th>"
                "<th>Gravidade</th><th>Pts</th><th>Descrição</th><th>Base legal</th></tr>"
            ]
            for i, inf in enumerate(infracoes, 1):
                if not isinstance(inf, dict):
                    continue
                ts = inf.get("timestamp_s")
                ts_fmt = (
                    f"{int(float(ts)) // 60:02d}:{int(float(ts)) % 60:02d}"
                    if ts not in (None, "")
                    else "—"
                )
                linhas.append(
                    f"<tr><td>{i}</td><td>{esc(ts_fmt)}</td>"
                    f"<td class='mono'>{esc(inf.get('regra_id') or '—')}</td>"
                    f"<td>{esc(inf.get('gravidade') or '—')}</td>"
                    f"<td>{esc(inf.get('pontos') if inf.get('pontos') is not None else '—')}</td>"
                    f"<td>{esc(inf.get('descricao') or '—')}</td>"
                    f"<td>{esc(inf.get('base_legal') or '—')}</td></tr>"
                )
            linhas.append("</table>")
            parts.append("".join(linhas))
        # Comentários do examinador (training_annotations)
        parts.append("<h2>4. Comentários do Examinador (TechPrático)</h2>")
        if not comentarios:
            parts.append(
                "<p class='vazio'>Sem comentários do examinador registrados para este exame.</p>"
            )
        else:
            linhas = ["<table class='inf'><tr><th>#</th><th>Tempo</th><th>Anotação</th></tr>"]
            for i, com in enumerate(comentarios, 1):
                if isinstance(com, dict):
                    linhas.append(
                        f"<tr><td>{i}</td><td>{esc(com.get('timestamp') or '—')}</td>"
                        f"<td>{esc(com.get('anotacoes') or com.get('anotacao') or '')}</td></tr>"
                    )
                else:
                    linhas.append(f"<tr><td>{i}</td><td>—</td><td>{esc(com)}</td></tr>")
            linhas.append("</table>")
            parts.append("".join(linhas))
        # Parecer / decisão (quando houver)
        if parecer or decisao:
            parts.append("<h2>5. Reconciliação (Auditoria Humana)</h2>")
            parts.append(
                "<table class='kv'>"
                f"<tr><th>Parecer do Auditor</th><td>{esc((parecer or {}).get('decisao') or '—')}</td>"
                f"<th>Resultado final</th><td>{esc((parecer or {}).get('resultado_final') or '—')}</td></tr>"
                f"<tr><th>Decisão do Supervisor</th><td>{esc((decisao or {}).get('decisao') or '—')}</td>"
                f"<th>Tipo de divergência</th><td>{esc(diverg.get('tipo_divergencia') or '—')}</td></tr>"
                "</table>"
            )
        # Rodapé / integridade
        parts.append("<h2>6. Integridade e Rastreabilidade</h2>")
        parts.append(
            "<table class='kv'>"
            f"<tr><th>Matriz / Rubrica</th><td>{esc(ident.get('rubrica') or '1020/2025')}</td>"
            f"<th>Versão do laudo</th><td>{esc(laudo.get('laudo_versao'))}</td></tr>"
            f"<tr><th>Hash do relatório</th><td class='mono'>{esc(integ.get('hash_relatorio') or '—')}</td>"
            f"<th>Fonte</th><td>{esc(laudo.get('fonte'))}</td></tr>"
            "</table>"
        )
        parts.append(
            "<p class='foot'>Documento gerado automaticamente pelo sistema ValBot. "
            "Veredito da IA tem caráter de apoio à decisão; a homologação final compete "
            "à autoridade examinadora competente.</p>"
        )
        parts.append("</div>")
        return "\n".join(parts)

    laudos = laudo if isinstance(laudo, list) else [laudo]
    corpo = "<hr class='page'/>".join(render_doc(l) for l in laudos)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    @page {{ size: A4; margin: 18mm 16mm; }}
    body{{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10.5px;color:#1a1a1a;}}
    .doc{{max-width:100%;}}
    .hdr{{border-bottom:3px solid #0b7a44;padding-bottom:8px;margin-bottom:14px;}}
    .brand{{font-size:26px;font-weight:800;color:#0b7a44;letter-spacing:-.5px;}}
    .subt{{font-size:13px;font-weight:700;margin-top:2px;color:#222;}}
    .ref{{font-size:9px;color:#666;margin-top:3px;}}
    h2{{font-size:12px;margin:16px 0 6px;color:#0b7a44;border-bottom:1px solid #e2e8e5;padding-bottom:2px;}}
    table{{border-collapse:collapse;width:100%;margin:4px 0;}}
    th,td{{border:1px solid #d9e0dc;padding:4px 7px;text-align:left;vertical-align:top;}}
    table.kv th{{background:#f1f6f3;width:16%;font-weight:600;color:#33403a;}}
    table.cmp th{{background:#0b7a44;color:#fff;text-align:center;font-size:10px;}}
    table.cmp td{{text-align:center;}}
    td.big{{font-size:15px;font-weight:800;padding:10px;}}
    td.big.ok{{color:#0b7a44;}} td.big.div{{color:#b42318;}}
    table.inf th{{background:#f1f6f3;font-size:9.5px;}}
    .mono{{font-family:'Courier New',monospace;font-size:9px;}}
    .note{{font-size:10px;color:#444;margin:6px 0;}} .vazio{{color:#999;font-style:italic;}}
    .foot{{margin-top:14px;font-size:8.5px;color:#888;border-top:1px solid #eee;padding-top:6px;}}
    hr.page{{page-break-after:always;border:none;}}
    </style></head><body>{corpo}</body></html>"""


def _render_pdf_bytes(html: str) -> bytes | None:
    """Renderiza HTML→PDF via WeasyPrint se disponível; senão None."""
    try:
        from weasyprint import HTML  # type: ignore

        return HTML(string=html).write_pdf()
    except Exception as e:
        log.warning("weasyprint indisponível p/ laudo PDF: %s", e)
        return None


# ===========================================================================
# LAUDO PDF v2 — documento oficial reescrito do ZERO (2026-06).
#
# Motivo da reescrita: a geração antiga (`_laudo_blocos_14_2` + `_laudo_pdf_html`)
# puxava de `db.laudo_dossie`, que lê de tabelas com schema-drift / vazias
# (`ordens_servico.exam_hash`, `exam_comite_laudos.comentarios_examinador_detectados`
# inexistentes) → blocos vinham vazios → PDF "uma folha com um status".
#
# v2 NÃO reaproveita nada disso. Lê APENAS fontes com conteúdo comprovado:
#   1. result.json (Gemini): infrações + veredito IA — leitura RAW, mesma
#      ordem de resolução do analyses_result (local → gs_result_json → db).
#   2. upload.json: metadados (candidato/exame/resultado_exame) + comentários
#      do examinador TechPrático via _read_training_annotations(hash).
#   3. Matriz MBEDV / Res. CONTRAN 1.020/2025 (rótulos/rodapé).
# Resiliente: nenhuma seção derruba o PDF; ausências viram "—" / seção omitida.
# ===========================================================================
_MATRIZ_VERSAO_V2 = "matriz-nacional-v1.0"
_RESOLUCAO_V2 = "Resolução CONTRAN nº 1.020/2025 — Matriz MBEDV"


def _esc_v2(v) -> str:
    """HTML-escape resiliente. None/'' → '—'."""
    import html as _html

    if v is None:
        return "—"
    s = str(v).strip()
    if not s:
        return "—"
    return _html.escape(s)


def _mmss_v2(seconds) -> str:
    """Segundos (int/float) → 'mm:ss'. Inválido → '—'."""
    try:
        s = int(float(seconds))
        if s < 0:
            return "—"
        return f"{s // 60:02d}:{s % 60:02d}"
    except (TypeError, ValueError):
        return "—"


def _grav_class_v2(sev: str) -> str:
    """Normaliza severidade textual → classe CSS de cor (eliminatória/grave/etc)."""
    import unicodedata

    if not sev:
        return "media"
    n = "".join(
        c for c in unicodedata.normalize("NFD", str(sev).lower()) if unicodedata.category(c) != "Mn"
    ).strip()
    if "elimina" in n:
        return "eliminatoria"
    if "gravissima" in n or "gravissimo" in n:
        return "gravissima"
    if "grave" in n:
        return "grave"
    if "media" in n or "medio" in n:
        return "media"
    if "leve" in n:
        return "leve"
    if "etic" in n:
        return "etica"
    return "media"


def _read_result_json_raw_v2(hash: str) -> dict:
    """Lê o result.json BRUTO (sem normalizar) — infrações Gemini com toda a
    riqueza (evidence/descricao/severidade/base_legal). Mesma ordem de
    resolução de fonte do analyses_result: local → gs_result_json → {}.
    NUNCA levanta."""
    # 1) local
    try:
        p = ANALYSES_DIR / hash / "result.json"
        if p.exists():
            raw = json.loads(p.read_text() or "{}")
            if isinstance(raw, dict):
                return raw
    except Exception as e:  # noqa: BLE001
        try:
            log.warning("_read_result_json_raw_v2 local falhou %s: %s", hash[:12], e)
        except Exception:
            pass
    # 2) gs_result_json (via dossiê só p/ pegar a URI, não os dados)
    try:
        gs_uri = None
        try:
            peek = db.laudo_dossie(hash)
            if peek:
                gs_uri = (peek.get("exam") or {}).get("gs_result_json")
        except Exception:
            gs_uri = None
        if gs_uri and str(gs_uri).startswith("gs://"):
            raw = _download_gcs_json(str(gs_uri))
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return {}


def _read_upload_json_raw_v2(hash: str) -> dict:
    """Lê upload.json bruto (metadados candidato/exame/resultado_exame).
    Local → gs_upload_json best-effort → {}. NUNCA levanta."""
    try:
        p = ANALYSES_DIR / hash / "upload.json"
        if p.exists():
            d = json.loads(p.read_text() or "{}")
            if isinstance(d, dict):
                return d
    except Exception as e:  # noqa: BLE001
        try:
            log.warning("_read_upload_json_raw_v2 local falhou %s: %s", hash[:12], e)
        except Exception:
            pass
    try:
        gs_uri = None
        try:
            peek = db.laudo_dossie(hash)
            if peek:
                gs_uri = (peek.get("exam") or {}).get("gs_upload_json")
        except Exception:
            gs_uri = None
        if gs_uri and str(gs_uri).startswith("gs://"):
            raw = _download_gcs_json(str(gs_uri))
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return {}


def _laudo_pdf_v2_html(hash: str) -> str:
    """Monta o HTML do laudo oficial v2 a partir de result.json + upload.json +
    training_annotations. Cada bloco é isolado em try/except — nenhuma seção
    pode derrubar o documento. Retorna sempre uma string HTML A4 válida."""
    result = _read_result_json_raw_v2(hash)
    upload = _read_upload_json_raw_v2(hash)
    train_ann = _read_training_annotations(hash)
    emitido = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")

    # ---- metadados ----------------------------------------------------------
    cand = (
        (upload.get("candidato") or result.get("candidato") or {})
        if isinstance(upload, dict)
        else {}
    )
    if not isinstance(cand, dict):
        cand = {}
    exa = (upload.get("exame") or result.get("exam") or {}) if isinstance(upload, dict) else {}
    if not isinstance(exa, dict):
        exa = {}
    video = result.get("video") if isinstance(result.get("video"), dict) else {}
    try:
        duracao_seg = int(float(video.get("duration_s") or 0))
    except (TypeError, ValueError):
        duracao_seg = 0
    duracao_fmt = _mmss_v2(duracao_seg) if duracao_seg else "—"
    data_exame = ""
    try:
        ra = upload.get("received_at") or ""
        data_exame = str(ra)[:10] if ra else ""
    except Exception:
        data_exame = ""

    # ---- veredito IA (ValBot/Gemini) ---------------------------------------
    aprovado_ia = result.get("aprovado")
    try:
        pont_total = result.get("pontuacao_total")
        pont_total = int(pont_total) if pont_total is not None else None
    except (TypeError, ValueError):
        pont_total = None
    # ---- resultado oficial (TechPrático) -----------------------------------
    res_oficial_raw = (upload.get("resultado_exame") if isinstance(upload, dict) else None) or ""
    res_oficial_raw = str(res_oficial_raw).strip().upper()
    _map_oficial = {"A": "APROVADO", "R": "REPROVADO", "N": "REPROVADO"}
    res_oficial = _map_oficial.get(res_oficial_raw, res_oficial_raw or "—")
    oficial_aprovado = res_oficial_raw == "A"

    # ---- concordância -------------------------------------------------------
    selo = "—"
    selo_cls = ""
    if aprovado_ia is not None and res_oficial_raw in ("A", "R", "N"):
        if bool(aprovado_ia) == oficial_aprovado:
            selo, selo_cls = "CONCORDÂNCIA", "ok"
        else:
            selo, selo_cls = "DIVERGÊNCIA", "div"

    ia_label = "—"
    if aprovado_ia is not None:
        ia_label = "APROVADO" if bool(aprovado_ia) else "REPROVADO"
    ia_extra = f" ({pont_total} pts)" if pont_total is not None else ""

    blocos = []

    # ===== cabeçalho institucional ==========================================
    blocos.append(f"""
    <div class="hdr">
      <div class="hdr-l">ValBot · Auditoria Automatizada de Exames Práticos</div>
      <h1>LAUDO TÉCNICO DE EXAME PRÁTICO DE DIREÇÃO VEICULAR</h1>
      <div class="hdr-sub">{_esc_v2(_RESOLUCAO_V2)} · versão {_esc_v2(_MATRIZ_VERSAO_V2)}</div>
      <div class="hdr-sub">Emitido em {_esc_v2(emitido)}</div>
    </div>""")

    # ===== identificação ====================================================
    try:
        blocos.append(f"""
    <h2>1. Identificação do Exame</h2>
    <table class="kv">
      <tr><th>Candidato</th><td>{_esc_v2(cand.get("nome"))}</td>
          <th>RENACH</th><td>{_esc_v2(cand.get("renach"))}</td></tr>
      <tr><th>CPF</th><td>{_esc_v2(cand.get("cpf"))}</td>
          <th>Processo</th><td>{_esc_v2(cand.get("processo"))}</td></tr>
      <tr><th>Categoria</th><td>{_esc_v2(cand.get("categoria"))}</td>
          <th>Veículo</th><td>{_esc_v2(exa.get("veiculo"))}</td></tr>
      <tr><th>Unidade/Local</th><td>{_esc_v2(exa.get("local"))}</td>
          <th>Auto-escola</th><td>{_esc_v2(exa.get("auto_escola"))}</td></tr>
      <tr><th>Examinador</th><td>{_esc_v2(exa.get("examinador"))}</td>
          <th>Data do exame</th><td>{_esc_v2(data_exame)}</td></tr>
      <tr><th>Duração</th><td>{_esc_v2(duracao_fmt)}</td>
          <th>Hash do exame</th><td class="mono">{_esc_v2(hash)}</td></tr>
    </table>""")
    except Exception as e:  # noqa: BLE001
        log.warning("laudo v2 bloco identificacao falhou %s: %s", hash[:12], e)

    # ===== comparativo de resultados ========================================
    try:
        blocos.append(f"""
    <h2>2. Comparativo de Resultados</h2>
    <table class="cmp">
      <tr><th>Resultado Oficial (TechPrático)</th>
          <th>Veredito ValBot (IA — Gemini)</th>
          <th>Concordância</th></tr>
      <tr>
        <td class="big {"ok" if oficial_aprovado else "div"}">{_esc_v2(res_oficial)}</td>
        <td class="big {"ok" if (aprovado_ia is True) else ("div" if aprovado_ia is False else "")}">{_esc_v2(ia_label)}{_esc_v2(ia_extra) if ia_extra else ""}</td>
        <td class="big {selo_cls}">{_esc_v2(selo)}</td>
      </tr>
    </table>
    <p class="note">Resultado oficial conforme registro TechPrático
    (resultado_exame = <span class="mono">{_esc_v2(res_oficial_raw or "—")}</span>).
    Veredito ValBot derivado da análise automatizada (Gemini) sobre as câmeras do veículo.</p>""")
    except Exception as e:  # noqa: BLE001
        log.warning("laudo v2 bloco comparativo falhou %s: %s", hash[:12], e)

    # ===== cadeia de decisão — os 5 pareceres ===============================
    # Reúne num só lugar, na ordem da escalação, os CINCO contextos de veredito do
    # exame: ① Examinador, ② Auditor Val (IA), ③ Comitê de IA, ④ Auditor (humano),
    # ⑤ Supervisor (decisão final). Comitê/Parecer/Decisão só existem no DB, por
    # isso reusamos _laudo_blocos_14_2 (mesma fonte do /laudo-json → web e PDF
    # ficam coerentes; resiliente: DB off → blocos vazios → pareceres "pendentes").
    try:
        _b14 = {}
        try:
            _b14 = (_laudo_blocos_14_2(hash) or {}).get("blocos") or {}
        except Exception:  # noqa: BLE001
            _b14 = {}

        def _blk(nome: str) -> dict:
            d = _b14.get(nome)
            return d if isinstance(d, dict) else {}

        def _first(d: dict, *keys):
            for k in keys:
                v = d.get(k)
                if v not in (None, ""):
                    return v
            return ""

        def _ar(v) -> tuple[str, str]:
            """(rótulo oficial, classe css) — terminologia travada APROVADO/REPROVADO."""
            s = str(v).strip().upper()
            if v is True or s.startswith("APRO") or s in ("A", "APTO"):
                return "APROVADO", "ap"
            if v is False or s.startswith("REPRO") or s in ("R", "INAPTO"):
                return "REPROVADO", "rp"
            return "—", "pend"

        def _tem(d: dict) -> bool:
            return any(v not in (None, "", []) for v in d.values())

        # ① Examinador
        _o = _blk("4_resultado_oficial")
        _ex_lbl, _ex_cls = _ar(_first(_o, "resultado_oficial", "resultado_exame"))
        _ex_resp = _first(_blk("3_examinador"), "nome") or "Examinador"
        _ex_pont = _first(_o, "pontuacao_oficial")
        _ex_sint = (
            f"Pontuação oficial: {_ex_pont}"
            if str(_ex_pont)
            else "Decisão presencial (TechPrático)"
        )

        # ② Auditor Val (IA)
        _c = _blk("5_resultado_calculado")
        _ia_lbl, _ia_cls = _ar(_first(_c, "resultado_calculado", "aprovado"))
        _ia_resp = (
            _first(_blk("1_identificacao"), "modelo_ia_principal", "engine_backend")
            or "Motor automático"
        )
        _ia_pont = _first(_c, "pontuacao_calculada", "pontuacao_total")
        _ia_sint = (
            f"Pontuação calculada: {_ia_pont}" if str(_ia_pont) else "Resultado calculado pela IA"
        )

        # ③ Comitê de IA (recomendação, não veredito final)
        _cm = _blk("9_comite_ia")
        _cm_concl = str(_first(_cm, "conclusao_comite", "conclusao"))
        _cm_map = {
            "concorda_com_examinador": "Concorda com o examinador",
            "manter_divergencia_com_fundamentacao": "Mantém divergência (fundamentada)",
        }
        _cm_lbl = _cm_map.get(_cm_concl, _cm_concl)
        _cm_rec = str(_first(_cm, "recomendacao_para_auditor", "recomendacao"))
        if _tem(_cm):
            _cm_vere, _cm_cls = (_cm_lbl or "—"), ""
            _cm_sint = _cm_rec or "Refino multi-modelo (recomendação, não veredito final)"
        else:
            _cm_vere, _cm_cls = "Não acionado", "pend"
            _cm_sint = "Sem divergência a refinar."

        # ④ Auditor (humano)
        _p = _blk("10_parecer_auditor")
        _pa_fin_lbl, _pa_fin_cls = _ar(_first(_p, "resultado_final"))
        _pa_dec = str(_first(_p, "decisao"))
        _pa_dec_lbl = {"concorda": "Concorda com a IA", "discorda": "Diverge da IA"}.get(
            _pa_dec, _pa_dec
        )
        if _tem(_p):
            _pa_vere, _pa_cls = (
                (_pa_fin_lbl, _pa_fin_cls) if _pa_fin_lbl != "—" else (_pa_dec_lbl or "—", "")
            )
            _pa_resp = str(_first(_p, "auditor")) or "Auditor responsável"
            _pa_sint = str(_first(_p, "justificativa")) or "Parecer registrado."
        else:
            _pa_vere, _pa_cls, _pa_resp = "—", "pend", "Auditor responsável"
            _pa_sint = "Aguardando parecer do auditor."

        # ⑤ Supervisor (decisão final)
        _d = _blk("11_decisao_supervisor")
        _ds_dec = str(_first(_d, "decisao_final", "decisao"))
        _ds_lbl = {"homologar": "Homologado", "reformar": "Reformado"}.get(_ds_dec, _ds_dec)
        if _tem(_d):
            _ds_vere = _ds_lbl or "—"
            _ds_cls = "ap" if _ds_dec == "homologar" else ("rp" if _ds_dec == "reformar" else "")
            _ds_resp = str(_first(_d, "supervisor", "decidido_por")) or "Supervisor"
            _ds_sint = str(_first(_d, "justificativa")) or "Decisão registrada."
        else:
            _ds_vere, _ds_cls, _ds_resp = "—", "pend", "Supervisor"
            _ds_sint = "Aguardando decisão do supervisor."

        _cadeia = [
            ("①", "Examinador", _ex_lbl, _ex_cls, _ex_resp, _ex_sint),
            ("②", "Auditor Val (IA)", _ia_lbl, _ia_cls, _ia_resp, _ia_sint),
            ("③", "Comitê de IA", _cm_vere, _cm_cls, "Refino multi-modelo", _cm_sint),
            ("④", "Auditor", _pa_vere, _pa_cls, _pa_resp, _pa_sint),
            ("⑤", "Supervisor", _ds_vere, _ds_cls, _ds_resp, _ds_sint),
        ]
        _rows = "".join(
            f'<tr><td style="text-align:center">{_n}</td>'
            f"<td>{_esc_v2(_rot)}</td>"
            f'<td class="cad-v {_cls}">{_esc_v2(_vere)}</td>'
            f"<td>{_esc_v2(_resp)}</td><td>{_esc_v2(_sint)}</td></tr>"
            for (_n, _rot, _vere, _cls, _resp, _sint) in _cadeia
        )
        blocos.append(f"""
    <h2>Cadeia de Decisão — 5 Pareceres</h2>
    <p class="note">Os cinco contextos de veredito sobre este exame, na ordem da escalação — do
    examinador presencial à decisão final do supervisor. Cada parecer é registrado de forma
    independente e preservado para auditoria.</p>
    <table class="cad">
      <tr><th style="width:5%">#</th><th style="width:19%">Parecer</th><th style="width:17%">Veredito</th>
          <th style="width:22%">Responsável / Fonte</th><th>Síntese</th></tr>
      {_rows}
    </table>""")
    except Exception as e:  # noqa: BLE001
        log.warning("laudo v2 bloco cadeia 5 pareceres falhou %s: %s", hash[:12], e)

    # ===== infrações detectadas pelo ValBot (Gemini) ========================
    try:
        infl = (
            result.get("infracoes_avaliadas")
            or result.get("infracoes_detectadas")
            or result.get("infracoes")
            or []
        )
        if not isinstance(infl, list):
            infl = []
        if infl:
            linhas = []
            for inf in infl:
                if not isinstance(inf, dict):
                    continue
                ts = inf.get("ts_seconds")
                if ts is None:
                    ts = inf.get("timestamp_s")
                tempo = _mmss_v2(ts)
                cod = inf.get("id") or inf.get("codigo") or inf.get("base_legal") or "—"
                sev = inf.get("severidade") or inf.get("gravidade") or "—"
                pts = inf.get("pontos")
                pts = str(pts) if pts is not None else "—"
                desc = inf.get("descricao") or inf.get("conduta_pontuada") or "—"
                evid = inf.get("evidence") or inf.get("evidencia") or "—"
                base = inf.get("base_legal") or inf.get("conduta_pontuada") or "—"
                gcls = _grav_class_v2(sev)
                linhas.append(f"""
      <tr>
        <td class="mono">{_esc_v2(tempo)}</td>
        <td class="mono">{_esc_v2(cod)}</td>
        <td><span class="badge {gcls}">{_esc_v2(sev)}</span></td>
        <td style="text-align:center">{_esc_v2(pts)}</td>
        <td>{_esc_v2(desc)}</td>
        <td class="evid">{_esc_v2(evid)}<br><span class="bl">{_esc_v2(base)}</span></td>
      </tr>""")
            blocos.append(f"""
    <h2>3. Infrações Detectadas pelo ValBot ({len(linhas)})</h2>
    <table class="inf">
      <tr><th>Tempo</th><th>Código (Art./MBEDV)</th><th>Gravidade</th>
          <th>Pontos</th><th>Descrição</th><th>Evidência / Base legal</th></tr>
      {"".join(linhas)}
    </table>""")
        else:
            blocos.append("""
    <h2>3. Infrações Detectadas pelo ValBot</h2>
    <p class="vazio">Nenhuma infração detectada pela análise automatizada.</p>""")
    except Exception as e:  # noqa: BLE001
        log.warning("laudo v2 bloco infracoes falhou %s: %s", hash[:12], e)
        blocos.append("""
    <h2>3. Infrações Detectadas pelo ValBot</h2>
    <p class="vazio">Seção indisponível.</p>""")

    # ===== comentários do examinador (TechPrático) ==========================
    try:
        if isinstance(train_ann, list) and train_ann:
            linhas = []
            for a in train_ann:
                if isinstance(a, dict):
                    ts = a.get("timestamp") or "—"
                    txt = a.get("anotacoes") or a.get("anotacao") or a.get("texto") or "—"
                else:
                    ts, txt = "—", str(a)
                linhas.append(f"""
      <tr><td class="mono">{_esc_v2(ts)}</td><td>{_esc_v2(txt)}</td></tr>""")
            blocos.append(f"""
    <h2>4. Comentários do Examinador (TechPrático) ({len(linhas)})</h2>
    <table class="inf">
      <tr><th style="width:14%">Tempo</th><th>Anotação do examinador</th></tr>
      {"".join(linhas)}
    </table>""")
        else:
            blocos.append("""
    <h2>4. Comentários do Examinador (TechPrático)</h2>
    <p class="vazio">Nenhum comentário do examinador registrado para este exame.</p>""")
    except Exception as e:  # noqa: BLE001
        log.warning("laudo v2 bloco comentarios falhou %s: %s", hash[:12], e)

    # ===== reconciliação / parecer do auditor (best-effort) =================
    try:
        parecer = None
        try:
            dossie = db.laudo_dossie(hash)
            if isinstance(dossie, dict):
                rec = dossie.get("reconciliacao") or dossie.get("parecer") or {}
                if isinstance(rec, dict):
                    parecer = rec.get("parecer_auditor") or rec.get("texto") or rec.get("conclusao")
                elif isinstance(rec, str):
                    parecer = rec
        except Exception:
            parecer = None
        if parecer and str(parecer).strip():
            blocos.append(f"""
    <h2>5. Parecer do Auditor</h2>
    <p class="note">{_esc_v2(parecer)}</p>""")
    except Exception as e:  # noqa: BLE001
        log.warning("laudo v2 bloco parecer falhou %s: %s", hash[:12], e)

    # ===== rodapé / integridade =============================================
    try:
        rep_id = f"LAU-{hash[:12].upper()}"
        fonte = "result.json + upload.json (storage/analyses)"
        blocos.append(f"""
    <div class="foot">
      <strong>Integridade:</strong> Matriz {_esc_v2(_MATRIZ_VERSAO_V2)} ·
      {_esc_v2(_RESOLUCAO_V2)} ·
      Relatório {_esc_v2(rep_id)} · Hash do exame
      <span class="mono">{_esc_v2(hash)}</span> · Fonte: {_esc_v2(fonte)}.<br>
      Documento gerado automaticamente pelo ValBot. A análise por IA tem caráter
      auxiliar à decisão do examinador credenciado; o resultado oficial do exame é
      o registrado pelo órgão executivo de trânsito conforme a legislação vigente.
    </div>""")
    except Exception as e:  # noqa: BLE001
        log.warning("laudo v2 rodape falhou %s: %s", hash[:12], e)

    corpo = "".join(blocos)
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
    <style>
    @page {{ size: A4; margin: 16mm 14mm; }}
    body {{ font-family:'Helvetica','Arial',sans-serif; font-size:10.5px; color:#1c2421; line-height:1.4; }}
    .hdr {{ border-bottom:3px solid #0b7a44; padding-bottom:8px; margin-bottom:12px; }}
    .hdr-l {{ font-size:9px; letter-spacing:1px; text-transform:uppercase; color:#0b7a44; font-weight:700; }}
    h1 {{ font-size:15px; margin:4px 0 2px; color:#0b3a22; }}
    .hdr-sub {{ font-size:9.5px; color:#55615b; }}
    h2 {{ font-size:12px; color:#0b3a22; border-left:4px solid #0b7a44; padding-left:7px; margin:14px 0 5px; }}
    table {{ border-collapse:collapse; width:100%; margin:4px 0; }}
    th,td {{ border:1px solid #d9e0dc; padding:4px 7px; text-align:left; vertical-align:top; }}
    table.kv th {{ background:#f1f6f3; width:16%; font-weight:600; color:#33403a; }}
    table.cmp th {{ background:#0b7a44; color:#fff; text-align:center; font-size:10px; }}
    table.cmp td {{ text-align:center; }}
    td.big {{ font-size:14px; font-weight:800; padding:10px; }}
    td.big.ok {{ color:#0b7a44; }} td.big.div {{ color:#b42318; }}
    table.inf th {{ background:#f1f6f3; font-size:9.5px; }}
    table.inf td {{ font-size:9.5px; }}
    table.cad th {{ background:#f1f6f3; font-size:9.5px; color:#33403a; }}
    table.cad td {{ font-size:9.5px; }}
    td.cad-v {{ font-weight:700; }}
    td.cad-v.ap {{ color:#0b7a44; }} td.cad-v.rp {{ color:#b42318; }}
    td.cad-v.pend {{ color:#999; font-weight:400; font-style:italic; }}
    .evid {{ font-size:9px; color:#3a4540; }} .bl {{ color:#7a857f; font-style:italic; }}
    .mono {{ font-family:'Courier New',monospace; font-size:9px; }}
    .badge {{ display:inline-block; padding:1px 6px; border-radius:3px; font-size:8.5px; font-weight:700; color:#fff; }}
    .badge.eliminatoria,.badge.gravissima {{ background:#b42318; }}
    .badge.grave {{ background:#d97706; }}
    .badge.media {{ background:#ca8a04; }}
    .badge.leve {{ background:#2563eb; }}
    .badge.etica {{ background:#7c3aed; }}
    .note {{ font-size:10px; color:#444; margin:6px 0; }}
    .vazio {{ color:#999; font-style:italic; margin:6px 0; }}
    .foot {{ margin-top:16px; font-size:8.5px; color:#777; border-top:1px solid #e3e8e5; padding-top:7px; }}
    </style></head><body>{corpo}</body></html>"""


@app.get("/api/exams/{hash}/laudo-pdf")
def get_laudo_pdf_dossie(hash: str, _sess: dict = Depends(require_session)):
    """PDF do laudo oficial (v2 — reescrito do zero). Se já existe laudo.pdf do
    pipeline, serve-o; senão monta o documento v2 a partir de result.json +
    upload.json + training_annotations. WeasyPrint ausente → 200 com o HTML.
    """
    # v2: SEMPRE regenera a partir de result.json + training_annotations e serve
    # INLINE. O laudo.pdf cacheado do pipeline vinha vazio (so status) e baixava.
    html = _laudo_pdf_v2_html(hash)
    pdf = _render_pdf_bytes(html)
    if pdf is None:
        from fastapi.responses import HTMLResponse

        return HTMLResponse(content=html, headers={"X-Laudo-Fallback": "html"})
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="laudo-{hash[:12]}.pdf"'},
    )


@app.get("/api/relatorios/consolidado")
def relatorios_consolidado(hashes: str = "", _sess: dict = Depends(require_session)):
    """PDF consolidado de múltiplos exames (um por página). `hashes` = CSV de hashes.

    DB off / sem dados → cada hash vira página placeholder. WeasyPrint ausente
    → devolve o HTML (200).
    """
    lista = [h.strip() for h in (hashes or "").split(",") if h.strip()]
    if not lista:
        raise HTTPException(422, "informe ?hashes=h1,h2,...")
    laudos = [_laudo_blocos_14_2(h) for h in lista[:100]]
    html = _laudo_pdf_html(laudos)
    pdf = _render_pdf_bytes(html)
    if pdf is None:
        from fastapi.responses import HTMLResponse

        return HTMLResponse(content=html, headers={"X-Laudo-Fallback": "html"})
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="consolidado.pdf"'},
    )


@app.get("/api/relatorios/export.csv")
def relatorios_export_csv(
    dias: int | None = None,
    unidade: str | None = None,
    examinador: str | None = None,
    resultado: str | None = None,
    categoria: str | None = None,
    limit: int = 5000,
    _sess: dict = Depends(require_session),
):
    """Exporta os resultados filtrados em CSV. DB off → CSV só com o cabeçalho (200)."""
    import csv
    import io

    limit = max(1, min(int(limit), 20000))
    rows = (
        db.list_resultados(
            dias=dias,
            unidade=unidade,
            examinador=examinador,
            resultado=resultado,
            categoria=categoria,
            limit=limit,
        )
        or []
    )
    campos = [
        "hash",
        "candidato_nome",
        "renach",
        "local_unidade",
        "examinador",
        "categoria",
        "status",
        "resultado",
        "resultado_exame",
        "aprovado",
        "pontuacao_total",
        "num_infracoes",
        "cost_usd",
        "duration_s",
        "created_at",
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(campos)
    for r in rows:
        w.writerow([r.get(c) for c in campos])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="relatorio_resultados.csv"'},
    )


# ---------------------------------------------------------------------------
# 3. MEDIÇÃO — telemetria do auditor + métricas agregadas.
# ---------------------------------------------------------------------------
class _TelemetriaIn(BaseModel):
    exam_hash: str | None = Field(None, description="hash do exame revisado")
    assistido_ate_seg: float | None = Field(None, description="maior offset assistido (s)")
    dur_seg: float | None = Field(None, description="duração do vídeo (s)")
    tempo_sessao_s: float | None = Field(None, description="tempo de parede da sessão (s)")
    avancos_bloqueados: int = Field(0, description="nº de avanços bloqueados pelo gate")
    auditor: str | None = Field(None, description="opcional; default = sessão")


@app.post("/api/telemetria")
def post_telemetria(
    data: _TelemetriaIn,
    valbot_session: str | None = Cookie(default=None),
    _sess: dict = Depends(require_session),
):
    """Grava telemetria de uma sessão de revisão do Auditor. Eco-mock se DB off."""
    user = _current_user(valbot_session)
    auditor = data.auditor or (user or {}).get("email")
    ok = db.insert_telemetria(
        auditor=auditor,
        exam_hash=data.exam_hash,
        assistido_ate_seg=data.assistido_ate_seg,
        dur_seg=data.dur_seg,
        tempo_sessao_s=data.tempo_sessao_s,
        avancos_bloqueados=data.avancos_bloqueados,
    )
    return {
        "recorded": ok,
        "auditor": auditor,
        "exam_hash": data.exam_hash,
        "source": "db" if ok else "mock",
    }


@app.get("/api/dashboard/auditor-metrics")
def dashboard_auditor_metrics(
    auditor: str | None = None,
    dias: int = 30,
    _sess: dict = Depends(require_session),
):
    """Métricas de produtividade/qualidade do Auditor. DB off → estrutura zerada."""
    dias = max(1, min(int(dias), 365))
    data = db.auditor_metrics(auditor=auditor, dias=dias)
    if data is None:
        return {
            "periodo_dias": dias,
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
            "source": "mock",
        }
    data["source"] = "db"
    return data


# ---------------------------------------------------------------------------
# 4. CRON / BATCH — agendamentos + trigger manual de processamento em lote.
# ---------------------------------------------------------------------------
# categorias CNH válidas para o filtro de batch (ACC + A..E). Vazio/None/"todas"
# => todas as categorias (sem filtro).
_CRON_CATEGORIAS = {"ACC", "A", "B", "C", "D", "E"}


def _norm_categoria(v) -> str | None:
    """Normaliza a categoria escolhida no agendamento/trigger.
    Aceita ACC/A/B/C/D/E (case-insensitive); "todas"/""/None => None (sem filtro).
    Inválida => None (resiliente: trata como 'todas', nunca 500)."""
    if v is None:
        return None
    s = str(v).strip().upper()
    if s in ("", "TODAS", "TODOS", "ALL", "*"):
        return None
    return s if s in _CRON_CATEGORIAS else None


class _CronJobIn(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    enabled: bool = True
    schedule_kind: str = Field("daily", description="daily | hourly | cron | interval")
    horario: str | None = Field(None, description="'HH:MM' p/ schedule_kind=daily")
    cron_expr: str | None = Field(None, description="expressão cron p/ schedule_kind=cron")
    batch_limit: int = Field(50, ge=1, le=5000)
    retry: int = Field(0, ge=0, le=10)
    escopo: str = Field("pending", description="pending | queued | failed | all")
    categoria: str | None = Field(
        None,
        description="ACC|A|B|C|D|E p/ filtrar o batch por categoria CNH; "
        "vazio/None/'todas' => todas as categorias",
    )


class _CronJobPatch(BaseModel):
    nome: str | None = None
    enabled: bool | None = None
    schedule_kind: str | None = None
    horario: str | None = None
    cron_expr: str | None = None
    batch_limit: int | None = Field(None, ge=1, le=5000)
    retry: int | None = Field(None, ge=0, le=10)
    escopo: str | None = None
    categoria: str | None = None


@app.get("/api/admin/cron-jobs")
def cron_list(_sess: dict = Depends(require_session)):
    """Lista agendamentos + últimos runs. DB off → vazio."""
    jobs = db.list_cron_jobs()
    if jobs is None:
        return {
            "count": 0,
            "items": [],
            "runs": [],
            "source": "mock",
            "scheduler": _scheduler_status(),
        }
    runs = db.list_cron_runs(limit=50) or []
    return {
        "count": len(jobs),
        "items": jobs,
        "runs": runs,
        "source": "db",
        "scheduler": _scheduler_status(),
    }


@app.post("/api/admin/cron-jobs")
def cron_create(data: _CronJobIn, _sess: dict = Depends(require_session)):
    """Cria um agendamento."""
    res = db.create_cron_job(
        nome=data.nome,
        enabled=data.enabled,
        schedule_kind=data.schedule_kind,
        horario=data.horario,
        cron_expr=data.cron_expr,
        batch_limit=data.batch_limit,
        retry=data.retry,
        escopo=data.escopo,
        categoria=_norm_categoria(data.categoria),
    )
    if res is None:
        return {**data.model_dump(), "id": None, "source": "mock"}
    _scheduler_sync()
    return {**res, "source": "db"}


@app.patch("/api/admin/cron-jobs/{job_id}")
def cron_update(job_id: str, data: _CronJobPatch, _sess: dict = Depends(require_session)):
    """Atualiza um agendamento."""
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if "categoria" in fields:
        # normaliza p/ ACC..E ou None (sem filtro). Mantém a chave mesmo se virar
        # None, p/ permitir LIMPAR o filtro (voltar a 'todas') via PATCH.
        fields["categoria"] = _norm_categoria(fields["categoria"])
    if not fields:
        raise HTTPException(422, "nenhum campo para atualizar")
    res = db.update_cron_job(job_id, fields)
    if res is None:
        if db._disabled():
            return {"id": job_id, **fields, "source": "mock"}
        raise HTTPException(404, f"cron-job {job_id} não encontrado")
    _scheduler_sync()
    return {**res, "source": "db"}


@app.delete("/api/admin/cron-jobs/{job_id}")
def cron_delete(job_id: str, _sess: dict = Depends(require_session)):
    """Remove um agendamento."""
    ok = db.delete_cron_job(job_id)
    if not ok and not db._disabled():
        raise HTTPException(404, f"cron-job {job_id} não encontrado")
    _scheduler_sync()
    return {"deleted": True, "id": job_id, "source": "mock" if db._disabled() else "db"}


_ESCOPO_STATUSES = {
    "pending": ("pending", "queued", "failed"),
    "queued": ("queued",),
    "failed": ("failed",),
    "all": ("pending", "queued", "failed"),
}


def _exam_categoria(aid: str) -> str | None:
    """Le a categoria CNH (ACC/A/B/C/D/E) de um exame a partir do upload.json
    (candidato.categoria). None se ausente/erro. Usado p/ filtrar o batch."""
    try:
        up = json.loads((ANALYSES_DIR / aid / "upload.json").read_text())
        cat = ((up.get("candidato") or {}).get("categoria") or "").strip().upper()
        return cat or None
    except Exception:
        return None


def _run_batch_job(
    job_id: str | None,
    batch_limit: int,
    escopo: str,
    categoria: str | None = None,
) -> None:
    """Worker em background: reusa list_pending + process_one do process_pending_s3.

    Abre um cron_job_runs, processa até `batch_limit` exames pendentes, agrega
    custo (lê cost_usd do result.json) e fecha o run com os totais. Resiliente:
    nunca levanta (background).
    """
    run_id = db.start_cron_run(job_id)
    n_ok = n_fail = 0
    custo = 0.0
    try:
        from tooling.process_pending_s3 import list_pending, process_one

        cat = _norm_categoria(categoria)
        todos = list_pending()
        if cat:
            todos = [aid for aid in todos if _exam_categoria(aid) == cat]
        pendentes = todos[: max(1, int(batch_limit))]
        log.info(
            "cron batch job=%s escopo=%s categoria=%s limit=%s pendentes=%d",
            job_id,
            escopo,
            cat or "todas",
            batch_limit,
            len(pendentes),
        )
        for aid in pendentes:
            try:
                ok = process_one(aid)
                if ok:
                    n_ok += 1
                    # agrega custo do result.json se disponível
                    try:
                        rp = ANALYSES_DIR / aid / "result.json"
                        if rp.exists():
                            res = json.loads(rp.read_text())
                            custo += float((res.get("cost") or {}).get("usd") or 0)
                    except Exception:
                        pass
                else:
                    n_fail += 1
            except Exception as e:  # noqa: BLE001 — isola falha por exame
                n_fail += 1
                log.warning("cron batch [%s] falhou: %s", aid[:12], e)
        db.finish_cron_run(
            run_id, n_processados=n_ok, n_falhas=n_fail, custo_usd=custo, status="success"
        )
    except Exception as e:
        log.exception("cron batch job=%s crashed: %s", job_id, e)
        db.finish_cron_run(
            run_id, n_processados=n_ok, n_falhas=n_fail, custo_usd=custo, status="failed"
        )


class _CronTriggerIn(BaseModel):
    categoria: str | None = Field(
        None,
        description="ACC|A|B|C|D|E p/ filtrar este disparo por categoria CNH; "
        "vazio/None/'todas' => todas. Sobrepõe a categoria do job.",
    )


@app.post("/api/admin/cron-jobs/{job_id}/trigger")
def cron_trigger(
    job_id: str,
    background: BackgroundTasks,
    data: _CronTriggerIn | None = Body(default=None),
    _sess: dict = Depends(require_session),
):
    """Dispara o batch de um agendamento AGORA, em background. Reusa a lógica de
    process_pending_s3 (list_pending + process_one). Devolve imediatamente.

    Body opcional `{categoria}`: filtra ESTE disparo por categoria CNH
    (ACC/A/B/C/D/E). Se omitido, herda a categoria persistida no job; vazio/'todas'
    => todas as categorias."""
    job = db.get_cron_job(job_id)
    batch_limit = int(job.get("batch_limit")) if job else 50
    escopo = job.get("escopo") if job else "pending"
    # precedência: categoria do body (se enviada) > categoria persistida no job
    body_cat = data.categoria if data is not None else None
    categoria = (
        _norm_categoria(body_cat)
        if body_cat is not None
        else _norm_categoria((job or {}).get("categoria"))
    )
    background.add_task(_run_batch_job, job_id, batch_limit, escopo, categoria)
    return {
        "triggered": True,
        "job_id": job_id,
        "batch_limit": batch_limit,
        "escopo": escopo,
        "categoria": categoria or "todas",
        "source": "db" if job else "mock",
    }


@app.get("/api/admin/cron-jobs/{job_id}/runs")
def cron_runs(job_id: str, limit: int = 50, _sess: dict = Depends(require_session)):
    """Histórico de execuções (runs) de um agendamento. DB off → vazio."""
    limit = max(1, min(int(limit), 500))
    runs = db.list_cron_runs(job_id=job_id, limit=limit)
    if runs is None:
        return {"count": 0, "items": [], "job_id": job_id, "source": "mock"}
    return {"count": len(runs), "items": runs, "job_id": job_id, "source": "db"}


# ---------------------------------------------------------------------------
# Scheduler opcional — APScheduler em thread daemon SE a lib existir.
# ---------------------------------------------------------------------------
_SCHEDULER = None  # singleton; None enquanto APScheduler não estiver disponível


def _scheduler_status() -> dict:
    """Estado do scheduler p/ a UI: disponível? rodando? quantos jobs?"""
    try:
        import apscheduler  # noqa: F401

        disponivel = True
    except Exception:
        disponivel = False
    rodando = _SCHEDULER is not None and getattr(_SCHEDULER, "running", False)
    n = len(_SCHEDULER.get_jobs()) if rodando else 0
    return {"disponivel": disponivel, "rodando": rodando, "jobs_registrados": n}


def _scheduler_sync() -> None:
    """Re-registra os jobs habilitados do DB no APScheduler (se ativo).

    TODO: granularizar (add/remove por id) em vez de remover-tudo-e-recriar.
    """
    if _SCHEDULER is None:
        return
    try:
        from apscheduler.triggers.cron import CronTrigger  # type: ignore

        _SCHEDULER.remove_all_jobs()
        for job in db.list_cron_jobs() or []:
            if not job.get("enabled"):
                continue
            kind = job.get("schedule_kind")
            trigger = None
            if kind == "cron" and job.get("cron_expr"):
                try:
                    trigger = CronTrigger.from_crontab(job["cron_expr"])
                except Exception:
                    trigger = None
            elif kind == "daily" and job.get("horario"):
                try:
                    hh, mm = str(job["horario"]).split(":")
                    trigger = CronTrigger(hour=int(hh), minute=int(mm))
                except Exception:
                    trigger = None
            elif kind == "hourly":
                trigger = CronTrigger(minute=0)
            if trigger is None:
                continue
            _SCHEDULER.add_job(
                _run_batch_job,
                trigger,
                args=[
                    job["id"],
                    job.get("batch_limit") or 50,
                    job.get("escopo") or "pending",
                    job.get("categoria"),
                ],
                id=str(job["id"]),
                replace_existing=True,
            )
        log.info("scheduler sync ok: %d jobs", len(_SCHEDULER.get_jobs()))
    except Exception as e:
        log.warning("scheduler sync falhou: %s", e)


@app.on_event("startup")
def _start_scheduler() -> None:
    """Tenta subir o APScheduler em background no boot. Se a lib não existir,
    deixa só o trigger manual (não quebra o boot). Desligável com
    VALBOT_DISABLE_SCHEDULER=1."""
    global _SCHEDULER
    if os.environ.get("VALBOT_DISABLE_SCHEDULER") == "1":
        log.info("scheduler desabilitado via VALBOT_DISABLE_SCHEDULER=1")
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
    except Exception:
        log.info("APScheduler não instalado — só trigger manual de cron-jobs disponível")
        return
    try:
        _SCHEDULER = BackgroundScheduler(daemon=True)
        _SCHEDULER.start()
        _scheduler_sync()
        log.info("APScheduler iniciado (thread daemon)")
    except Exception as e:
        log.warning("falha ao iniciar APScheduler: %s", e)
        _SCHEDULER = None


# ---------------------------------------------------------------------------
# 5. SUPERVISOR — decisão final sobre a OS (homologar | reformar).
# ---------------------------------------------------------------------------
class _DecisaoSupervisorIn(BaseModel):
    decisao: str = Field(..., description="homologar | reformar")
    justificativa: str | None = None
    resultado_final: str | None = Field(None, description="aprovado | reprovado")
    homologar_conduta: bool = Field(
        False,
        description="Mantém (true) o encaminhamento da conduta da examinadora ao DETRAN (Bloco 9).",
    )


@app.post("/api/os/{os_id}/decisao")
def post_decisao_supervisor(
    os_id: str,
    data: _DecisaoSupervisorIn,
    valbot_session: str | None = Cookie(default=None),
    _sess: dict = Depends(require_supervisor),
):
    """Grava a decisão final do Supervisor; encerra a OS (status=decisao_final).

    `decisao`: 'homologar' (mantém parecer auditor) | 'reformar' (sobrepõe).
    Eco-mock quando DB off ou OS inexistente.
    """
    if data.decisao not in ("homologar", "reformar"):
        raise HTTPException(422, "decisao deve ser 'homologar' ou 'reformar'")
    user = _current_user(valbot_session)
    supervisor = (user or {}).get("email")
    saved = db.save_supervisor_decisao(
        os_id,
        supervisor=supervisor,
        decisao=data.decisao,
        resultado_final=data.resultado_final,
        justificativa=data.justificativa,
        homologar_conduta=data.homologar_conduta,
    )
    if saved is None:
        return {
            "os_id": os_id,
            "supervisor": supervisor,
            "decisao": data.decisao,
            "resultado_final": data.resultado_final,
            "justificativa": data.justificativa,
            "homologar_conduta": data.homologar_conduta,
            "status_os": "decisao_final",
            "source": "mock",
        }
    saved["source"] = "db"
    return saved


@app.get("/api/os/{os_id}/decisao")
def get_decisao_supervisor(os_id: str, _sess: dict = Depends(require_session)):
    """Recupera a decisão do supervisor de uma OS. Mock vazio quando DB off."""
    d = db.get_supervisor_decisao(os_id)
    if d is None:
        if db._disabled():
            return {
                "os_id": os_id,
                "decisao": None,
                "resultado_final": None,
                "justificativa": None,
                "status": "pendente",
                "source": "mock",
            }
        raise HTTPException(404, f"OS {os_id} sem decisão de supervisor")
    return {**d, "source": "db"}


@app.get("/api/dashboard/supervisor-metrics")
def dashboard_supervisor_metrics(dias: int = 30, _sess: dict = Depends(require_session)):
    """Concordância Supervisor×Auditor/IA. Usa db.supervisor_concordancia (db.py é
    montado em prod). NÃO depende de backend.dashboard.metrics (não montado em
    prod). Resiliente: DB off / falha → estrutura zerada, nunca 500."""
    dias = max(1, min(int(dias), 365))
    try:
        data = db.supervisor_concordancia(dias=dias)
        if data is None:
            return {
                "periodo_dias": dias,
                "total_decisoes": 0,
                "homologadas": 0,
                "reformadas": 0,
                "concordancia_supervisor_auditor_pct": 0.0,
                "concordancia_supervisor_ia_pct": 0.0,
                "source": "mock",
            }
        data["source"] = "db"
        return data
    except Exception as e:
        log.warning("dashboard_supervisor_metrics falhou: %s", e)
        return {
            "periodo_dias": dias,
            "total_decisoes": 0,
            "homologadas": 0,
            "reformadas": 0,
            "concordancia_supervisor_auditor_pct": 0.0,
            "concordancia_supervisor_ia_pct": 0.0,
            "source": "mock",
        }


if __name__ == "__main__":
    import uvicorn

    print(f"[API] Storage em: {STORAGE}")
    print("[API] Endpoints:")
    print("  POST http://localhost:8001/api/exams")
    print("  GET  http://localhost:8001/api/exams")
    print("  GET  http://localhost:8001/api/exams/{id}")
    print("  GET  http://localhost:8001/api/bench/videos")
    print("  GET  http://localhost:8001/api/bench/{slug}/models")
    print("  GET  http://localhost:8001/api/bench/{slug}/laudo/{model_id}")
    print("  GET  http://localhost:8001/static/videos/{filename}")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
