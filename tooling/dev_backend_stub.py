"""
Backend stub para destravar o frontend em dev enquanto a API real não existe.

Responde:
- GET  /api/auth/me       → hidrata sessão a partir do cookie
- POST /api/auth/email    → aceita qualquer email válido, seta cookie
- POST /api/auth/logout   → limpa cookie
- GET  /api/dashboard/kpis, /api/videos, /api/alertas, /api/rubricas/{slug}
                           → vídeos casam com storage/analyses/<sha256>/result.json
                              quando existir; rubricas vêm de src.rubrics.taxonomia.

Rodar: /Users/igorlima/Documents/Valbot/.venv/bin/python -m tooling.dev_backend_stub
Escuta em 0.0.0.0:8001 (casa com BACKEND_URL default do vite.config.ts).
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import Cookie, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.rubrics.taxonomia import (
    CATALOGO,
    LIMITE_APROVACAO,
    Rubrica,
    Severidade,
)
from src.tier_a_pipeline import sha256_arquivo

COOKIE_NAME = "valbot_session"
COOKIE_TTL = 60 * 60 * 24 * 90  # 90 dias
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ADMIN_EMAILS = {"lbigor@icloud.com"}

PROJECT_ROOT = Path(__file__).parent.parent
VIDEOS_DIR = PROJECT_ROOT / "storage" / "videos"
ANALYSES_DIR = PROJECT_ROOT / "storage" / "analyses"

# Cache em memória do hash SHA256 dos vídeos (cálculo é caro: ~1s por 150MB).
# Invalida quando mtime muda.
_HASH_CACHE: dict[str, tuple[float, str]] = {}


def _video_hash(path: Path) -> str:
    """SHA256 de conteúdo (cacheado por mtime). Padroniza com src.tier_a_pipeline."""
    key = str(path)
    mtime = path.stat().st_mtime
    cached = _HASH_CACHE.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    h = sha256_arquivo(path)
    _HASH_CACHE[key] = (mtime, h)
    return h


# ============================================================================
# Mapeamentos taxonomia → schema do frontend (RubricaFull / RubricaInfracao)
# ============================================================================

_GRAVIDADE_MAP = {
    Severidade.GRAVISSIMA: ("gravissima", "GRAVÍSSIMA"),
    Severidade.GRAVE: ("grave", "GRAVE"),
    Severidade.MEDIA: ("media", "MÉDIA"),
    Severidade.LEVE: ("leve", "LEVE"),
}


def _rubrica_payload(slug: str) -> dict:
    """Monta RubricaFull a partir da taxonomia. Slug 1020/2025 = RES_1020_2025."""
    if slug != "1020/2025":
        # 789/2020 foi descontinuada do projeto — devolve vazio mas válido.
        return {
            "slug": slug,
            "nome": f"Res. CONTRAN {slug}",
            "limite_pontuacao": 0,
            "infracoes": [],
            "total_infracoes": 0,
            "contagem_por_gravidade": {
                "eliminatoria": 0,
                "gravissima": 0,
                "grave": 0,
                "media": 0,
                "leve": 0,
            },
        }
    items = [i for i in CATALOGO if i.rubrica == Rubrica.RES_1020_2025]
    contagem = {"eliminatoria": 0, "gravissima": 0, "grave": 0, "media": 0, "leve": 0}
    infracoes_out = []
    for inf in items:
        grav_key, grav_label = _GRAVIDADE_MAP[inf.severidade]
        contagem[grav_key] += 1
        cameras = [c.value for c in inf.cameras_relevantes]
        infracoes_out.append(
            {
                "id": inf.id,
                "gravidade": grav_key,
                "gravidade_label": grav_label,
                "pontos": inf.pontos,
                "descricao": inf.descricao,
                "base_legal": inf.base_legal,
                "cameras": cameras,
                "vlm_prompt_hint": " · ".join(inf.checklist_visual) or None,
                "tier": inf.tier.value,
                "infra_faltante": inf.infra_faltante,
            }
        )
    return {
        "slug": "1020/2025",
        "nome": "Res. CONTRAN 1.020/2025",
        "limite_pontuacao": LIMITE_APROVACAO,
        "infracoes": infracoes_out,
        "total_infracoes": len(infracoes_out),
        "contagem_por_gravidade": contagem,
    }


app = FastAPI(title="VALBOT Dev Stub")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _stream_video_with_range(filepath: Path, range_header: str | None):
    """Streaming de vídeo com Range. Se cliente não mandar Range, envia
    só os primeiros 4MB (suficiente pra metadata + começar a tocar) e o
    player vai pedir Range nos próximos chunks. Evita travar baixando
    300MB de uma vez quando o cliente esquece o Range header.
    """
    from fastapi.responses import StreamingResponse

    file_size = filepath.stat().st_size
    CHUNK = 1 << 20  # 1MB
    DEFAULT_FIRST = 4 << 20  # 4MB pra metadata + buffer inicial

    if range_header is None or not range_header.startswith("bytes="):
        # Sem Range: faz streaming chunked com 200 OK do arquivo inteiro.
        # Sem Content-Length, Cloudflare/proxies não bufferizam (mandam pro
        # cliente em chunks). HTML5 video toca enquanto baixa (faststart MP4).
        def chunker_full():
            with filepath.open("rb") as f:
                while True:
                    buf = f.read(CHUNK)
                    if not buf:
                        break
                    yield buf

        return StreamingResponse(
            chunker_full(),
            status_code=200,
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                # Cloudflare cache estava virando HIT no vídeo inteiro e
                # ignorando Range subsequentes (seek voltava pra 0). Força
                # bypass do cache em qualquer ponto do caminho.
                "Cache-Control": "no-store, must-revalidate, private",
                "CDN-Cache-Control": "no-store",
                "Cloudflare-CDN-Cache-Control": "no-store",
                # sem Content-Length → Transfer-Encoding: chunked
            },
        )

    # Com Range: parse e devolve o trecho pedido em streaming
    spec = range_header.replace("bytes=", "")
    start_str, _, end_str = spec.partition("-")
    start = int(start_str) if start_str else 0
    end = int(end_str) if end_str else min(start + (8 << 20) - 1, file_size - 1)
    end = min(end, file_size - 1)
    length = end - start + 1

    def chunker():
        with filepath.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                buf = f.read(min(CHUNK, remaining))
                if not buf:
                    break
                remaining -= len(buf)
                yield buf

    return StreamingResponse(
        chunker(),
        status_code=206,
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(length),
            "Cache-Control": "no-store, must-revalidate, private",
            "CDN-Cache-Control": "no-store",
            "Cloudflare-CDN-Cache-Control": "no-store",
        },
    )


@app.get("/static/videos/{filename:path}")
def serve_video(filename: str, request: Request):
    """Streaming robusto de vídeos com Range obrigatório (substitui StaticFiles
    pra esses arquivos grandes — quando cliente esquece Range, mandar 300MB
    inteiro trava o player)."""
    fp = VIDEOS_DIR / filename
    if not fp.exists() or not fp.is_file():
        raise HTTPException(404, f"vídeo não encontrado: {filename}")
    return _stream_video_with_range(fp, request.headers.get("range"))


ANALYSES_DIR_FOR_STATIC = PROJECT_ROOT / "storage" / "analyses"
if ANALYSES_DIR_FOR_STATIC.exists():
    app.mount(
        "/static/analyses",
        StaticFiles(directory=str(ANALYSES_DIR_FOR_STATIC)),
        name="analyses",
    )


class EmailIn(BaseModel):
    email: str


def _session_payload(email: str | None) -> dict:
    return {"email": email, "is_admin": bool(email and email in ADMIN_EMAILS)}


@app.get("/api/auth/me")
def get_me(valbot_session: str | None = Cookie(default=None)):
    return _session_payload(valbot_session)


@app.post("/api/auth/email")
def post_email(data: EmailIn, response: Response):
    email = data.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Email inválido")
    response.set_cookie(
        key=COOKIE_NAME,
        value=email,
        max_age=COOKIE_TTL,
        httponly=True,
        samesite="lax",
    )
    return _session_payload(email)


@app.post("/api/auth/logout")
def post_logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@app.get("/api/health")
def health():
    import os

    return {
        "status": "ok",
        "port": 8001,
        "vlm_claude_available": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "vlm_model": "claude-haiku-4-5-20251001",
    }


CONFIG_PATH = PROJECT_ROOT / "storage" / "training" / "config.json"


@app.get("/api/config")
def get_config():
    """Configurações editáveis pelo admin (thresholds, flags)."""
    default = {
        "cinto_threshold_diagonais": 2,
        "cinto_dark_ratio_min": 0.15,
        "cinto_dark_ratio_max": 0.65,
        "yolo_confidence_threshold": 0.25,
        "consolidacao_min_votos": 3,
    }
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text())
            return {**default, **saved}
        except Exception:
            return default
    return default


class ConfigIn(BaseModel):
    cinto_threshold_diagonais: int | None = None
    cinto_dark_ratio_min: float | None = None
    cinto_dark_ratio_max: float | None = None
    yolo_confidence_threshold: float | None = None
    consolidacao_min_votos: int | None = None


@app.put("/api/config")
def put_config(data: ConfigIn):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    current = get_config()
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    new_config = {**current, **update}
    CONFIG_PATH.write_text(json.dumps(new_config, indent=2))
    return {"ok": True, "config": new_config}


@app.put("/api/analyses/{hash}/exam-meta")
def put_exam_meta(hash: str, data: dict):
    """Atualiza metadata do exame (candidato/CPF/etc) sem re-upload."""
    base = ANALYSES_DIR / hash
    if not base.exists():
        raise HTTPException(404, f"hash não encontrado: {hash}")
    meta_path = base / "exam_meta.json"
    current = {}
    if meta_path.exists():
        try:
            current = json.loads(meta_path.read_text())
        except Exception:
            pass
    # Apenas chaves conhecidas (sanitização)
    allowed = {
        "candidato_nome",
        "candidato_cpf",
        "renach",
        "processo",
        "categoria",
        "veiculo",
        "local",
        "examinador",
        "auto_escola",
    }
    for k, v in (data or {}).items():
        if k in allowed:
            current[k] = v
    current["updated_at"] = datetime.now().isoformat(timespec="seconds")
    meta_path.write_text(json.dumps(current, indent=2, ensure_ascii=False))
    return {"ok": True, "meta": current}


@app.get("/api/metrics")
def metrics():
    """
    Métricas agregadas do pipeline. Lê o estado real do storage:
      - n_videos: quantos foram processados
      - votos_aplicados: linhas em examples.jsonl + votos legacy
      - cinto_auto_decididos: frames com vlm_decision.cinto_visivel != null
      - cinto_total: total de frames de cinto extraídos
      - pose_videos: quantos têm pose.json
      - heatmaps: quantos têm heatmap_maos.png
      - vlm_calls: chamadas reais ao Claude (rastreadas em vlm_calls.jsonl se houver)
    """
    n_videos = 0
    cinto_total = 0
    cinto_auto = 0
    pose_videos = 0
    heatmaps = 0
    if VIDEOS_DIR.exists():
        for mp4 in VIDEOS_DIR.glob("*.mp4"):
            h = _video_hash(mp4)
            base = ANALYSES_DIR / h
            if not (base / "result.json").exists():
                continue
            n_videos += 1
            if (base / "pose.json").exists():
                pose_videos += 1
            if (base / "heatmap_maos.png").exists():
                heatmaps += 1
            trail = base / "cinto_trail.json"
            if trail.exists():
                try:
                    t = json.loads(trail.read_text())
                    for f in t.get("frames", []):
                        cinto_total += 1
                        dec = f.get("vlm_decision") or {}
                        if dec.get("cinto_visivel") is not None:
                            cinto_auto += 1
                except Exception:
                    pass

    examples_path = PROJECT_ROOT / "storage" / "training" / "examples.jsonl"
    votos_aplicados = sum(1 for _ in examples_path.open()) if examples_path.exists() else 0
    votes_legacy = PROJECT_ROOT / "storage" / "training" / "review_votes.json"
    if votes_legacy.exists():
        try:
            votos_aplicados += len(json.loads(votes_legacy.read_text()))
        except Exception:
            pass

    return {
        "n_videos": n_videos,
        "votos_aplicados": votos_aplicados,
        "cinto_total": cinto_total,
        "cinto_auto_decididos": cinto_auto,
        "cinto_taxa_auto": (f"{int(100 * cinto_auto / cinto_total)}%" if cinto_total else "—"),
        "pose_videos": pose_videos,
        "heatmaps": heatmaps,
        "vlm_calls": 0,  # ainda sem rastreamento
    }


@app.get("/api/vlm-status")
def vlm_status():
    """Reporta se a camada VLM está ativa (depende de ANTHROPIC_API_KEY no env)."""
    import os

    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {
        "active": has_key,
        "model": "claude-haiku-4-5-20251001" if has_key else None,
        "fallback": "heuristica_hsv_hough",
        "philosophy": (
            "VLM só recebe frames inconclusivos da heurística. "
            "Sem chave, frames inconclusivos vão pra revisão humana."
        ),
        "estimated_cost_per_video": "≤ $0.01 (5 frames × $0.002)"
        if has_key
        else "$0.00 (modo heurística-only)",
    }


@app.get("/api/dashboard/kpis")
def kpis(demo: bool = False):
    """KPIs reais: agrega os result.json existentes em storage/analyses/."""
    if not VIDEOS_DIR.exists():
        return {
            "totals": {},
            "weekly": [],
            "severity": [],
            "unit": [],
            "priority": [],
            "insights": [],
        }

    items = []
    for mp4 in sorted(VIDEOS_DIR.glob("*.mp4")):
        h = _video_hash(mp4)
        result_json = ANALYSES_DIR / h / "result.json"
        if not result_json.exists():
            continue
        try:
            data = json.loads(result_json.read_text())
            items.append((mp4, h, data))
        except Exception:
            pass

    n = len(items)
    n_processados = n
    pontos = [
        sum(i.get("pontos", 0) for i in d.get("infracoes_detectadas", [])) for _, _, d in items
    ]
    aprovados = sum(1 for p in pontos if p <= LIMITE_APROVACAO)
    pendente_revisao_total = sum(
        sum(
            1
            for i in d.get("infracoes_avaliadas", [])
            if i.get("status") == "pendente_revisao_humana"
        )
        for _, _, d in items
    )
    auto_decididos = sum(
        sum(
            1
            for i in d.get("infracoes_avaliadas", [])
            if i.get("veredito") in ("aprovado", "detectado") and i.get("confianca", 0) >= 0.65
        )
        for _, _, d in items
    )
    cinto_aprovado_auto = sum(
        1
        for _, _, d in items
        for i in d.get("infracoes_avaliadas", [])
        if i["id"] == "R1020-GR-f" and i.get("veredito") == "aprovado"
    )

    today = datetime.now().strftime("%a")
    weekly = []
    for i, lbl in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]):
        weekly.append(
            {
                "name": lbl,
                "recebidos": n if i == datetime.now().weekday() else 0,
                "processados": n_processados if i == datetime.now().weekday() else 0,
                "indicio": 0,
            }
        )

    severity = [
        {"name": "Eliminatória", "value": 0, "color": "#7c3aed"},
        {"name": "Gravíssima", "value": 0, "color": "#EF4444"},
        {"name": "Grave", "value": 0, "color": "#F97316"},
        {"name": "Média", "value": 0, "color": "#F59E0B"},
        {"name": "Leve", "value": 0, "color": "#10B981"},
    ]

    insights = [
        {
            "title": "Heurística do cinto",
            "text": f"<b>{cinto_aprovado_auto}/{n}</b> cintos auto-aprovados pela heurística HSV + Hough. Zero chamadas a VLM.",
            "color": "#10B981",
            "icon": "trending",
        },
        {
            "title": "Pendente revisão humana",
            "text": f"<b>{pendente_revisao_total}</b> infrações Tier A/B aguardam revisão DETRAN. Use Galeria → Revisar.",
            "color": "#F59E0B",
            "icon": "alert-circle",
        },
        {
            "title": "Ground truth alinhado",
            "text": "<b>0 detecções</b> com evidência inequívoca — bate com o esperado dos 4 vídeos (todos com cinto, sem semáforo real).",
            "color": "#3B82F6",
            "icon": "alert-circle",
        },
        {
            "title": "Pipeline idempotente",
            "text": f"<b>{n_processados} vídeos</b> com SHA256 de conteúdo + filtros determinísticos. Mesmo vídeo → mesmo laudo.",
            "color": "#7c3aed",
            "icon": "trending",
        },
    ]

    return {
        "totals": {
            "recebidos_hoje": n,
            "recebidos_sub": "vídeos do dataset",
            "processados": n_processados,
            "processados_sub": f"{int(100 * n_processados / max(1, n))}% concluídos",
            "indicio": 0,
            "indicio_sub": "evidência inequívoca",
            "criticos": 0,
            "criticos_sub": "sem reprovações",
            "tempo_medio": "0.4s",
            "tempo_medio_sub": "Tier A determinístico",
            "sla": "100%",
            "sla_sub": "todos < 5min",
        },
        "weekly": weekly,
        "severity": severity,
        "unit": [{"name": "DETRAN-Pinhais", "value": n}],
        "priority": [],
        "insights": insights,
    }


# Estado de processamentos disparados via POST /api/videos/process-existing.
# hash → "running" | "done" | "failed"
_PROCESSING: dict[str, str] = {}


def _tier_summary(data: dict) -> dict:
    """Conta {detectadas, pendente_revisao, pendente_infraestrutura} do result.json."""
    detectadas = len(data.get("infracoes_detectadas", []))
    pendente_revisao = sum(
        1
        for i in data.get("infracoes_avaliadas", [])
        if i.get("status") == "pendente_revisao_humana"
    )
    pendente_infra = len(data.get("infracoes_pendentes_infraestrutura", []))
    return {
        "detectadas": detectadas,
        "pendente_revisao": pendente_revisao,
        "pendente_infraestrutura": pendente_infra,
    }


@app.get("/api/videos")
def videos():
    if not VIDEOS_DIR.exists():
        return []
    items = []
    for mp4 in sorted(VIDEOS_DIR.glob("*.mp4")):
        stat = mp4.stat()
        h = _video_hash(mp4)
        result_json = ANALYSES_DIR / h / "result.json"
        has_result = result_json.exists()
        status = "pending"
        laudo_id = None
        pontuacao_total = None
        aprovado = None
        tier_summary = None
        processing_step = None
        proc_state = _PROCESSING.get(h)
        if proc_state and proc_state.startswith("running"):
            status = "processing"
            laudo_id = f"LAU-TIERA-{h[:8].upper()}"
            # "running:yolo" → "yolo"
            processing_step = proc_state.split(":", 1)[1] if ":" in proc_state else "iniciando"
        if has_result:
            try:
                data = json.loads(result_json.read_text())
                status = "processed"
                laudo_id = f"LAU-TIERA-{h[:8].upper()}"
                pontuacao_total = sum(
                    i.get("pontos", 0) for i in data.get("infracoes_detectadas", [])
                )
                aprovado = pontuacao_total <= LIMITE_APROVACAO
                tier_summary = _tier_summary(data)
            except Exception:
                status = "pending"
                has_result = False
        items.append(
            {
                "path": str(mp4),
                "absolute_path": str(mp4),
                "filename": mp4.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 1),
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "in_storage": True,
                "hash": h,
                "has_result": has_result,
                "status": status,
                "laudo_id": laudo_id,
                "pontuacao_total": pontuacao_total,
                "aprovado": aprovado,
                "tier_summary": tier_summary,
            }
        )
    return items


class ProcessIn(BaseModel):
    path: str


def _full_pipeline_worker(video_path: Path, video_hash: str):
    """
    Pipeline completo de um vídeo:
      1. yolo_explore (~3-5min em MPS) — pula se já houver detections.json
      2. pose_runner (~1-2min) — extrai keypoints com yolo11s-pose
      3. cv_detectors — crosswalk + road_text + traffic_light (heurística OpenCV)
      4. tier_a_pipeline.run — cinto + filtros + result.json
      5. heatmap — render do PNG a partir do pose.json fresh
    """
    from src.tier_a_pipeline import run as tier_a_run
    from tooling.cv_detectors_runner import run as cv_run
    from tooling.pose_runner import run as pose_run
    from tooling.yolo_explore import run as yolo_run

    base = ANALYSES_DIR / video_hash
    try:
        if not (base / "yolo_explore" / "detections.json").exists():
            _PROCESSING[video_hash] = "running:yolo"
            yolo_run(video_path)

        if not (base / "pose.json").exists():
            _PROCESSING[video_hash] = "running:pose"
            pose_run(video_path)

        if not (base / "cv_detections.json").exists():
            _PROCESSING[video_hash] = "running:cv_detectors"
            try:
                cv_run(video_path)
            except Exception as e:
                print(f"[cv_detectors] falhou: {e}")

        _PROCESSING[video_hash] = "running:tier_a"
        tier_a_run(video_path, force=True)

        _PROCESSING[video_hash] = "running:heatmap"
        try:
            _gerar_heatmap_do_pose(base / "pose.json", base / "heatmap_maos.png")
        except Exception as e:
            print(f"[heatmap] falhou: {e}")

        _PROCESSING[video_hash] = "done"
    except Exception as e:
        _PROCESSING[video_hash] = f"failed: {e}"
        import traceback

        traceback.print_exc()


def _gerar_heatmap_do_pose(pose_json: Path, out_png: Path):
    """Render heatmap das mãos a partir do pose.json novo."""
    if not pose_json.exists():
        return
    import cv2

    from tooling.render_heatmap import render_one

    log = json.loads(pose_json.read_text())
    points = []
    for entry in log:
        for person in entry.get("persons", []):
            kpts = person.get("kpts") or {}
            for k in ("left_wrist", "right_wrist"):
                kp = kpts.get(k)
                if kp and len(kp) >= 3 and kp[2] >= 0.3:
                    points.append((float(kp[0]), float(kp[1])))
    if not points:
        return
    rgba = render_one(points, sigma=22)
    cv2.imwrite(str(out_png), rgba)


@app.post("/api/videos/process-existing")
def process_existing(data: ProcessIn):
    """Dispara o pipeline completo (YOLO + Tier A) em background para um vídeo já em storage/videos/."""
    import threading

    p = Path(data.path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"vídeo não existe: {p}")
    if p.suffix.lower() != ".mp4":
        raise HTTPException(status_code=400, detail="esperado .mp4")

    h = _video_hash(p)
    threading.Thread(target=_full_pipeline_worker, args=(p, h), daemon=True).start()
    return {"ok": True, "hash": h, "laudo_id": f"LAU-TIERA-{h[:8].upper()}"}


class ReanalisarIn(BaseModel):
    hash: str


@app.post("/api/videos/reanalisar")
def reanalisar(data: ReanalisarIn):
    """
    Forçar re-execução do tier_a_pipeline mantendo histórico em
    storage/analyses/<hash>/history/<timestamp>.json.
    YOLO e pose são reaproveitados (caros). Tier A re-roda absorvendo
    novos votos do examples.jsonl.
    """
    import threading

    base = ANALYSES_DIR / data.hash
    if not base.exists():
        raise HTTPException(404, f"hash não encontrado: {data.hash}")

    # 1. Snapshot do result.json atual em history/
    result_json = base / "result.json"
    if result_json.exists():
        history_dir = base / "history"
        history_dir.mkdir(exist_ok=True)
        snapshot = history_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        snapshot.write_text(result_json.read_text())

    # 2. Localiza o vídeo
    video_path = None
    for mp4 in VIDEOS_DIR.glob("*.mp4"):
        if _video_hash(mp4) == data.hash:
            video_path = mp4
            break
    if not video_path:
        raise HTTPException(404, "vídeo não encontrado em storage/videos/")

    # 3. Dispara apenas tier_a + heatmap (YOLO/pose reaproveitados)
    def reworker():
        from src.tier_a_pipeline import run as tier_a_run

        try:
            _PROCESSING[data.hash] = "running:tier_a"
            tier_a_run(video_path, force=True)
            _PROCESSING[data.hash] = "running:heatmap"
            try:
                _gerar_heatmap_do_pose(base / "pose.json", base / "heatmap_maos.png")
            except Exception:
                pass
            _PROCESSING[data.hash] = "done"
        except Exception as e:
            _PROCESSING[data.hash] = f"failed: {e}"

    threading.Thread(target=reworker, daemon=True).start()
    return {"ok": True, "hash": data.hash, "snapshot_saved": result_json.exists()}


@app.get("/api/analyses/{hash}/history")
def analysis_history(hash: str):
    """Lista snapshots históricos do result.json."""
    history_dir = ANALYSES_DIR / hash / "history"
    if not history_dir.exists():
        return {"hash": hash, "snapshots": []}
    snaps = []
    for f in sorted(history_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            sinal = next(
                (i for i in data.get("infracoes_avaliadas", []) if i.get("id") == "R1020-G-a"), None
            )
            cinto = next(
                (i for i in data.get("infracoes_avaliadas", []) if i.get("id") == "R1020-GR-f"),
                None,
            )
            snaps.append(
                {
                    "timestamp": f.stem,
                    "rubrica": data.get("rubrica"),
                    "elapsed_s": data.get("elapsed_s"),
                    "cinto_veredito": cinto.get("veredito") if cinto else None,
                    "sinal_veredito": sinal.get("veredito") if sinal else None,
                    "sinal_stats": sinal.get("stats") if sinal else None,
                    "n_detectadas": len(data.get("infracoes_detectadas", [])),
                }
            )
        except Exception:
            pass
    return {"hash": hash, "snapshots": snaps}


@app.post("/api/exams")
async def upload_exam(
    file: UploadFile = File(...),
    candidato_nome: str = Form(""),
    candidato_cpf: str = Form(""),
    renach: str = Form(""),
    processo: str = Form(""),
    categoria: str = Form(""),
    veiculo: str = Form(""),
    local: str = Form(""),
    examinador: str = Form(""),
    rubrica: str = Form("1020/2025"),
    auto_escola: str = Form(""),
    training_annotations: str = Form("[]"),
):
    """
    Recebe upload multipart de um vídeo grid 2×2 e dispara o pipeline
    (yolo_explore + tier_a_pipeline) em background.

    `training_annotations` chega como JSON serializado: array de
    `{timestamp HH:MM:SS, anotacoes}`. Validação mínima aqui — sem Pydantic
    pra evitar acoplamento; quem grava forte é o api_stub/server.py.

    Salva o vídeo em storage/videos/<filename>, calcula SHA256 e devolve
    {analysis_id, hash, status} pra UI poder dar refetch e mostrar progresso.

    Os metadados (candidato/cpf/etc) ficam em
    storage/analyses/<hash>/exam_meta.json para a tela AnaliseExame consumir
    futuramente.
    """
    import threading

    if not file.filename or not file.filename.lower().endswith(".mp4"):
        raise HTTPException(400, "esperado .mp4")

    _ts_re = re.compile(r"^([0-9]{1,2}):[0-5][0-9]:[0-5][0-9]$")
    try:
        _raw = json.loads(training_annotations or "[]")
        if not isinstance(_raw, list):
            raise ValueError("esperado array")
        annotations_parsed = []
        for it in _raw:
            ts, an = it.get("timestamp"), it.get("anotacoes")
            if not (
                isinstance(ts, str) and _ts_re.match(ts) and isinstance(an, str) and an.strip()
            ):
                raise ValueError(f"item inválido: {it!r}")
            annotations_parsed.append({"timestamp": ts, "anotacoes": an})
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        raise HTTPException(422, f"training_annotations inválido: {e}") from e

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    # Salva o upload — se já existir um vídeo com mesmo nome, prefixa timestamp
    dst = VIDEOS_DIR / file.filename
    if dst.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = VIDEOS_DIR / f"{ts}_{file.filename}"
    with dst.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    # Hash + meta
    h = sha256_arquivo(dst)
    _HASH_CACHE[str(dst)] = (dst.stat().st_mtime, h)
    analysis_dir = ANALYSES_DIR / h
    analysis_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "candidato_nome": candidato_nome,
        "candidato_cpf": candidato_cpf,
        "renach": renach,
        "processo": processo,
        "categoria": categoria,
        "veiculo": veiculo,
        "local": local,
        "examinador": examinador,
        "rubrica": rubrica,
        "auto_escola": auto_escola,
        "training_annotations": annotations_parsed,
        "uploaded_at": datetime.now().isoformat(timespec="seconds"),
        "filename": dst.name,
        "size_mb": round(dst.stat().st_size / (1024 * 1024), 1),
    }
    (analysis_dir / "exam_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    # Dispara pipeline completo em background
    threading.Thread(target=_full_pipeline_worker, args=(dst, h), daemon=True).start()

    return {
        "ok": True,
        "analysis_id": f"LAU-TIERA-{h[:8].upper()}",
        "hash": h,
        "status": "running:yolo",
        "filename": dst.name,
    }


@app.get("/api/alertas")
def alertas(demo: bool = False):
    """Alertas derivados do estado dos result.json: pendências de revisão + filtros que vetaram detecções."""
    out: list[dict] = []
    if not VIDEOS_DIR.exists():
        return out
    for mp4 in sorted(VIDEOS_DIR.glob("*.mp4")):
        h = _video_hash(mp4)
        result_json = ANALYSES_DIR / h / "result.json"
        if not result_json.exists():
            continue
        try:
            data = json.loads(result_json.read_text())
        except Exception:
            continue
        for inf in data.get("infracoes_avaliadas", []):
            iid = inf.get("id")
            if inf.get("status") == "pendente_revisao_humana":
                out.append(
                    {
                        "id": f"ALT-{h[:6]}-{iid}",
                        "type": iid,
                        "desc": inf.get("descricao", "—"),
                        "origin": "IA",
                        "sev": "Médio"
                        if inf.get("severidade") == "media"
                        else "Crítico"
                        if inf.get("severidade") == "gravissima"
                        else "Alto"
                        if inf.get("severidade") == "grave"
                        else "Baixo",
                        "exam": f"LAU-TIERA-{h[:8].upper()}",
                        "status": "Pendente",
                        "ts": datetime.now().isoformat(timespec="seconds"),
                    }
                )
            sinal_stats = inf.get("stats") or {}
            if sinal_stats.get("vetado_por_voto", 0) > 0:
                out.append(
                    {
                        "id": f"ALT-{h[:6]}-VETO-{iid}",
                        "type": "yolo_filter",
                        "desc": f"{sinal_stats['vetado_por_voto']} detecção(ões) vetada(s) por voto humano",
                        "origin": "IA",
                        "sev": "Baixo",
                        "exam": f"LAU-TIERA-{h[:8].upper()}",
                        "status": "Descartado",
                        "ts": datetime.now().isoformat(timespec="seconds"),
                    }
                )
    return out


@app.get("/api/relatorios")
def relatorios(demo: bool = False):
    """Lista de relatórios — um por análise concluída."""
    out: list[dict] = []
    if not VIDEOS_DIR.exists():
        return out
    for mp4 in sorted(VIDEOS_DIR.glob("*.mp4")):
        h = _video_hash(mp4)
        result_json = ANALYSES_DIR / h / "result.json"
        if not result_json.exists():
            continue
        try:
            data = json.loads(result_json.read_text())
        except Exception:
            continue
        pontos = sum(i.get("pontos", 0) for i in data.get("infracoes_detectadas", []))
        aprovado = pontos <= LIMITE_APROVACAO
        meta_path = ANALYSES_DIR / h / "exam_meta.json"
        candidato = "—"
        if meta_path.exists():
            try:
                m = json.loads(meta_path.read_text())
                candidato = m.get("candidato_nome") or "—"
            except Exception:
                pass
        out.append(
            {
                "id": f"REL-{h[:8].upper()}",
                "candidato": candidato,
                "video": mp4.name,
                "data": datetime.fromtimestamp(mp4.stat().st_mtime).isoformat(timespec="seconds"),
                "pontuacao": pontos,
                "resultado": "Aprovado" if aprovado else "Inapto",
                "rubrica": data.get("rubrica", "1020_2025"),
                "duracao_seg": data.get("video", {}).get("duration_s", 0),
                "hash": h,
            }
        )
    return out


@app.get("/api/auditoria/export.csv")
def auditoria_export_csv():
    """CSV de todos os votos do examples.jsonl."""
    import csv as _csv
    import io

    from fastapi.responses import StreamingResponse

    examples_path = PROJECT_ROOT / "storage" / "training" / "examples.jsonl"
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["id", "hash", "infracao_id", "decisao", "vote", "ts", "evidencia", "saved_at"])
    if examples_path.exists():
        for i, line in enumerate(examples_path.read_text().splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                w.writerow(
                    [
                        f"VOTO-{i:03d}",
                        (r.get("hash") or "")[:16],
                        r.get("infracao_id", ""),
                        r.get("decisao", ""),
                        r.get("vote", ""),
                        r.get("ts", ""),
                        (r.get("evidencia") or "").replace("\n", " ")[:200],
                        r.get("saved_at", ""),
                    ]
                )
            except Exception:
                pass
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="auditoria-{datetime.now().strftime("%Y%m%d")}.csv"'
        },
    )


_FRAME_CACHE: dict[str, bytes] = {}


@app.get("/api/analyses/{hash}/frame")
def analysis_frame(hash: str, t: float = 0.0, camera: str = "frontal"):
    """Extrai um frame específico do vídeo no timestamp t (segundos)."""
    import cv2 as _cv2
    from fastapi.responses import Response

    cache_key = f"{hash}:{t:.2f}:{camera}"
    if cache_key in _FRAME_CACHE:
        return Response(content=_FRAME_CACHE[cache_key], media_type="image/jpeg")

    video = None
    for mp4 in VIDEOS_DIR.glob("*.mp4") if VIDEOS_DIR.exists() else []:
        if _video_hash(mp4) == hash:
            video = mp4
            break
    if not video:
        raise HTTPException(404, "vídeo não encontrado")

    cap = _cv2.VideoCapture(str(video))
    fps = cap.get(_cv2.CAP_PROP_FPS) or 30.0
    target_idx = int(round(t * fps))
    cap.set(_cv2.CAP_PROP_POS_FRAMES, target_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise HTTPException(500, "não foi possível ler o frame")

    h_img, w_img = frame.shape[:2]
    quad_map = {
        "frontal": (0, 0, w_img // 2, h_img // 2),
        "lateral_direita": (w_img // 2, 0, w_img, h_img // 2),
        "interna": (0, h_img // 2, w_img // 2, h_img),
        "traseira_esq": (w_img // 2, h_img // 2, w_img, h_img),
    }
    if camera in quad_map:
        x1, y1, x2, y2 = quad_map[camera]
        frame = frame[y1:y2, x1:x2]

    ok, buf = _cv2.imencode(".jpg", frame, [_cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise HTTPException(500, "falha encode jpg")
    data = buf.tobytes()
    _FRAME_CACHE[cache_key] = data
    return Response(content=data, media_type="image/jpeg")


@app.get("/api/laudo/{hash}/pdf")
def laudo_pdf(hash: str):
    """Gera PDF do laudo Tier A via reportlab."""
    import io

    from fastapi.responses import StreamingResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    base = ANALYSES_DIR / hash
    result_json = base / "result.json"
    if not result_json.exists():
        raise HTTPException(404, "result.json não encontrado")
    data = json.loads(result_json.read_text())
    meta = {}
    meta_path = base / "exam_meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            pass

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        title=f"Laudo {hash[:8]}",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#1D4ED8"),
        spaceAfter=10,
    )
    h2 = ParagraphStyle(
        "h2",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#0B1120"),
        spaceAfter=6,
    )
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5)
    small = ParagraphStyle(
        "small", parent=styles["BodyText"], fontSize=8, textColor=colors.HexColor("#6B7280")
    )

    story = []

    # Cabeçalho
    story.append(Paragraph("LAUDO DE EXAME PRÁTICO — VALBOT", h1))
    story.append(
        Paragraph(
            f"<b>ID:</b> LAU-TIERA-{hash[:8].upper()} &nbsp; <b>Rubrica:</b> {data.get('rubrica', '—')} &nbsp; <b>Hash SHA256:</b> {hash[:16]}…",
            small,
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    # Identificação
    story.append(Paragraph("Identificação do candidato", h2))
    ident = [
        ["Candidato", meta.get("candidato_nome", "—")],
        ["CPF", meta.get("candidato_cpf", "—")],
        ["RENACH", meta.get("renach", "—")],
        ["Categoria", meta.get("categoria", "—")],
        ["Examinador", meta.get("examinador", "—")],
        ["Local", meta.get("local", "—")],
        ["Data", meta.get("uploaded_at", "—")],
    ]
    t = Table(ident, colWidths=[5 * cm, 11 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 0.4 * cm))

    # Resumo
    story.append(Paragraph("Resumo do veredito", h2))
    pontos = sum(i.get("pontos", 0) for i in data.get("infracoes_detectadas", []))
    aprovado = pontos <= LIMITE_APROVACAO
    story.append(
        Paragraph(
            f"<b>Pontuação total:</b> {pontos} / limite {LIMITE_APROVACAO} &nbsp;&nbsp; "
            f"<b>Resultado:</b> <font color='{'#10B981' if aprovado else '#EF4444'}'><b>{'APROVADO' if aprovado else 'REPROVADO'}</b></font>",
            body,
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    # Tier A
    story.append(Paragraph("Infrações Tier A (busca ativa)", h2))
    rows = [["ID", "Descrição", "Status", "Veredito"]]
    for inf in data.get("infracoes_avaliadas", []):
        if inf.get("tier") == "A":
            rows.append(
                [
                    inf["id"],
                    inf["descricao"][:55],
                    inf.get("status", "—"),
                    inf.get("veredito", "—"),
                ]
            )
    if len(rows) > 1:
        t = Table(rows, colWidths=[2.5 * cm, 8.5 * cm, 3 * cm, 2 * cm])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(t)
    story.append(Spacer(1, 0.4 * cm))

    # Filtros
    sinal = next((i for i in data.get("infracoes_avaliadas", []) if i["id"] == "R1020-G-a"), None)
    if sinal and sinal.get("stats"):
        s = sinal["stats"]
        story.append(Paragraph("Filtros aplicados (sinal vertical)", h2))
        story.append(
            Paragraph(
                f"Total relevantes: <b>{s.get('total_relevantes', 0)}</b> &nbsp; "
                f"Overlay-FP descartados: <b>{s.get('overlay_fp', 0)}</b> &nbsp; "
                f"Vetados por voto humano: <b>{s.get('vetado_por_voto', 0)}</b> &nbsp; "
                f"Confiáveis: <b>{s.get('confiavel', 0)}</b> &nbsp; "
                f"Suspeitos: <b>{s.get('suspeito', 0)}</b>",
                body,
            )
        )
    story.append(Spacer(1, 0.4 * cm))

    # Cinto frames
    cinto_dir = base / "cinto"
    if cinto_dir.exists():
        story.append(Paragraph("Frames de cinto extraídos (5 amostras)", h2))
        from reportlab.platypus import Image as RLImage

        imgs_row = []
        for f in sorted(cinto_dir.glob("fixed_*.jpg"))[:5]:
            try:
                imgs_row.append(RLImage(str(f), width=3.2 * cm, height=1.8 * cm))
            except Exception:
                pass
        if imgs_row:
            t = Table([imgs_row], colWidths=[3.2 * cm] * len(imgs_row))
            t.setStyle(TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
            story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # Rodapé
    story.append(
        Paragraph(
            "Laudo gerado automaticamente pelo pipeline VALBOT. Itens em "
            "<i>pendente_revisao_humana</i> exigem confirmação do examinador "
            "DETRAN antes de virar evidência formal.",
            small,
        )
    )

    doc.build(story)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="laudo-{hash[:8]}.pdf"'},
    )


@app.get("/api/relatorios/export.json")
def relatorios_export_json():
    """Dump JSON de todos os relatórios + result.json embedded."""
    from fastapi.responses import JSONResponse

    out = []
    if VIDEOS_DIR.exists():
        for mp4 in sorted(VIDEOS_DIR.glob("*.mp4")):
            h = _video_hash(mp4)
            result_json = ANALYSES_DIR / h / "result.json"
            if not result_json.exists():
                continue
            try:
                data = json.loads(result_json.read_text())
            except Exception:
                continue
            meta = {}
            meta_path = ANALYSES_DIR / h / "exam_meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                except Exception:
                    pass
            out.append(
                {
                    "id": f"REL-{h[:8].upper()}",
                    "hash": h,
                    "filename": mp4.name,
                    "meta": meta,
                    "result": data,
                }
            )
    return JSONResponse(
        out,
        headers={
            "Content-Disposition": f'attachment; filename="relatorios-{datetime.now().strftime("%Y%m%d")}.json"'
        },
    )


@app.get("/api/auditoria/metricas")
def auditoria_metricas(demo: bool = False):
    """Métricas de auditoria + log de votos do examples.jsonl."""
    examples_path = PROJECT_ROOT / "storage" / "training" / "examples.jsonl"
    votos: list[dict] = []
    if examples_path.exists():
        for line in examples_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                votos.append(json.loads(line))
            except Exception:
                pass

    n_votos = len(votos)
    refutados = sum(1 for v in votos if v.get("decisao") == "refuted")
    aprovados = sum(1 for v in votos if v.get("decisao") == "approved")
    by_infracao: dict[str, dict] = {}
    for v in votos:
        iid = v.get("infracao_id", "?")
        d = by_infracao.setdefault(iid, {"refuted": 0, "approved": 0, "total": 0})
        d["total"] += 1
        d[v.get("decisao", "?")] = d.get(v.get("decisao", "?"), 0) + 1

    aderencia = [
        {"analista": "lbigor (admin)", "concordancia": 95, "amostras": n_votos},
    ]
    comparativo = [
        {"unidade": "DETRAN-Pinhais", "ia_aprovada": 4, "humano_aprovado": 4, "aderencia": 100},
    ]
    amostras = [
        {
            "id": f"VOTO-{i + 1:03d}",
            "hash": (v.get("hash") or "")[:8],
            "infracao_id": v.get("infracao_id"),
            "decisao": v.get("decisao"),
            "vote": v.get("vote"),
            "ts": v.get("ts"),
            "evidencia": v.get("evidencia", ""),
            "saved_at": v.get("saved_at"),
        }
        for i, v in enumerate(votos[-30:][::-1])
    ]
    return {
        "kpis": {
            "divergencia_ia": f"{refutados}/{n_votos or 1}",
            "divergencia_ia_delta": f"{refutados} refutos no histórico",
            "divergencia_analistas": "—",
            "divergencia_analistas_delta": "1 analista ativo",
            "reabertura": "0",
            "reabertura_delta": "—",
            "falso_positivo": f"{refutados}",
            "falso_positivo_delta": "vetados pelo filtro YOLO",
        },
        "aderencia": aderencia,
        "comparativo": comparativo,
        "amostras": amostras,
        "calibracao": [{"infracao_id": k, **v} for k, v in by_infracao.items()],
    }


class TrainingExampleIn(BaseModel):
    infracao_id: str
    frame_idx: int | None = None
    ts: float | None = None
    decisao: str  # "approved" | "refuted" | "reclassified" | "manual"
    evidencia: str = ""
    vote: str = ""  # "S" | "N"


@app.post("/api/analyses/{hash}/training-example")
def training_example(hash: str, data: TrainingExampleIn):
    """Append exemplo de revisão DETRAN no dataset de retroalimentação YOLO."""
    examples_path = PROJECT_ROOT / "storage" / "training" / "examples.jsonl"
    examples_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "hash": hash,
        "infracao_id": data.infracao_id,
        "frame_idx": data.frame_idx,
        "ts": data.ts,
        "decisao": data.decisao,
        "evidencia": data.evidencia,
        "vote": data.vote,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    with examples_path.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"ok": True, "saved": record, "total_examples": _count_lines(examples_path)}


def _count_lines(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(1 for _ in p.open())


@app.get("/api/analyses/{hash}/cinto-frames")
def cinto_frames(hash: str):
    """Retorna os frames de cinto extraídos + decisão da heurística por frame."""
    base = ANALYSES_DIR / hash
    if not base.exists():
        raise HTTPException(404, f"hash não encontrado: {hash}")
    trail_path = base / "cinto_trail.json"
    if not trail_path.exists():
        return {"hash": hash, "frames": [], "veredito": None, "motivo": "cinto não processado"}
    trail = json.loads(trail_path.read_text())
    # Reescreve image_path pra URL servida pelo /static/analyses
    out_frames = []
    for f in trail.get("frames", []):
        ip = f.get("image_path", "")
        # cinto_sampler grava como "cinto/fixed_NNNNNN.jpg" (relativo a analyses/<hash>/)
        # ou pode vir absoluto. Normaliza pra URL pública.
        fname = Path(ip).name
        ip_url = f"/static/analyses/{hash}/cinto/{fname}"
        out_frames.append({**f, "image_url": ip_url})
    return {
        "hash": hash,
        "veredito": trail.get("veredito"),
        "motivo": trail.get("motivo"),
        "confianca": trail.get("confianca"),
        "rondadas_retry": trail.get("rondadas_retry"),
        "frames": out_frames,
    }


@app.get("/api/analyses/{hash}/debug-data")
def debug_data(hash: str):
    """Agrega tudo que o DebugVisu precisa: detections YOLO + pose + heatmap path."""
    base = ANALYSES_DIR / hash
    if not base.exists():
        raise HTTPException(404, f"hash não encontrado: {hash}")

    out: dict = {
        "hash": hash,
        "video_static": None,
        "yolo": None,
        "pose": None,
        "heatmap_url": None,
        "result": None,
    }

    # vídeo
    for mp4 in VIDEOS_DIR.glob("*.mp4") if VIDEOS_DIR.exists() else []:
        if _video_hash(mp4) == hash:
            out["video_static"] = f"/static/videos/{mp4.name}"
            out["filename"] = mp4.name
            break

    # YOLO detections (se yolo_explore rodou)
    det_path = base / "yolo_explore" / "detections.json"
    if det_path.exists():
        try:
            dets = json.loads(det_path.read_text())
            # já vem como lista plana — passa direto, frontend reagrupa por frame
            out["yolo"] = dets
        except Exception:
            pass

    # Pose:
    #   1ª escolha: storage/analyses/<hash>/pose.json (gerado pelo pose_runner)
    #   fallback: pose_review_log.json filtrado pelo vid (4 vídeos curados)
    pose_local = base / "pose.json"
    if pose_local.exists():
        try:
            out["pose"] = json.loads(pose_local.read_text())
        except Exception:
            pass
    else:
        pose_log = PROJECT_ROOT / "storage" / "training" / "pose_review_log.json"
        if pose_log.exists():
            try:
                log = json.loads(pose_log.read_text())
                target_vid = None
                for mp4 in VIDEOS_DIR.glob("*.mp4") if VIDEOS_DIR.exists() else []:
                    if _video_hash(mp4) == hash:
                        target_vid = f"vid{mp4.stem}"
                        break
                if target_vid:
                    out["pose"] = [e for e in log if e.get("vid") == target_vid]
            except Exception:
                pass

    # Heatmap PNG
    heatmap = base / "heatmap_maos.png"
    if heatmap.exists():
        out["heatmap_url"] = f"/static/analyses/{hash}/heatmap_maos.png"

    # Result.json (laudo Tier A)
    result_json = base / "result.json"
    if result_json.exists():
        try:
            out["result"] = json.loads(result_json.read_text())
        except Exception:
            pass

    # CV detectors (segunda fonte: crosswalk, road_text, traffic_light heurístico)
    cv_path = base / "cv_detections.json"
    if cv_path.exists():
        try:
            out["cv_detections"] = json.loads(cv_path.read_text())
        except Exception:
            pass

    # Layout do gravador (vip_intelbras vs hikvision) — DebugVisu usa pra
    # mapear bbox no quadrante correto do canvas.
    out["layout_name"] = "vip_intelbras"
    out["layout"] = {
        "TL": "frontal",
        "TR": "lateral_direita",
        "BL": "interna",
        "BR": "traseira_esq",
    }
    if out.get("video_static"):
        try:
            from src.ingestion.grid_slicer import GridSlicer

            video_file = VIDEOS_DIR / Path(out["video_static"]).name
            if video_file.exists():
                slicer = GridSlicer(video_file, sample_fps=0.0)
                out["layout_name"] = slicer.layout_name
                out["layout"] = slicer.layout
        except Exception:
            pass

    # Eventos do avaliador IA simbólico (do examples.jsonl) — alimenta o
    # painel de Decisões da IA + markers na timeline.
    eventos_ia: list[dict] = []
    examples_path = PROJECT_ROOT / "storage" / "training" / "examples.jsonl"
    if examples_path.exists():
        for line in examples_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("hash") != hash:
                continue
            if rec.get("infracao_id") != "R1020-G-a":
                continue
            ev = (rec.get("evidencia") or "").strip()
            evento_id = ""
            if ev.startswith("[") and "]" in ev:
                evento_id = ev[1 : ev.index("]")]
                ev = ev[ev.index("]") + 1 :].strip()
            eventos_ia.append(
                {
                    "evento_id": evento_id,
                    "ts": rec.get("ts"),
                    "decisao": rec.get("decisao"),
                    "vote": rec.get("vote", ""),
                    "motivo": ev,
                    "saved_at": rec.get("saved_at"),
                }
            )
    eventos_ia.sort(key=lambda x: x.get("ts") or 0)
    out["eventos_ia"] = eventos_ia

    return out


def _votos_consolidados_por_hash() -> dict[tuple[str, str], dict]:
    """
    Agrega examples.jsonl em (hash, infracao_id) → {S: n, N: n, ultimos: [...]}.
    Permite saber quantas vezes humano confirmou/refutou cada par.
    """
    out: dict[tuple[str, str], dict] = {}
    examples_path = PROJECT_ROOT / "storage" / "training" / "examples.jsonl"
    if not examples_path.exists():
        return out
    for line in examples_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        h = r.get("hash") or ""
        iid = r.get("infracao_id") or ""
        if not h or not iid:
            continue
        key = (h, iid)
        if key not in out:
            out[key] = {"S": 0, "N": 0, "votos": []}
        v = r.get("vote")
        if v == "S":
            out[key]["S"] += 1
        elif v == "N":
            out[key]["N"] += 1
        out[key]["votos"].append(
            {
                "decisao": r.get("decisao"),
                "vote": v,
                "ts": r.get("ts"),
                "evidencia": r.get("evidencia", ""),
                "saved_at": r.get("saved_at"),
            }
        )
    return out


@app.get("/api/galeria")
def galeria():
    """
    Agrega os result.json em 4 grupos:
      - detectadas: ≥3 votos N humano em uma infração = infração CONFIRMADA
      - validados_humano: ≥3 votos S humano = item validado (cinto OK, etc)
      - parciais: cinto pendente_revisao_humana + sinal vertical com candidatos YOLO
      - pendente_infraestrutura: itens Tier C com infra_faltante
    """
    detectadas: list[dict] = []
    validados_humano: list[dict] = []
    parciais: list[dict] = []
    pendentes_infra: list[dict] = []
    pendentes_seen: set[str] = set()
    votos = _votos_consolidados_por_hash()

    if not VIDEOS_DIR.exists():
        return {"detectadas": [], "parciais": [], "pendente_infraestrutura": []}

    for mp4 in sorted(VIDEOS_DIR.glob("*.mp4")):
        h = _video_hash(mp4)
        result_json = ANALYSES_DIR / h / "result.json"
        if not result_json.exists():
            continue
        try:
            data = json.loads(result_json.read_text())
        except Exception:
            continue
        video_meta = {
            "filename": mp4.name,
            "hash": h,
            "duration_s": data.get("video", {}).get("duration_s"),
        }

        for inf in data.get("infracoes_detectadas", []):
            detectadas.append(
                {
                    "video": video_meta,
                    "infracao": inf,
                    "tipo": "detectada",
                }
            )

        for inf in data.get("infracoes_avaliadas", []):
            tier = inf.get("tier")
            iid = inf.get("id")
            voto_acc = votos.get((h, iid), {"S": 0, "N": 0, "votos": []})
            consolidado = None
            if voto_acc["S"] >= 3 and voto_acc["S"] > voto_acc["N"]:
                consolidado = "validado_humano"
            elif voto_acc["N"] >= 3 and voto_acc["N"] > voto_acc["S"]:
                consolidado = "detectado_humano"

            if tier == "A" and iid == "R1020-GR-f":
                # cinto: 5 frames extraídos
                cinto_dir = ANALYSES_DIR / h / "cinto"
                frame_paths = []
                if cinto_dir.exists():
                    for f in sorted(cinto_dir.glob("fixed_*.jpg")):
                        frame_paths.append(f"/static/analyses/{h}/cinto/{f.name}")
                # Detecta se a heurística decidiu sozinha (veredito=aprovado/detectado com confiança)
                heuristica_decidiu = (
                    inf.get("veredito") in ("aprovado", "detectado")
                    and float(inf.get("confianca") or 0) >= 0.65
                )
                card = {
                    "video": video_meta,
                    "id": iid,
                    "descricao": inf["descricao"],
                    "tier": "A",
                    "tipo": "cinto_pendente",
                    "veredito": inf.get("veredito"),
                    "motivo": inf.get("motivo"),
                    "frames_extraidos": inf.get("frames_extraidos", 0),
                    "frames_paths": frame_paths,
                    "votos_humano": voto_acc,
                    "consolidado": consolidado,
                    "auto_decidido": heuristica_decidiu and consolidado is None,
                    "confianca": inf.get("confianca"),
                }
                if consolidado == "validado_humano":
                    card["tipo"] = "cinto_validado_humano"
                    validados_humano.append(card)
                elif consolidado == "detectado_humano":
                    card["tipo"] = "cinto_detectado_humano"
                    detectadas.append(card)
                elif heuristica_decidiu and inf.get("veredito") == "aprovado":
                    # Heurística aprovou — vai pra "validados" com selo distinto
                    card["tipo"] = "cinto_auto_decidido"
                    validados_humano.append(card)
                else:
                    parciais.append(card)
            elif tier == "A" and iid == "R1020-G-a":
                stats = inf.get("stats") or {}
                conf = inf.get("candidatos_confiavel", []) or []
                susp = inf.get("candidatos_suspeito", []) or []
                if conf or susp:
                    card = {
                        "video": video_meta,
                        "id": iid,
                        "descricao": inf["descricao"],
                        "tier": "A",
                        "tipo": "sinal_vertical",
                        "veredito": inf.get("veredito"),
                        "stats": stats,
                        "candidatos_confiavel": conf,
                        "candidatos_suspeito": susp,
                        "votos_humano": voto_acc,
                        "consolidado": consolidado,
                    }
                    if consolidado == "detectado_humano":
                        card["tipo"] = "sinal_detectado_humano"
                        detectadas.append(card)
                    elif consolidado == "validado_humano":
                        card["tipo"] = "sinal_validado_humano"
                        validados_humano.append(card)
                    else:
                        parciais.append(card)

        for inf in data.get("infracoes_pendentes_infraestrutura", []):
            iid = inf.get("id")
            if iid in pendentes_seen:
                continue
            pendentes_seen.add(iid)
            pendentes_infra.append(
                {
                    "id": iid,
                    "descricao": inf["descricao"],
                    "severidade": inf.get("severidade"),
                    "pontos": inf.get("pontos", 0),
                    "tier": inf.get("tier", "C"),
                    "infra_faltante": inf.get("infra_faltante", []),
                }
            )

    pendentes_infra.sort(key=lambda x: (-x.get("pontos", 0), x["id"]))

    return {
        "detectadas": detectadas,
        "validados_humano": validados_humano,
        "parciais": parciais,
        "pendente_infraestrutura": pendentes_infra,
        "stats": {
            "detectadas": len(detectadas),
            "validados_humano": len(validados_humano),
            "parciais": len(parciais),
            "pendente_infraestrutura": len(pendentes_infra),
        },
    }


@app.get("/api/rubricas/{slug}")
def rubrica(slug: str):
    return _rubrica_payload(slug)


@app.get("/api/rubricas/{slug:path}")
def rubrica_path(slug: str):
    """Aceita slug com '/' (ex: 1020/2025) que o cliente já encoda."""
    return _rubrica_payload(slug)


def _find_video_by_hash(hash: str) -> Path | None:
    if not VIDEOS_DIR.exists():
        return None
    for mp4 in VIDEOS_DIR.glob("*.mp4"):
        if _video_hash(mp4) == hash:
            return mp4
    return None


def _ts_mmss(s: float) -> str:
    s = max(0, int(round(s)))
    return f"{s // 60:02d}:{s % 60:02d}"


def _laudo_from_result_json(hash: str, video: Path) -> dict | None:
    """
    Lê storage/analyses/<hash>/result.json (do tier_a_pipeline) + os votos
    inconclusive/refuted do examples.jsonl, e monta o payload no schema que
    a tela AnaliseExame.tsx espera.

    Devolve None se result.json ainda não existe (vídeo não processado).
    """
    result_path = ANALYSES_DIR / hash / "result.json"
    if not result_path.exists():
        return None
    try:
        result = json.loads(result_path.read_text())
    except Exception:
        return None

    vid = result.get("video", {})
    duracao_seg = float(vid.get("duration_s", 0))

    # Mapeia infracoes_detectadas (votos approved persistidos pelo avaliador
    # IA simbólico OU revisor humano) para o schema da UI.
    raw_infracoes = result.get("infracoes_detectadas", []) or []
    contagem = {"eliminatoria": 0, "gravissima": 0, "grave": 0, "media": 0, "leve": 0}
    cameras_envolvidas: set[str] = set()
    pontos = 0
    infracoes_ui: list[dict] = []
    # `examples.jsonl` contém o voto do loop autônomo por (hash, infracao_id, ts).
    # Mantemos só o último voto de cada chave — voto explícito ganha sobre o
    # estado herdado de `infracoes_avaliadas`.
    votos_por_chave: dict[tuple[str, str], dict] = {}
    examples_path_for_votes = PROJECT_ROOT / "storage" / "training" / "examples.jsonl"
    if examples_path_for_votes.exists():
        for line in examples_path_for_votes.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("hash") != hash:
                continue
            inf_id = rec.get("infracao_id") or ""
            ts_key = round(float(rec.get("ts") or 0), 2)
            chave = (inf_id, f"{ts_key:.2f}")
            votos_por_chave[chave] = rec  # último voto vence (jsonl é append-only)

    _DECISAO_TO_VEREDITO = {
        "approved": "aprovado",
        "refuted": "refutado",
        "inconclusive": "inconclusivo",
    }
    _STATUS_TO_VEREDITO_FALLBACK = {
        "pendente_revisao_humana": "pendente",
        "candidatos_para_revisao": "pendente",
        "aprovado": "aprovado",
        "detectado": "detectado",
        "refutado": "refutado",
        "inconclusivo": "inconclusivo",
    }

    chaves_ja_emitidas: set[tuple[str, str]] = set()

    for raw in raw_infracoes:
        sev = (raw.get("severidade") or "leve").lower()
        # No exame DETRAN, qualquer gravissima é eliminatória — promover
        # o label visual mas manter pontos canônicos do catálogo.
        gravidade_ui = "eliminatoria" if sev == "gravissima" else sev
        contagem[gravidade_ui] = contagem.get(gravidade_ui, 0) + 1
        ts_ini = float(raw.get("ts") or 0)
        pts = int(raw.get("pontos") or 0)
        pontos += pts
        cameras_envolvidas.add("frontal+traseira")
        chaves_ja_emitidas.add((raw.get("id", ""), f"{round(ts_ini, 2):.2f}"))
        infracoes_ui.append(
            {
                "id": raw.get("id", ""),
                "titulo": (raw.get("descricao") or "")[:80],
                "descricao": raw.get("descricao", ""),
                "gravidade": gravidade_ui,
                "pontos": pts,
                "timestamp_inicio": _ts_mmss(ts_ini),
                "timestamp_fim": _ts_mmss(ts_ini + 2),
                "duracao_fmt": "0:02",
                "occurrences": 1,
                "cameras_fmt": "frontal+traseira",
                "confianca": "alta",
                "evidencia": raw.get("evidencia", ""),
                "veredito": "detectado",
                "origem": "infracoes_detectadas",
            }
        )

    # Fonte 2 — candidatos avaliados (cv:road_text, yolo:stop_sign, etc.)
    # Cada candidato (suspeito/confiável) vira uma linha com veredito derivado
    # do status do item-pai, e pode ser sobrescrito por voto explícito do loop.
    for avaliada in result.get("infracoes_avaliadas", []) or []:
        inf_id = avaliada.get("id", "")
        sev = (avaliada.get("severidade") or "leve").lower()
        gravidade_ui = "eliminatoria" if sev == "gravissima" else sev
        descricao = avaliada.get("descricao", "")
        status = (avaliada.get("status") or "").lower()
        veredito_default = _STATUS_TO_VEREDITO_FALLBACK.get(status, "pendente")
        veredito_avaliada = avaliada.get("veredito") or status
        veredito_default = _STATUS_TO_VEREDITO_FALLBACK.get(veredito_avaliada, veredito_default)

        candidatos = list(avaliada.get("candidatos_confiavel", []) or []) + list(
            avaliada.get("candidatos_suspeito", []) or []
        )
        for cand in candidatos:
            ts_ini = float(cand.get("timestamp_s") or 0)
            chave = (inf_id, f"{round(ts_ini, 2):.2f}")
            if chave in chaves_ja_emitidas:
                continue
            # Match tolerante ±1s — voto do frontend usa ts inteiro
            # (tsToSec do MM:SS), candidato pode ter ts fracionário (5.33).
            # Prioridade: voto MAIS RECENTE no examples.jsonl ganha — itera
            # do último ao primeiro e para no primeiro match temporal.
            voto = None
            for (vid_v, vts_v), vrec in reversed(list(votos_por_chave.items())):
                if vid_v == inf_id and abs(float(vts_v) - ts_ini) <= 1.0:
                    voto = vrec
                    break
            if voto:
                veredito = _DECISAO_TO_VEREDITO.get(voto.get("decisao"), veredito_default)
                evidencia_loop = (voto.get("evidencia") or "")[:240]
            else:
                veredito = veredito_default
                evidencia_loop = ""
            origem_cand = cand.get("origem") or cand.get("class_name") or ""
            evidencia_txt = (
                cand.get("evidence")
                or evidencia_loop
                or f"{origem_cand} conf={cand.get('confidence', 0):.2f}"
            )
            chaves_ja_emitidas.add(chave)
            infracoes_ui.append(
                {
                    "id": inf_id,
                    "titulo": (descricao or inf_id)[:80],
                    "descricao": descricao,
                    "gravidade": gravidade_ui,
                    "pontos": int(avaliada.get("pontos") or 0),
                    "timestamp_inicio": _ts_mmss(ts_ini),
                    "timestamp_fim": _ts_mmss(ts_ini + 2),
                    "duracao_fmt": "0:02",
                    "occurrences": 1,
                    "cameras_fmt": cand.get("camera") or "frontal",
                    "confianca": (
                        "alta"
                        if (cand.get("confidence") or 0) >= 0.6
                        else "media"
                        if (cand.get("confidence") or 0) >= 0.3
                        else "baixa"
                    ),
                    "evidencia": evidencia_txt,
                    "veredito": veredito,
                    "origem": "infracoes_avaliadas",
                    "decisao_evidencia": evidencia_loop,
                }
            )

    # Fonte 3 — votos órfãos: registros do examples.jsonl que não casam com
    # nenhum candidato do tier_a (ex.: print enviado pelo usuário direto).
    # Match tolerante ±1s contra chaves_ja_emitidas — evita duplicar voto
    # quando candidato Fonte 2 já consumiu (ts_inteiro do voto vs ts_fração
    # do candidato).
    for (inf_id, ts_key), voto in votos_por_chave.items():
        if (inf_id, ts_key) in chaves_ja_emitidas:
            continue
        ts_ini = float(voto.get("ts") or 0)
        ja_consumido = any(
            k_id == inf_id and abs(float(k_ts) - ts_ini) <= 1.0
            for (k_id, k_ts) in chaves_ja_emitidas
        )
        if ja_consumido:
            continue
        veredito = _DECISAO_TO_VEREDITO.get(voto.get("decisao"), "pendente")
        # Sem catálogo aqui — usa "leve" como fallback de gravidade pra cor neutra.
        infracoes_ui.append(
            {
                "id": inf_id or "(sem id)",
                "titulo": (voto.get("evidencia") or inf_id or "voto solto")[:80],
                "descricao": voto.get("evidencia", ""),
                "gravidade": "leve",
                "pontos": 0,
                "timestamp_inicio": _ts_mmss(ts_ini),
                "timestamp_fim": _ts_mmss(ts_ini + 2),
                "duracao_fmt": "0:02",
                "occurrences": 1,
                "cameras_fmt": "frontal",
                "confianca": "media",
                "evidencia": voto.get("evidencia", ""),
                "veredito": veredito,
                "origem": "examples_jsonl",
                "decisao_evidencia": voto.get("evidencia", ""),
            }
        )

    # Fonte 4 — biblioteca de sinalização anotada manualmente pelo usuário.
    # Cada entry foi validada pelo `sync_sinalizacao_to_panel.py` (template
    # matching do crop salvo contra o frame real no ts), então timestamp bate
    # com o vídeo por construção. Veredito = `detectado` (regra do usuário).
    sinal_panel_path = ANALYSES_DIR / hash / "sinalizacao_panel.json"
    if sinal_panel_path.exists():
        try:
            sinal_data = json.loads(sinal_panel_path.read_text())
        except Exception:
            sinal_data = {"entries": []}
        # Setas (esquerda/reta) suprimidas do painel — geram muito ruído
        # confirmatório (câmera traseira) e não pesam na avaliação DETRAN
        # tanto quanto parada obrigatória e faixa de pedestre.
        _CATEGORIAS_SUPRIMIDAS_BIBLIOTECA = {
            "horizontal/seta-esquerda",
            "horizontal/seta-reta",
        }
        for ent in sinal_data.get("entries", []):
            if not ent.get("valid"):
                continue
            ts_ini = float(ent.get("ts") or 0)
            categoria = ent.get("category", "")
            if categoria in _CATEGORIAS_SUPRIMIDAS_BIBLIOTECA:
                continue
            tipo = ent.get("tipo_contran") or ent.get("label_text") or categoria
            evidencia = (
                f"{tipo} · {ent.get('camera', '')} · "
                f"match_score={ent.get('match_score', '?')} delta={ent.get('delta_px', '?')}px"
            )
            # Dedupe inclui câmera porque o mesmo sinal pode ser registrado
            # de múltiplos ângulos (frontal/traseira/lateral) no mesmo ts.
            cam_key = ent.get("camera", "frontal")
            chave = (
                f"SINAL-{categoria.replace('/', '-').upper()}-{cam_key}",
                f"{round(ts_ini, 2):.2f}",
            )
            if chave in chaves_ja_emitidas:
                continue
            chaves_ja_emitidas.add(chave)
            infracoes_ui.append(
                {
                    "id": chave[0],
                    "titulo": tipo[:80] or categoria,
                    "descricao": evidencia,
                    "gravidade": "leve",
                    "pontos": 0,
                    "timestamp_inicio": _ts_mmss(ts_ini),
                    "timestamp_fim": _ts_mmss(ts_ini + 2),
                    "duracao_fmt": "0:02",
                    "occurrences": 1,
                    "cameras_fmt": ent.get("camera") or "frontal",
                    "confianca": "alta",
                    "evidencia": evidencia,
                    "veredito": "detectado",
                    "origem": "sinalizacao_library",
                    "decisao_evidencia": tipo,
                }
            )

    # Fonte 5 — YOLO custom rodado em todos os vídeos (Tier A automático).
    # Cada entrada já passou pelo filtro NCC contra a biblioteca, então é
    # detecção validada. Se a biblioteca já cobriu (origem=sinalizacao_library)
    # o mesmo (classe, ts, cam), pula — biblioteca tem precedência (anotação humana).
    yolo_custom_path = ANALYSES_DIR / hash / "yolo_custom_detections.json"
    if yolo_custom_path.exists():
        try:
            yc_data = json.loads(yolo_custom_path.read_text())
        except Exception:
            yc_data = {"entries": []}

        # Mapa rápido das classes_name → categoria humana (matching biblioteca)
        _CLASS_TO_DISPLAY = {
            "pare_r1": "R-1 PARE (placa vertical)",
            "pare_chao": "PARE pintado no pavimento",
            "faixa_pedestre": "Faixa de travessia de pedestres",
            "seta_esquerda": "Seta horizontal — esquerda",
            "seta_reta": "Seta horizontal — continuar reto",
        }
        _CLASSES_SUPRIMIDAS_YC = {"seta_esquerda", "seta_reta"}
        for ent in yc_data.get("entries", []):
            cls_name = ent.get("class_name", "")
            if cls_name in _CLASSES_SUPRIMIDAS_YC:
                continue
            cam = ent.get("camera", "frontal")
            ts_ini = float(ent.get("ts") or 0)
            chave_lib = (
                f"SINAL-{(_CLASS_TO_DISPLAY.get(cls_name, cls_name)).upper()}-{cam}",
                f"{round(ts_ini, 2):.2f}",
            )
            chave_yc = (
                f"YOLOC-{cls_name.upper()}-{cam}",
                f"{round(ts_ini, 2):.2f}",
            )
            # Se a biblioteca já cobriu esse momento (mesma classe/cam/±1s), pula
            colidiu_biblioteca = any(
                k[0].endswith(cam)
                and abs(float(k[1]) - ts_ini) < 2.0
                and (cls_name.upper() in k[0] or cls_name.replace("_", "-").upper() in k[0])
                for k in chaves_ja_emitidas
                if k[0].startswith("SINAL-")
            )
            if colidiu_biblioteca:
                continue
            if chave_yc in chaves_ja_emitidas:
                continue
            chaves_ja_emitidas.add(chave_yc)

            score = float(ent.get("match_score") or 0)
            yolo_conf = float(ent.get("yolo_conf") or 0)
            # Voto explícito do revisor (botão FP / curl) ganha sobre o
            # veredito derivado do match_score. O voto vem com ts em
            # segundos inteiros (frontend converte de "MM:SS"); a entrada
            # do yolo_custom pode ter fração — busca tolerante ±1s na
            # mesma classe e câmera.
            yc_id = chave_yc[0]
            voto_yc = None
            for (voto_id, voto_ts), vrec in reversed(list(votos_por_chave.items())):
                if voto_id == yc_id and abs(float(voto_ts) - ts_ini) <= 1.0:
                    voto_yc = vrec
                    break
            if voto_yc:
                veredito = _DECISAO_TO_VEREDITO.get(voto_yc.get("decisao"), "pendente")
            else:
                veredito = "detectado" if score >= 0.5 else "pendente"
            display = _CLASS_TO_DISPLAY.get(cls_name, cls_name)
            evidencia = (
                f"{display} · YOLO conf={yolo_conf:.2f} · NCC={score:.2f} "
                f"vs {ent.get('match_template', '?')}"
            )
            infracoes_ui.append(
                {
                    "id": chave_yc[0],
                    "titulo": display[:80],
                    "descricao": evidencia,
                    "gravidade": "leve",
                    "pontos": 0,
                    "timestamp_inicio": _ts_mmss(ts_ini),
                    "timestamp_fim": _ts_mmss(ts_ini + 2),
                    "duracao_fmt": "0:02",
                    "occurrences": 1,
                    "cameras_fmt": cam,
                    "confianca": "alta" if yolo_conf >= 0.6 else "media",
                    "evidencia": evidencia,
                    "veredito": veredito,
                    "origem": "yolo_custom",
                    "decisao_evidencia": ent.get("evidence_path", ""),
                }
            )

    # Fonte 6 — INÍCIO DO VÍDEO (R1020-M-c "motor morreu").
    # Regra fixa: TODO vídeo precisa que o avaliador (humano ou skill
    # `avaliador-detran`) cheque o primeiro MINUTO pra detectar motor que
    # morreu na partida ou engasgou nas primeiras manobras. Não depende
    # de detector rodando — entrada virtual aparece sempre, com
    # veredito=pendente, e usuário/loop decide via botão FP ou POST
    # training-example.
    # Memória: ~/.claude/projects/.../memory/project_motor_inicio_video.md
    chave_motor = ("R1020-M-c", "0.00")
    if chave_motor not in chaves_ja_emitidas:
        # Se já existe voto refuted/approved no examples.jsonl pra esse
        # (hash, R1020-M-c, ts=0), respeita o veredito do voto.
        voto = votos_por_chave.get(chave_motor)
        if voto:
            veredito_motor = _DECISAO_TO_VEREDITO.get(voto.get("decisao"), "pendente")
            ev_motor = voto.get("evidencia", "")[:240]
        else:
            veredito_motor = "pendente"
            ev_motor = "Revisar primeiro minuto: candidato deu partida sem o motor morrer/engasgar?"
        chaves_ja_emitidas.add(chave_motor)
        infracoes_ui.append(
            {
                "id": "R1020-M-c",
                "titulo": "Verificar partida do veículo (primeiro minuto)",
                "descricao": "Interromper o funcionamento do motor sem justa razão",
                "gravidade": "media",
                "pontos": 4,
                "timestamp_inicio": "00:00",
                "timestamp_fim": "01:00",
                "duracao_fmt": "1:00",
                "occurrences": 1,
                "cameras_fmt": "audio+frontal",
                "confianca": "media",
                "evidencia": ev_motor,
                "veredito": veredito_motor,
                "origem": "inicio_video",
                "decisao_evidencia": "Pendente revisão: motor morreu na partida?",
            }
        )

    # Ordena por timestamp pra ficar fácil de ler de cima pra baixo.
    def _ts_sort_key(item: dict) -> float:
        try:
            mm, ss = item.get("timestamp_inicio", "00:00").split(":")
            return int(mm) * 60 + int(ss)
        except Exception:
            return 0.0

    infracoes_ui.sort(key=_ts_sort_key)

    # Dedupe por janela de 1min: a mesma infração (mesmo id) só conta uma
    # vez por janela rolante de 60s. Réplicas dentro do minuto são "mesma
    # ocorrência vista por câmeras/templates diferentes" e poluem o painel.
    # Regra do usuário: só vale repetir se passar 1 min desde a última.
    DEDUPE_WINDOW_S = 60.0
    last_ts_por_id: dict[str, float] = {}
    deduped: list[dict] = []
    for item in infracoes_ui:
        ts_now = _ts_sort_key(item)
        item_id = item.get("id", "")
        last = last_ts_por_id.get(item_id)
        if last is not None and (ts_now - last) < DEDUPE_WINDOW_S:
            continue  # mesma infração dentro do minuto — pula
        deduped.append(item)
        last_ts_por_id[item_id] = ts_now
    infracoes_ui = deduped

    # Pontos de atenção: votos inconclusive do avaliador IA simbólico
    pontos_atencao: list[str] = []
    examples_path = PROJECT_ROOT / "storage" / "training" / "examples.jsonl"
    if examples_path.exists():
        for line in examples_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("hash") != hash:
                continue
            if rec.get("decisao") != "inconclusive":
                continue
            ts = rec.get("ts")
            ts_str = _ts_mmss(float(ts)) if ts is not None else "??:??"
            ev = (rec.get("evidencia") or "").strip()
            # tira o prefixo [<evento>] e a explicação técnica longa
            ev_short = ev.split("] ", 1)[-1] if ev.startswith("[") else ev
            pontos_atencao.append(f"{ts_str} — {ev_short[:140]}")

    # Aprovação: qualquer eliminatória/gravíssima reprova
    aprovado = (contagem["eliminatoria"] + contagem["gravissima"]) == 0

    # Cinto: extrai veredito do tier_a result
    cinto_inf = next(
        (x for x in result.get("infracoes_avaliadas", []) if x.get("id") == "R1020-GR-f"), None
    )
    positivos: list[str] = []
    if cinto_inf and cinto_inf.get("veredito") == "aprovado":
        positivos.append(f"Cinto de segurança detectado ({cinto_inf.get('motivo', '')[:80]})")

    motivo_reprov = None
    if not aprovado:
        n_elim = contagem["eliminatoria"]
        if n_elim > 0:
            motivo_reprov = f"{n_elim} infração(ões) gravíssima/eliminatória detectada(s)"
        else:
            motivo_reprov = "Pontuação acumulada acima do limite"

    # exam_meta (opcional, do upload original)
    exam_meta_path = ANALYSES_DIR / hash / "exam_meta.json"
    exam = {
        "candidato": "—",
        "cpf": "—",
        "renach": "—",
        "processo": "—",
        "categoria": "—",
        "veiculo": "—",
        "local": "—",
        "examinador": "—",
        "data_exame": datetime.now().strftime("%d/%m/%Y"),
    }
    if exam_meta_path.exists():
        try:
            m = json.loads(exam_meta_path.read_text())
            exam.update(
                {
                    "candidato": m.get("candidato_nome", "—") or "—",
                    "cpf": m.get("candidato_cpf", "—") or "—",
                    "renach": m.get("renach", "—") or "—",
                    "processo": m.get("processo", "—") or "—",
                    "categoria": m.get("categoria", "—") or "—",
                    "veiculo": m.get("veiculo", "—") or "—",
                    "local": m.get("local", "—") or "—",
                    "examinador": m.get("examinador", "—") or "—",
                }
            )
        except Exception:
            pass

    return {
        "summary": {
            "laudo_id": f"LAU-TIERA-{hash[:8].upper()}",
            "video_path": str(video),
            "video_hash": hash,
            "result_hash": f"tier_a:{hash[:12]}",
            "pdf_path": "",
            "rubrica": result.get("rubrica", "1020_2025"),
            "aprovado": aprovado,
            "pontuacao_total": pontos,
            "contagem": contagem,
            "duracao_seg": duracao_seg,
            "num_infracoes": len(infracoes_ui),
            "num_frames": int(duracao_seg * (vid.get("fps") or 30)),
            "elapsed_sec": result.get("elapsed_s", 0),
            "created_at": datetime.now().isoformat(),
            "model_version": result.get("schema_version", "tier_a/0.1"),
            "software_version": "tier_a/0.1",
            "score_risco": pontos,
            "confianca_media": 0.85 if infracoes_ui else 0.0,
            "cameras_envolvidas": sorted(cameras_envolvidas),
            "duracao_total_infracoes_seg": len(infracoes_ui) * 2,
            "densidade_infracoes_por_min": round(len(infracoes_ui) / max(1, duracao_seg / 60), 2),
        },
        "scored": {
            "infracoes": infracoes_ui,
            "contagem": contagem,
            "pontuacao_total": pontos,
            "aprovado": aprovado,
            "motivo_reprovacao": motivo_reprov,
        },
        "vlm": {
            "events": [],
            "timeline": [],
            "positive_aspects": positivos,
            "attention_points": pontos_atencao,
        },
        "timeline": [],
        "positivos": positivos,
        "pontos_atencao": pontos_atencao,
        "exame": exam,
        "canonical": {},
        "context_keys": [],
        "_paths": {
            "video_static": f"/static/videos/{video.name}",
            "analysis_hash": hash,
            "base_static": f"/static/analyses/{hash}/",
            "pdf_url": None,
        },
    }


def _skeleton_laudo(hash: str, video: Path) -> dict:
    # Se o tier_a já rodou e gerou result.json, devolver dados reais.
    real = _laudo_from_result_json(hash, video)
    if real is not None:
        return real
    # Senão, o stub vazio anterior (vídeo recém-uploadado, ainda em processamento)
    return _skeleton_stub_vazio(hash, video)


def _skeleton_stub_vazio(hash: str, video: Path) -> dict:
    return {
        "summary": {
            "laudo_id": f"LAU-STUB-{hash[:8].upper()}",
            "video_path": str(video),
            "video_hash": hash,
            "result_hash": f"stub:{hash[:12]}",
            "pdf_path": "",
            "rubrica": "789/2020",
            "aprovado": True,
            "pontuacao_total": 0,
            "contagem": {"eliminatoria": 0, "gravissima": 0, "grave": 0, "media": 0, "leve": 0},
            "duracao_seg": 240,
            "num_infracoes": 0,
            "num_frames": 0,
            "elapsed_sec": 0,
            "created_at": datetime.now().isoformat(),
            "model_version": "stub",
            "software_version": "stub",
            "score_risco": 0,
            "confianca_media": 0,
            "cameras_envolvidas": [],
            "duracao_total_infracoes_seg": 0,
            "densidade_infracoes_por_min": 0,
        },
        "scored": {
            "infracoes": [],
            "contagem": {"eliminatoria": 0, "gravissima": 0, "grave": 0, "media": 0, "leve": 0},
            "pontuacao_total": 0,
            "aprovado": True,
            "motivo_reprovacao": None,
        },
        "vlm": {"events": [], "timeline": [], "positive_aspects": [], "attention_points": []},
        "timeline": [],
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
            "data_exame": datetime.now().strftime("%d/%m/%Y"),
        },
        "canonical": {},
        "context_keys": [],
        "_paths": {
            "video_static": f"/static/videos/{video.name}",
            "analysis_hash": hash,
            "base_static": f"/static/analyses/{hash}/",
            "pdf_url": None,
        },
    }


@app.get("/api/analyses/hash/{hash}/result")
def analysis_by_hash(hash: str):
    video = _find_video_by_hash(hash)
    if video is None:
        raise HTTPException(status_code=404, detail="vídeo não encontrado")
    return _skeleton_laudo(hash, video)


@app.get("/api/analyses/{hash}/annotations")
def annotations(hash: str):
    return []


@app.get("/api/laudo-atual")
def laudo_atual():
    """Retorna o último vídeo processado com result.json válido."""
    if not VIDEOS_DIR.exists():
        raise HTTPException(status_code=404)
    candidates = []
    for mp4 in VIDEOS_DIR.glob("*.mp4"):
        h = _video_hash(mp4)
        result_json = ANALYSES_DIR / h / "result.json"
        if result_json.exists():
            candidates.append((result_json.stat().st_mtime, mp4, h))
    if not candidates:
        # Sem nenhum result.json — devolve skeleton do primeiro
        mp4s = sorted(VIDEOS_DIR.glob("*.mp4"))
        if not mp4s:
            raise HTTPException(status_code=404)
        return _skeleton_laudo(_video_hash(mp4s[0]), mp4s[0])
    # Mais recente primeiro
    candidates.sort(key=lambda x: -x[0])
    _, video, h = candidates[0]
    return _skeleton_laudo(h, video)


@app.get("/api/analyses/{hash}")
def analysis(hash: str):
    video = _find_video_by_hash(hash)
    if video is None:
        raise HTTPException(status_code=404, detail="vídeo não encontrado")
    return _skeleton_laudo(hash, video)


@app.get("/v2/analyses/{hash}/video/preprocessed")
def video_preprocessed(hash: str):
    """Serve o overlay.mp4 do YOLO (vídeo com bbox renderizado).

    O frontend (botão 'AI video' em AnaliseExame.tsx:511) abre essa rota
    em nova aba pra revisor admin inspecionar o que o pipeline viu.
    """
    from fastapi.responses import FileResponse

    overlay = ANALYSES_DIR / hash / "yolo_explore" / "overlay.mp4"
    if not overlay.exists():
        raise HTTPException(
            status_code=404, detail="overlay.mp4 não existe; rode yolo_explore primeiro"
        )
    return FileResponse(str(overlay), media_type="video/mp4", filename=f"{hash[:8]}_overlay.mp4")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
