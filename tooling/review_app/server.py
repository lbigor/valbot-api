"""
Review App — frontend mínimo para o user revisar visualmente as detecções
que o Claude marca como TP. 1 imagem, 1 pergunta, 3 botões (SIM/NÃO/INCONCLUSIVO).

Atalhos de teclado: 1=SIM, 2=NÃO, 3=INCONCLUSIVO, ←=anterior, →=pular.

Rodar: /Users/igorlima/Documents/Valbot/.venv/bin/python -m tooling.review_app.server
Abrir: http://localhost:8003
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).parent.parent.parent
ITEMS_FILE = PROJECT_ROOT / "storage" / "training" / "review_items.json"
VOTES_FILE = PROJECT_ROOT / "storage" / "training" / "review_votes.json"
FRAMES_DIR = PROJECT_ROOT / "storage" / "frames"
CALIB_FILE = PROJECT_ROOT / "storage" / "training" / "zones_calibration.json"
CALIB_REL_FILE = PROJECT_ROOT / "storage" / "training" / "zones_calibration_rel.json"
CALIB_REL_META = PROJECT_ROOT / "storage" / "training" / "calibrate_rel_meta.json"
VIDEOS = ["vid1", "vid2", "vid3", "vid4"]
ZONE_NAMES = ["VOLANTE", "CAMBIO", "FREIO_MAO", "PAINEL"]

# Offsets default em frações da ESCALA escolhida pra cada zona.
# anchor = keypoint usado como ponto-zero
# scale = nome da escala anatômica (biacromial, arm_d_len, arm_e_len, torso_len)
# ox, oy = deslocamento do CENTRO da zona em relação ao âncora (frações da escala)
# w, h = tamanho da zona (frações da escala)
DEFAULT_REL_ZONES = {
    "VOLANTE": {
        "anchor": "right_shoulder",
        "scale": "arm_d_len",
        "ox": 0.6,
        "oy": 0.1,
        "w": 0.7,
        "h": 0.6,
    },
    "CAMBIO": {
        "anchor": "right_hip",
        "scale": "torso_len",
        "ox": -0.4,
        "oy": 0.2,
        "w": 0.5,
        "h": 0.7,
    },
    "FREIO_MAO": {
        "anchor": "right_hip",
        "scale": "biacromial",
        "ox": -1.0,
        "oy": 0.3,
        "w": 0.5,
        "h": 0.6,
    },
    "PAINEL": {
        "anchor": "right_shoulder",
        "scale": "biacromial",
        "ox": 1.5,
        "oy": 1.0,
        "w": 0.9,
        "h": 0.7,
    },
}

app = FastAPI(title="VALBOT Review")
app.mount("/img", StaticFiles(directory=str(FRAMES_DIR)), name="frames")


class Vote(BaseModel):
    item_id: str
    vote: str  # "S" | "N" | "I"
    note: str = ""


def load_items() -> list[dict]:
    return json.loads(ITEMS_FILE.read_text())


def load_votes() -> dict[str, dict]:
    if not VOTES_FILE.exists():
        return {}
    return json.loads(VOTES_FILE.read_text())


def save_votes(votes: dict[str, dict]) -> None:
    VOTES_FILE.write_text(json.dumps(votes, indent=2, ensure_ascii=False))


@app.get("/api/items")
def get_items():
    items = load_items()
    votes = load_votes()
    for item in items:
        item["vote"] = votes.get(item["id"], {}).get("vote")
        item["voted_at"] = votes.get(item["id"], {}).get("voted_at")
    return items


@app.get("/api/next")
def get_next():
    items = load_items()
    votes = load_votes()
    pending = [i for i in items if i["id"] not in votes]
    if not pending:
        return {"done": True, "total": len(items), "stats": _stats(items, votes)}
    item = pending[0]
    voted = len(items) - len(pending)
    return {
        "done": False,
        "item": item,
        "progress": {"current": voted + 1, "total": len(items)},
    }


@app.post("/api/vote")
def post_vote(vote: Vote):
    if vote.vote not in ("S", "N", "I"):
        raise HTTPException(status_code=400, detail="vote must be S, N or I")
    votes = load_votes()
    votes[vote.item_id] = {
        "vote": vote.vote,
        "note": vote.note,
        "voted_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_votes(votes)
    return {"ok": True}


@app.delete("/api/vote/{item_id}")
def delete_vote(item_id: str):
    votes = load_votes()
    if item_id in votes:
        del votes[item_id]
        save_votes(votes)
    return {"ok": True}


def _stats(items, votes):
    counts = {"S": 0, "N": 0, "I": 0}
    for v in votes.values():
        counts[v["vote"]] = counts.get(v["vote"], 0) + 1
    return counts


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML


# ==================== Calibração de zonas ====================


def load_calib() -> dict:
    if not CALIB_FILE.exists():
        return {}
    return json.loads(CALIB_FILE.read_text())


def save_calib(data: dict) -> None:
    CALIB_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


class ZoneRect(BaseModel):
    name: str  # VOLANTE | CAMBIO | FREIO_MAO | PAINEL
    x1: int
    y1: int
    x2: int
    y2: int


class CalibSave(BaseModel):
    video: str  # vid1..vid4
    zones: list[ZoneRect]


@app.get("/api/calibrate/state")
def calib_state():
    calib = load_calib()
    return {
        "videos": VIDEOS,
        "zone_names": ZONE_NAMES,
        "calibrated": list(calib.keys()),
        "calib": calib,
    }


@app.post("/api/calibrate/save")
def calib_save(payload: CalibSave):
    if payload.video not in VIDEOS:
        raise HTTPException(400, "video inválido")
    names = {z.name for z in payload.zones}
    missing = set(ZONE_NAMES) - names
    if missing:
        raise HTTPException(400, f"zonas faltando: {missing}")
    calib = load_calib()
    calib[payload.video] = [z.dict() for z in payload.zones]
    save_calib(calib)
    return {"ok": True, "calibrated": list(calib.keys())}


@app.delete("/api/calibrate/{video}")
def calib_clear(video: str):
    calib = load_calib()
    if video in calib:
        del calib[video]
        save_calib(calib)
    return {"ok": True}


@app.get("/calibrate", response_class=HTMLResponse)
def calibrate_page():
    return CALIBRATE_HTML


# ==================== Calibração RELATIVA (zonas em frações da escala anatômica) ====================


def load_rel() -> dict:
    if CALIB_REL_FILE.exists():
        return json.loads(CALIB_REL_FILE.read_text())
    return dict(DEFAULT_REL_ZONES)


def save_rel(data: dict) -> None:
    CALIB_REL_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_meta() -> dict:
    if CALIB_REL_META.exists():
        return json.loads(CALIB_REL_META.read_text())
    return {}


@app.get("/api/calibrate-rel/state")
def calib_rel_state():
    return {
        "videos": VIDEOS,
        "zone_names": ZONE_NAMES,
        "zones": load_rel(),
        "meta": load_meta(),
        "default_zones": DEFAULT_REL_ZONES,
    }


class RelZone(BaseModel):
    anchor: str
    scale: str
    ox: float
    oy: float
    w: float
    h: float


class RelSave(BaseModel):
    zones: dict[str, RelZone]


@app.post("/api/calibrate-rel/save")
def calib_rel_save(payload: RelSave):
    data = {name: z.dict() for name, z in payload.zones.items()}
    save_rel(data)
    return {"ok": True, "saved_zones": list(data.keys())}


@app.post("/api/calibrate-rel/reset")
def calib_rel_reset():
    save_rel(dict(DEFAULT_REL_ZONES))
    return {"ok": True}


@app.get("/calibrate-rel", response_class=HTMLResponse)
def calibrate_rel_page():
    return CALIBRATE_REL_HTML


@app.get("/laudos", response_class=HTMLResponse)
def laudos_page():
    return LAUDOS_HTML


@app.get("/api/laudos")
def laudos_data():
    base = PROJECT_ROOT / "storage" / "frames" / "simulacoes"
    f = base / "laudos_iter4.json"
    if not f.exists():
        return {"laudos": {}}
    return {"laudos": json.loads(f.read_text())}


@app.get("/debug", response_class=HTMLResponse)
def debug_page():
    return DEBUG_HTML


# ==================== Anotação manual frame-a-frame ====================

ANNOT_FILE = PROJECT_ROOT / "storage" / "training" / "annotations_manual.json"


def load_annot() -> dict:
    if ANNOT_FILE.exists():
        return json.loads(ANNOT_FILE.read_text())
    return {}


def save_annot(data: dict) -> None:
    ANNOT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


class Annot(BaseModel):
    video: str
    ts: float
    box: list[int]  # [x1, y1, x2, y2] no frame BL 640x360
    label: str
    note: str = ""


@app.get("/api/anotacoes")
def get_annots(video: str | None = None):
    data = load_annot()
    if video:
        return {"annotations": data.get(video, [])}
    return {"annotations": data}


@app.post("/api/anotacoes")
def post_annot(a: Annot):
    data = load_annot()
    data.setdefault(a.video, []).append(
        {
            "ts": round(a.ts, 2),
            "box": a.box,
            "label": a.label,
            "note": a.note,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    # ordenar por ts
    data[a.video].sort(key=lambda x: x["ts"])
    save_annot(data)
    return {"ok": True, "total": len(data[a.video])}


@app.delete("/api/anotacoes")
def del_annot(video: str, idx: int):
    data = load_annot()
    if video in data and 0 <= idx < len(data[video]):
        del data[video][idx]
        save_annot(data)
    return {"ok": True}


@app.get("/anotar", response_class=HTMLResponse)
def anotar_page():
    return ANOTAR_HTML


@app.get("/api/anotacoes/unified")
def anotacoes_unified():
    f = PROJECT_ROOT / "storage" / "training" / "annotations_unified" / "annotations_unified.json"
    if f.exists():
        return json.loads(f.read_text())
    return {}


@app.get("/api/anotar/frames/{video}")
def anotar_frames_count(video: str):
    """Quantos frames (5fps) o vídeo tem na sequência pré-extraída."""
    seq = PROJECT_ROOT / "storage" / "frames" / "anotar_seq" / video
    if not seq.exists():
        return {"total": 0, "fps": 5}
    n = len(list(seq.glob("f*.jpg")))
    return {"total": n, "fps": 5}


# ==================== Diagrama 2D simbólico ====================


@app.get("/diagrama", response_class=HTMLResponse)
def diagrama_page():
    return DIAGRAMA_HTML


@app.get("/api/diagrama/{vid}")
def diagrama_data(vid: str):
    base = PROJECT_ROOT / "storage" / "frames" / "diagrama2d"
    odom = PROJECT_ROOT / "storage" / "frames" / "odometria"
    eventos_f = base / f"{vid}_eventos.json"
    resumo_f = base / f"{vid}_resumo.json"
    if not (eventos_f.exists() and resumo_f.exists()):
        raise HTTPException(404, f"diagrama de {vid} não gerado")
    real_path = base / f"{vid}_real_BL.mp4"
    real_url = f"/img/diagrama2d/{vid}_real_BL.mp4" if real_path.exists() else None
    tesla_path = PROJECT_ROOT / "storage" / "frames" / "topdown_tesla" / f"{vid}_tesla.mp4"
    tesla_url = f"/img/topdown_tesla/{vid}_tesla.mp4" if tesla_path.exists() else None
    movimento_f = odom / f"{vid}_movimento.json"
    movimento = json.loads(movimento_f.read_text()) if movimento_f.exists() else None
    return {
        "video": vid,
        "mp4_url": f"/img/diagrama2d/{vid}_simbolico.mp4",
        "real_url": real_url,
        "topdown_url": tesla_url,
        "movimento": movimento,
        "eventos": json.loads(eventos_f.read_text()),
        "resumo": json.loads(resumo_f.read_text()),
    }


INDEX_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>VALBOT — Review</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; background: #0e1116; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
  body { display: flex; flex-direction: column; align-items: center; padding: 16px; gap: 12px; }
  .progress { font-size: 13px; color: #8b949e; }
  .meta { font-size: 13px; color: #8b949e; text-align: center; }
  .claim { font-size: 22px; font-weight: 600; text-align: center; line-height: 1.3; max-width: 900px; }
  .context { font-size: 13px; color: #8b949e; text-align: center; max-width: 900px; padding: 0 16px; }
  .img-row { display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; align-items: flex-start; max-width: 100%; }
  .img-wrap { background: #161b22; border-radius: 8px; padding: 8px; }
  .img-wrap img { display: block; max-width: 100%; max-height: 55vh; border-radius: 4px; }
  .img-wrap canvas { display: block; max-width: 100%; max-height: 55vh; border-radius: 4px; }
  .img-label { font-size: 11px; color: #8b949e; margin-top: 4px; text-align: center; }
  .pose-toggles { display: flex; gap: 6px; flex-wrap: wrap; justify-content: center; margin: 8px 0; }
  .pose-toggle {
    padding: 8px 14px; border-radius: 8px; border: 2px solid;
    cursor: pointer; font-size: 13px; font-weight: 600;
    background: #161b22; min-height: 38px;
    -webkit-tap-highlight-color: transparent;
  }
  .pose-toggle.off { opacity: 0.35; text-decoration: line-through; }
  .actions { display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; }
  button { font-size: 17px; padding: 14px 22px; border-radius: 8px; border: 1px solid #30363d; background: #21262d; color: #e6edf3; cursor: pointer; min-width: 130px; }
  button:hover { background: #30363d; }
  button.yes { border-color: #2da44e; }
  button.yes:hover { background: #2da44e; color: white; }
  button.no  { border-color: #cf222e; }
  button.no:hover { background: #cf222e; color: white; }
  button.inc { border-color: #bf8700; }
  button.inc:hover { background: #bf8700; color: white; }
  .key { font-size: 11px; opacity: 0.7; margin-left: 6px; }
  .done { font-size: 22px; padding: 24px; text-align: center; }
  .done h1 { font-size: 28px; margin-bottom: 16px; }
  .stats { display: flex; gap: 24px; justify-content: center; margin: 16px 0; }
  .stats .stat { padding: 12px 18px; border-radius: 6px; background: #161b22; min-width: 100px; }
  .stats .stat .n { font-size: 28px; font-weight: bold; }
  .stats .stat .l { font-size: 12px; color: #8b949e; }
  .small-link { font-size: 12px; color: #8b949e; text-decoration: none; margin-top: 8px; }
  .small-link:hover { color: #e6edf3; }
</style>
</head>
<body>
<div class="progress" id="progress">carregando…</div>
<div class="meta" id="meta"></div>
<div class="claim" id="claim"></div>
<div class="context" id="context"></div>
<div class="pose-toggles" id="pose-toggles" style="display:none"></div>
<div class="img-row" id="img-row"></div>
<div class="actions">
  <button class="yes" onclick="vote('S')">✅ SIM<span class="key">[1]</span></button>
  <button class="no"  onclick="vote('N')">❌ NÃO<span class="key">[2]</span></button>
  <button class="inc" onclick="vote('I')">❓ INCONCLUSIVO<span class="key">[3]</span></button>
</div>
<a class="small-link" href="#" onclick="showAll(); return false">ver todos / desfazer voto</a>

<script>
let currentItem = null;

async function loadNext() {
  const r = await fetch('/api/next');
  const data = await r.json();
  if (data.done) {
    document.body.innerHTML = `
      <div class="done">
        <h1>Tudo revisado ✅</h1>
        <div class="stats">
          <div class="stat"><div class="n" style="color:#2da44e">${data.stats.S || 0}</div><div class="l">SIM</div></div>
          <div class="stat"><div class="n" style="color:#cf222e">${data.stats.N || 0}</div><div class="l">NÃO</div></div>
          <div class="stat"><div class="n" style="color:#bf8700">${data.stats.I || 0}</div><div class="l">INCONCLUSIVO</div></div>
        </div>
        <p style="color:#8b949e">Total: ${data.total}</p>
        <a href="#" onclick="showAll(); return false" style="color:#58a6ff">ver detalhes</a>
      </div>`;
    return;
  }
  currentItem = data.item;
  document.getElementById('progress').textContent = `${data.progress.current} de ${data.progress.total}`;
  document.getElementById('meta').textContent = `${data.item.video} · t=${data.item.timestamp_s}s · cat: ${data.item.category}`;
  document.getElementById('claim').textContent = data.item.claim;
  document.getElementById('context').textContent = data.item.context;
  const row = document.getElementById('img-row');
  const togglesDiv = document.getElementById('pose-toggles');
  const cb = `?_=${Date.now()}`;

  if (data.item.category === 'pose' && data.item.pose_data) {
    // Render dinâmico com toggles
    togglesDiv.style.display = 'flex';
    renderPoseToggles(togglesDiv);
    row.innerHTML = '<div class="img-wrap"><canvas id="pose-canvas" width="640" height="360"></canvas><div class="img-label">arraste toggles acima pra ocultar partes</div></div>';
    drawPoseFrame(data.item, cb);
  } else {
    togglesDiv.style.display = 'none';
    let html = `<div class="img-wrap"><img src="/img/${data.item.image_path}${cb}"><div class="img-label">contexto · bbox em verde</div></div>`;
    if (data.item.zoom_path) {
      html += `<div class="img-wrap"><img src="/img/${data.item.zoom_path}${cb}"><div class="img-label">zoom limpo (4×) · sem overlay</div></div>`;
    }
    row.innerHTML = html;
  }
}

// ===== Pose rendering com toggles =====
const POSE_LAYERS = [
  {key: 'skeleton', label: 'Esqueleto',  color: '#ffffff'},
  {key: 'head',     label: 'Cabeça',     color: '#dc1414'},
  {key: 'arms',     label: 'Braços',     color: '#0078dc'},
  {key: 'hands',    label: 'Mãos',       color: '#ffff00'},
  {key: 'torso',    label: 'Torso',      color: '#00b400'},
  {key: 'legs',     label: 'Pernas',     color: '#a050a0'},
  {key: 'labels',   label: 'Labels',     color: '#7ee787'},
];
let poseLayerState = JSON.parse(localStorage.getItem('poseLayerState') || 'null') || POSE_LAYERS.reduce((o,l)=>{o[l.key]=true;return o;}, {});
let currentPoseItem = null;

function renderPoseToggles(div) {
  div.innerHTML = '';
  POSE_LAYERS.forEach(l => {
    const b = document.createElement('button');
    b.className = 'pose-toggle' + (poseLayerState[l.key] ? '' : ' off');
    b.style.borderColor = l.color;
    b.style.color = l.color;
    b.textContent = l.label;
    b.onclick = () => {
      poseLayerState[l.key] = !poseLayerState[l.key];
      localStorage.setItem('poseLayerState', JSON.stringify(poseLayerState));
      renderPoseToggles(div);
      if (currentPoseItem) drawPoseFrame(currentPoseItem, '?_=' + Date.now());
    };
    div.appendChild(b);
  });
}

const SKEL_PAIRS = [
  ['left_shoulder','right_shoulder'],
  ['left_shoulder','left_elbow'], ['left_elbow','left_wrist'],
  ['right_shoulder','right_elbow'], ['right_elbow','right_wrist'],
  ['left_shoulder','left_hip'], ['right_shoulder','right_hip'],
  ['left_hip','right_hip'],
  ['left_hip','left_knee'], ['left_knee','left_ankle'],
  ['right_hip','right_knee'], ['right_knee','right_ankle'],
];
const ROLE_BG = {CONDUTOR:'#00b428', EXAMINADOR:'#ffa500', OUTRO:'#8c8c8c'};

function drawBox(ctx, box, color, label) {
  if (!box) return;
  const [x1,y1,x2,y2] = box;
  ctx.strokeStyle = color; ctx.lineWidth = 2;
  ctx.strokeRect(x1, y1, x2-x1, y2-y1);
  if (label && poseLayerState.labels) {
    ctx.font = 'bold 12px sans-serif';
    const m = ctx.measureText(label);
    ctx.fillStyle = color;
    ctx.fillRect(x1, Math.max(0,y1-16), m.width+6, 14);
    ctx.fillStyle = '#fff';
    ctx.fillText(label, x1+3, Math.max(11, y1-4));
  }
}

function drawPoseFrame(item, cb) {
  currentPoseItem = item;
  const cv = document.getElementById('pose-canvas');
  if (!cv) return;
  const ctx = cv.getContext('2d');
  const img = new Image();
  img.onload = () => {
    ctx.clearRect(0,0,640,360);
    ctx.drawImage(img, 0, 0, 640, 360);
    if (!item.pose_data || !item.pose_data.persons) return;
    for (const p of item.pose_data.persons) {
      // Esqueleto
      if (poseLayerState.skeleton && p.kpts) {
        ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.5;
        for (const [a,b] of SKEL_PAIRS) {
          const ka = p.kpts[a], kb = p.kpts[b];
          if (ka && kb) {
            ctx.beginPath();
            ctx.moveTo(ka[0], ka[1]);
            ctx.lineTo(kb[0], kb[1]);
            ctx.stroke();
          }
        }
        // pontos
        ctx.fillStyle = '#ffffff';
        for (const k of Object.values(p.kpts)) {
          ctx.beginPath();
          ctx.arc(k[0], k[1], 3, 0, Math.PI*2);
          ctx.fill();
        }
      }
      // Cabeça
      if (poseLayerState.head) drawBox(ctx, p.head, '#dc1414', 'CABECA');
      // Braços
      if (poseLayerState.arms) {
        drawBox(ctx, p.arm_d, '#0078dc', 'BRACO D');
        drawBox(ctx, p.arm_e, '#0078dc', 'BRACO E');
      }
      // Mãos
      if (poseLayerState.hands) {
        drawBox(ctx, p.hand_d, '#ffff00', 'MAO D');
        drawBox(ctx, p.hand_e, '#ffff00', 'MAO E');
      }
      // Torso
      if (poseLayerState.torso) drawBox(ctx, p.torso, '#00b400', 'TORSO');
      // Pernas
      if (poseLayerState.legs) {
        drawBox(ctx, p.leg_d, '#a050a0', 'PERNA D');
        drawBox(ctx, p.leg_e, '#a050a0', 'PERNA E');
      }
      // Role label
      if (poseLayerState.labels && p.kpts && p.kpts.nose) {
        const nose = p.kpts.nose;
        const lp = [Math.max(2, nose[0]-40), Math.max(20, nose[1]-55)];
        const text = p.role;
        ctx.font = 'bold 18px sans-serif';
        const m = ctx.measureText(text);
        ctx.fillStyle = ROLE_BG[p.role] || '#888';
        ctx.fillRect(lp[0]-2, lp[1]-20, m.width+8, 24);
        ctx.fillStyle = '#fff';
        ctx.fillText(text, lp[0]+2, lp[1]-2);
      }
    }
  };
  img.src = `/img/${item.image_path}${cb}`;
}

async function vote(v) {
  if (!currentItem) return;
  await fetch('/api/vote', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({item_id: currentItem.id, vote: v})
  });
  loadNext();
}

async function showAll() {
  const r = await fetch('/api/items');
  const items = await r.json();
  let html = '<div style="max-width:1000px; padding:24px">';
  html += '<h1 style="margin-bottom:16px">Todos os itens</h1>';
  html += '<a href="/" style="color:#58a6ff">← voltar pra revisão</a>';
  html += '<table style="width:100%; margin-top:16px; border-collapse:collapse">';
  html += '<tr style="border-bottom:1px solid #30363d"><th style="text-align:left; padding:8px">ID</th><th style="text-align:left; padding:8px">Vídeo</th><th style="text-align:left; padding:8px">Pergunta</th><th style="padding:8px">Voto</th><th style="padding:8px">Ação</th></tr>';
  for (const it of items) {
    const v = it.vote || '—';
    const color = v === 'S' ? '#2da44e' : v === 'N' ? '#cf222e' : v === 'I' ? '#bf8700' : '#8b949e';
    html += `<tr style="border-bottom:1px solid #21262d">
      <td style="padding:8px">${it.id}</td>
      <td style="padding:8px">${it.video} t=${it.timestamp_s}</td>
      <td style="padding:8px">${it.claim}</td>
      <td style="padding:8px; text-align:center; color:${color}; font-weight:bold">${v}</td>
      <td style="padding:8px; text-align:center">${it.vote ? `<a href="#" onclick="undo('${it.id}'); return false" style="color:#58a6ff">desfazer</a>` : ''}</td>
    </tr>`;
  }
  html += '</table></div>';
  document.body.innerHTML = html;
}

async function undo(id) {
  await fetch(`/api/vote/${id}`, {method: 'DELETE'});
  showAll();
}

document.addEventListener('keydown', (e) => {
  if (e.key === '1') vote('S');
  else if (e.key === '2') vote('N');
  else if (e.key === '3') vote('I');
});

loadNext();
</script>
</body>
</html>
"""


CALIBRATE_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>VALBOT — Calibrar zonas</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-touch-callout: none; -webkit-user-select: none; user-select: none; }
  html, body { overscroll-behavior: none; touch-action: manipulation; }
  body { background: #0e1116; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 12px; }
  .top { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
  .top strong { font-size: 14px; }
  .vids { display: flex; gap: 6px; flex-wrap: wrap; }
  .vid-btn {
    padding: 12px 18px; border-radius: 10px; background: #21262d; color: #e6edf3;
    border: 2px solid #30363d; cursor: pointer; font-size: 16px; font-weight: 600;
    min-height: 48px; min-width: 70px;
  }
  .vid-btn.active { background: #1f6feb; border-color: #58a6ff; }
  .vid-btn.done::after { content: " ✓"; color: #7ee787; }
  .zones-pal { display: flex; gap: 6px; flex-wrap: wrap; }
  .zone-btn {
    padding: 12px 18px; border-radius: 10px; border: 3px solid transparent;
    cursor: pointer; font-weight: 700; font-size: 16px; min-height: 48px;
    color: white; -webkit-tap-highlight-color: transparent;
  }
  .zone-btn.active { box-shadow: 0 0 0 4px white inset; }
  .zone-btn.done::after { content: " ✓"; }
  .canvas-wrap {
    display: inline-block; position: relative; background: #161b22;
    border-radius: 8px; padding: 6px; max-width: 100%;
  }
  canvas {
    display: block; cursor: crosshair; touch-action: none;
    max-width: 100%; height: auto;
  }
  .actions { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; align-items: center; }
  button {
    padding: 14px 22px; border-radius: 10px; border: 1px solid #30363d;
    background: #21262d; color: #e6edf3; cursor: pointer;
    font-size: 16px; font-weight: 600; min-height: 50px;
    -webkit-tap-highlight-color: transparent;
  }
  button.primary { background: #2da44e; border-color: #2da44e; color: white; }
  button:active { transform: scale(0.97); }
  .hint { font-size: 13px; color: #8b949e; line-height: 1.4; }
  .legend { font-size: 13px; margin-top: 12px; color: #c9d1d9; }
  .legend ul { margin-left: 22px; line-height: 1.6; }
  .pen-mode { display: inline-block; margin-left: auto; font-size: 12px; color: #8b949e; padding: 4px 10px; background: #161b22; border-radius: 12px; }
  .pen-mode.active { color: #7ee787; }
  @media (max-width: 800px) {
    body { padding: 8px; }
    .top { gap: 8px; }
  }
</style>
</head>
<body>
<div class="top">
  <strong>Vídeo:</strong>
  <div class="vids" id="vids"></div>
  <strong style="margin-left:16px">Zona ativa:</strong>
  <div class="zones-pal" id="zones-pal"></div>
</div>
<div class="hint">
  Selecione uma zona e <strong>arraste com a Apple Pencil</strong> (ou dedo / mouse) sobre o frame pra desenhar o retângulo. Re-arrastar substitui. No teclado: <kbd>1</kbd>=VOLANTE, <kbd>2</kbd>=CAMBIO, <kbd>3</kbd>=FREIO_MAO, <kbd>4</kbd>=PAINEL.
  <span class="pen-mode" id="pen-status">aguardando entrada</span>
</div>
<div class="canvas-wrap"><canvas id="cv" width="640" height="360"></canvas></div>
<div class="actions">
  <button onclick="clearOne()">Apagar zona ativa</button>
  <button onclick="clearAll()">Limpar tudo</button>
  <button onclick="loadFromServer()">Recarregar</button>
  <button class="primary" id="save-btn" onclick="save()">Salvar e próximo →</button>
  <a href="/" style="margin-left:auto; color:#58a6ff; text-decoration:none; align-self:center; font-size:14px">← revisão</a>
</div>
<div class="legend">
  <p><strong>Como definir cada zona</strong> (não precisa ser exato — é a região onde a mão tipicamente fica):</p>
  <ul>
    <li><strong>VOLANTE</strong>: área do volante visível</li>
    <li><strong>CAMBIO</strong>: alavanca de marchas (entre os bancos)</li>
    <li><strong>FREIO_MAO</strong>: alavanca do freio de mão</li>
    <li><strong>PAINEL</strong>: console central / rádio / botões</li>
  </ul>
</div>

<script>
const VIDS = ['vid1','vid2','vid3','vid4'];
const ZONES = ['VOLANTE','CAMBIO','FREIO_MAO','PAINEL'];
const COLORS = {VOLANTE:'#00c800', CAMBIO:'#ffc800', FREIO_MAO:'#c864c8', PAINEL:'#ff6432'};

let currentVid = 'vid1';
let activeZone = 'VOLANTE';
let zones = {}; // {VOLANTE: {x1,y1,x2,y2}, ...}
let img = new Image();
let isDragging = false; let dragStart = null;
let calibratedSet = new Set();
const cv = document.getElementById('cv');
const ctx = cv.getContext('2d');

function renderTopBar() {
  const v = document.getElementById('vids');
  v.innerHTML = '';
  VIDS.forEach(vid => {
    const b = document.createElement('button');
    b.className = 'vid-btn' + (vid===currentVid?' active':'') + (calibratedSet.has(vid)?' done':'');
    b.textContent = vid;
    b.onclick = () => switchVideo(vid);
    v.appendChild(b);
  });
  const p = document.getElementById('zones-pal');
  p.innerHTML = '';
  ZONES.forEach(z => {
    const b = document.createElement('button');
    b.className = 'zone-btn' + (z===activeZone?' active':'') + (zones[z]?' done':'');
    b.style.background = COLORS[z];
    b.style.color = 'white';
    b.style.borderColor = COLORS[z];
    b.textContent = z;
    b.onclick = () => { activeZone = z; renderTopBar(); };
    p.appendChild(b);
  });
}

function draw() {
  ctx.clearRect(0,0,640,360);
  if (img.complete) ctx.drawImage(img, 0, 0, 640, 360);
  for (const [name, r] of Object.entries(zones)) {
    ctx.strokeStyle = COLORS[name];
    ctx.lineWidth = 3;
    ctx.fillStyle = COLORS[name] + '33';
    ctx.fillRect(r.x1, r.y1, r.x2-r.x1, r.y2-r.y1);
    ctx.strokeRect(r.x1, r.y1, r.x2-r.x1, r.y2-r.y1);
    ctx.fillStyle = COLORS[name];
    ctx.font = 'bold 14px sans-serif';
    ctx.fillText(name, r.x1+4, r.y1+16);
  }
}

// Canvas é renderizado em 640x360 mas pode estar escalado no display.
// Pointer Events: unifica mouse, touch e pen (Apple Pencil) numa só API.
function getCanvasPos(e) {
  const r = cv.getBoundingClientRect();
  const scaleX = cv.width  / r.width;
  const scaleY = cv.height / r.height;
  return { x: (e.clientX - r.left) * scaleX, y: (e.clientY - r.top) * scaleY };
}

function showPenStatus(type) {
  const el = document.getElementById('pen-status');
  if (type === 'pen') { el.textContent = '✏️ Apple Pencil ativa'; el.classList.add('active'); }
  else if (type === 'touch') { el.textContent = '👆 Toque'; el.classList.add('active'); }
  else { el.textContent = '🖱 Mouse'; el.classList.add('active'); }
}

cv.addEventListener('pointerdown', e => {
  e.preventDefault();
  cv.setPointerCapture(e.pointerId);
  const p = getCanvasPos(e);
  dragStart = p;
  isDragging = true;
  showPenStatus(e.pointerType);
});
cv.addEventListener('pointermove', e => {
  if (!isDragging) return;
  e.preventDefault();
  const p = getCanvasPos(e);
  draw();
  ctx.strokeStyle = COLORS[activeZone];
  ctx.lineWidth = 3; ctx.setLineDash([6,6]);
  ctx.strokeRect(dragStart.x, dragStart.y, p.x-dragStart.x, p.y-dragStart.y);
  ctx.setLineDash([]);
});
function endDrag(e) {
  if (!isDragging) return;
  e.preventDefault?.();
  const p = getCanvasPos(e);
  const x1 = Math.max(0, Math.min(dragStart.x, p.x));
  const y1 = Math.max(0, Math.min(dragStart.y, p.y));
  const x2 = Math.min(640, Math.max(dragStart.x, p.x));
  const y2 = Math.min(360, Math.max(dragStart.y, p.y));
  if (x2 - x1 > 5 && y2 - y1 > 5) {
    zones[activeZone] = {
      x1: Math.round(x1), y1: Math.round(y1),
      x2: Math.round(x2), y2: Math.round(y2)
    };
  }
  isDragging = false;
  const nextZ = ZONES.find(z => !zones[z]);
  if (nextZ) activeZone = nextZ;
  renderTopBar(); draw();
}
cv.addEventListener('pointerup', endDrag);
cv.addEventListener('pointercancel', endDrag);
cv.addEventListener('pointerleave', e => { if (isDragging) endDrag(e); });

// previne gestos de scroll/zoom enquanto desenha
cv.addEventListener('touchstart', e => e.preventDefault(), {passive:false});
cv.addEventListener('touchmove',  e => e.preventDefault(), {passive:false});
cv.addEventListener('touchend',   e => e.preventDefault(), {passive:false});

document.addEventListener('keydown', e => {
  const map = {'1':'VOLANTE','2':'CAMBIO','3':'FREIO_MAO','4':'PAINEL'};
  if (map[e.key]) { activeZone = map[e.key]; renderTopBar(); }
});

function switchVideo(vid) {
  currentVid = vid;
  zones = {};
  img.onload = () => draw();
  img.src = `/img/calibrate/${vid}_ref.jpg?_=${Date.now()}`;
  loadFromServer();
}

async function loadFromServer() {
  const r = await fetch('/api/calibrate/state');
  const data = await r.json();
  calibratedSet = new Set(data.calibrated);
  if (data.calib[currentVid]) {
    zones = {};
    for (const z of data.calib[currentVid]) zones[z.name] = {x1:z.x1, y1:z.y1, x2:z.x2, y2:z.y2};
  }
  activeZone = ZONES.find(z => !zones[z]) || 'VOLANTE';
  renderTopBar(); draw();
}

async function save() {
  const missing = ZONES.filter(z => !zones[z]);
  if (missing.length) { alert('Faltam zonas: ' + missing.join(', ')); return; }
  const payload = { video: currentVid, zones: ZONES.map(n => ({name:n, ...zones[n]})) };
  const r = await fetch('/api/calibrate/save', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  if (!r.ok) { alert('Erro ao salvar'); return; }
  // próximo vídeo não calibrado
  await loadFromServer();
  const next = VIDS.find(v => !calibratedSet.has(v));
  if (next) switchVideo(next);
  else alert('Todos os 4 vídeos calibrados! 🎉');
}

function clearAll() {
  zones = {};
  activeZone = 'VOLANTE';
  renderTopBar(); draw();
}

function clearOne() {
  delete zones[activeZone];
  renderTopBar(); draw();
}

switchVideo('vid1');
</script>
</body>
</html>
"""


CALIBRATE_REL_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>VALBOT — Calibrar zonas relativas</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-touch-callout: none; -webkit-user-select: none; user-select: none; }
  html, body { overscroll-behavior: none; touch-action: manipulation; }
  body { background: #0e1116; color: #e6edf3; font-family: -apple-system, sans-serif; padding: 12px; }
  .row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
  .vid-btn, .zone-btn, button {
    padding: 12px 16px; border-radius: 10px; cursor: pointer; font-size: 15px; font-weight: 600;
    min-height: 48px; -webkit-tap-highlight-color: transparent;
  }
  .vid-btn { background: #21262d; color: #e6edf3; border: 2px solid #30363d; }
  .vid-btn.active { background: #1f6feb; border-color: #58a6ff; }
  .zone-btn { color: white; border: 3px solid transparent; }
  .zone-btn.active { box-shadow: 0 0 0 4px white inset; }
  button { background: #21262d; color: #e6edf3; border: 1px solid #30363d; }
  button.primary { background: #2da44e; border-color: #2da44e; color: white; }
  button:active { transform: scale(0.97); }
  .canvas-wrap { display: inline-block; background: #161b22; border-radius: 8px; padding: 6px; max-width: 100%; }
  canvas { display: block; touch-action: none; max-width: 100%; height: auto; cursor: crosshair; }
  .hint { font-size: 13px; color: #8b949e; line-height: 1.4; margin-top: 6px; }
  .meta-info { font-size: 12px; color: #8b949e; padding: 6px 10px; background: #161b22; border-radius: 8px; margin-top: 8px; }
  kbd { background: #30363d; padding: 1px 6px; border-radius: 4px; font-family: monospace; font-size: 12px; }
  .pen-status { font-size: 12px; color: #8b949e; padding: 4px 10px; background: #161b22; border-radius: 12px; display: inline-block; }
  .pen-status.active { color: #7ee787; }
</style>
</head>
<body>
<div class="row">
  <strong>Vídeo (preview):</strong>
  <div id="vids" style="display:flex;gap:6px;flex-wrap:wrap"></div>
</div>
<div class="row">
  <strong>Zona ativa:</strong>
  <div id="zones-pal" style="display:flex;gap:6px;flex-wrap:wrap"></div>
</div>
<div class="hint">
  Calibre <strong>uma vez só</strong> e a calibração serve para os 4 vídeos (offsets em frações da escala anatômica).
  Selecione uma zona e arraste com Apple Pencil sobre o frame. As demais zonas se adaptam automaticamente em cada vídeo.
  Atalhos: <kbd>1</kbd>=VOLANTE, <kbd>2</kbd>=CAMBIO, <kbd>3</kbd>=FREIO_MAO, <kbd>4</kbd>=PAINEL.
  <span class="pen-status" id="pen-status">aguardando entrada</span>
</div>
<div class="canvas-wrap"><canvas id="cv" width="640" height="360"></canvas></div>
<div class="row" style="margin-top:14px">
  <button onclick="resetDefaults()">Restaurar default</button>
  <button onclick="loadFromServer()">Recarregar</button>
  <button class="primary" onclick="save()">Salvar offsets</button>
  <a href="/calibrate" style="margin-left:8px;color:#58a6ff;text-decoration:none">calibração absoluta</a>
  <a href="/" style="margin-left:auto;color:#58a6ff;text-decoration:none">← revisão</a>
</div>
<div id="meta-info" class="meta-info"></div>

<script>
const VIDS = ['vid1','vid2','vid3','vid4'];
const ZONES = ['VOLANTE','CAMBIO','FREIO_MAO','PAINEL'];
const COLORS = {VOLANTE:'#00c800', CAMBIO:'#ffc800', FREIO_MAO:'#c864c8', PAINEL:'#ff6432'};

let currentVid = 'vid1';
let activeZone = 'VOLANTE';
let zonesRel = {};      // offsets relativos { VOLANTE: {anchor, scale, ox, oy, w, h}, ...}
let meta = {};          // {vid1: {kpts, scales, image}, ...}
let img = new Image();
let isDragging = false; let dragStart = null;
const cv = document.getElementById('cv');
const ctx = cv.getContext('2d');

// Calcula bbox absoluto a partir de zona relativa
function bboxAbs(zone, kpts, scales) {
  if (!kpts[zone.anchor]) return null;
  const B = scales[zone.scale];
  if (!B || B < 5) return null;
  const a = kpts[zone.anchor];
  const cx = a.x + zone.ox * B;
  const cy = a.y + zone.oy * B;
  const w = zone.w * B;
  const h = zone.h * B;
  return { x1: cx - w/2, y1: cy - h/2, x2: cx + w/2, y2: cy + h/2 };
}

// Calcula offsets relativos a partir de bbox absoluto + zona-config (mantém anchor/scale)
function bboxToRel(bbox, zoneCfg, kpts, scales) {
  const a = kpts[zoneCfg.anchor];
  const B = scales[zoneCfg.scale];
  const cx = (bbox.x1 + bbox.x2) / 2;
  const cy = (bbox.y1 + bbox.y2) / 2;
  return {
    anchor: zoneCfg.anchor,
    scale: zoneCfg.scale,
    ox: (cx - a.x) / B,
    oy: (cy - a.y) / B,
    w:  (bbox.x2 - bbox.x1) / B,
    h:  (bbox.y2 - bbox.y1) / B,
  };
}

function getCanvasPos(e) {
  const r = cv.getBoundingClientRect();
  return {
    x: (e.clientX - r.left) * (cv.width / r.width),
    y: (e.clientY - r.top)  * (cv.height / r.height)
  };
}

function showPenStatus(type) {
  const el = document.getElementById('pen-status');
  if (type === 'pen') { el.textContent = '✏️ Apple Pencil ativa'; el.classList.add('active'); }
  else if (type === 'touch') { el.textContent = '👆 Toque'; el.classList.add('active'); }
  else { el.textContent = '🖱 Mouse'; el.classList.add('active'); }
}

function renderTopBar() {
  const v = document.getElementById('vids');
  v.innerHTML = '';
  VIDS.forEach(vid => {
    const b = document.createElement('button');
    b.className = 'vid-btn' + (vid===currentVid?' active':'');
    b.textContent = vid;
    b.onclick = () => switchVideo(vid);
    v.appendChild(b);
  });
  const p = document.getElementById('zones-pal');
  p.innerHTML = '';
  ZONES.forEach(z => {
    const b = document.createElement('button');
    b.className = 'zone-btn' + (z===activeZone?' active':'');
    b.style.background = COLORS[z];
    b.style.borderColor = COLORS[z];
    b.textContent = z;
    b.onclick = () => { activeZone = z; renderTopBar(); };
    p.appendChild(b);
  });
  // info de meta
  const m = meta[currentVid];
  const info = document.getElementById('meta-info');
  if (m) {
    info.innerHTML = `${currentVid} · âncora=${ZONES.map(z => zonesRel[z]?.anchor || '?').join('/')} · escalas: B=${m.scales.biacromial.toFixed(0)}px · arm_d=${m.scales.arm_d_len.toFixed(0)}px · torso=${m.scales.torso_len.toFixed(0)}px`;
  } else {
    info.textContent = '';
  }
}

function draw() {
  ctx.clearRect(0,0,640,360);
  if (img.complete) ctx.drawImage(img, 0, 0, 640, 360);
  const m = meta[currentVid];
  if (!m) return;
  // desenha as 4 zonas calculadas
  for (const z of ZONES) {
    const cfg = zonesRel[z];
    if (!cfg) continue;
    const bb = bboxAbs(cfg, m.kpts, m.scales);
    if (!bb) continue;
    ctx.strokeStyle = COLORS[z];
    ctx.lineWidth = 3;
    ctx.fillStyle = COLORS[z] + '33';
    ctx.fillRect(bb.x1, bb.y1, bb.x2-bb.x1, bb.y2-bb.y1);
    ctx.strokeRect(bb.x1, bb.y1, bb.x2-bb.x1, bb.y2-bb.y1);
    ctx.fillStyle = COLORS[z];
    ctx.font = 'bold 14px sans-serif';
    ctx.fillText(z, bb.x1+4, bb.y1+18);
    // marcar âncora
    const a = m.kpts[cfg.anchor];
    if (a) {
      ctx.fillStyle = COLORS[z];
      ctx.beginPath(); ctx.arc(a.x, a.y, 5, 0, Math.PI*2); ctx.fill();
    }
  }
}

cv.addEventListener('pointerdown', e => {
  e.preventDefault();
  cv.setPointerCapture(e.pointerId);
  dragStart = getCanvasPos(e);
  isDragging = true;
  showPenStatus(e.pointerType);
});
cv.addEventListener('pointermove', e => {
  if (!isDragging) return;
  e.preventDefault();
  const p = getCanvasPos(e);
  draw();
  ctx.strokeStyle = COLORS[activeZone];
  ctx.lineWidth = 3; ctx.setLineDash([6,6]);
  ctx.strokeRect(dragStart.x, dragStart.y, p.x-dragStart.x, p.y-dragStart.y);
  ctx.setLineDash([]);
});
function endDrag(e) {
  if (!isDragging) return;
  e.preventDefault?.();
  const p = getCanvasPos(e);
  const x1 = Math.max(0, Math.min(dragStart.x, p.x));
  const y1 = Math.max(0, Math.min(dragStart.y, p.y));
  const x2 = Math.min(640, Math.max(dragStart.x, p.x));
  const y2 = Math.min(360, Math.max(dragStart.y, p.y));
  if (x2 - x1 > 5 && y2 - y1 > 5) {
    const m = meta[currentVid];
    if (m && m.kpts[zonesRel[activeZone].anchor]) {
      // converte bbox arrastado em offsets relativos
      zonesRel[activeZone] = bboxToRel({x1,y1,x2,y2}, zonesRel[activeZone], m.kpts, m.scales);
    }
  }
  isDragging = false;
  // pular pra próxima zona
  const idx = ZONES.indexOf(activeZone);
  activeZone = ZONES[(idx+1) % ZONES.length];
  renderTopBar(); draw();
}
cv.addEventListener('pointerup', endDrag);
cv.addEventListener('pointercancel', endDrag);
cv.addEventListener('pointerleave', e => { if (isDragging) endDrag(e); });
cv.addEventListener('touchstart', e => e.preventDefault(), {passive:false});
cv.addEventListener('touchmove',  e => e.preventDefault(), {passive:false});
cv.addEventListener('touchend',   e => e.preventDefault(), {passive:false});

document.addEventListener('keydown', e => {
  const map = {'1':'VOLANTE','2':'CAMBIO','3':'FREIO_MAO','4':'PAINEL'};
  if (map[e.key]) { activeZone = map[e.key]; renderTopBar(); }
});

function switchVideo(vid) {
  currentVid = vid;
  if (meta[vid]) {
    img.onload = () => draw();
    img.src = `/img/${meta[vid].image}?_=${Date.now()}`;
  }
  renderTopBar();
}

async function loadFromServer() {
  const r = await fetch('/api/calibrate-rel/state');
  const data = await r.json();
  zonesRel = data.zones;
  meta = data.meta;
  switchVideo(currentVid);
}

async function save() {
  const r = await fetch('/api/calibrate-rel/save', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ zones: zonesRel })
  });
  if (!r.ok) { alert('Erro ao salvar'); return; }
  alert('Offsets salvos! Vale pros 4 vídeos. ✅');
}

async function resetDefaults() {
  if (!confirm('Restaurar offsets default?')) return;
  await fetch('/api/calibrate-rel/reset', {method:'POST'});
  loadFromServer();
}

loadFromServer();
</script>
</body>
</html>
"""


DIAGRAMA_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VALBOT — Diagrama 2D simbólico</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0e1116; color: #e6edf3; font-family: -apple-system, sans-serif; padding: 12px; }
  h1 { font-size: 18px; margin-bottom: 10px; }
  .vids { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
  .vid-btn { padding: 10px 16px; border-radius: 8px; background: #21262d; border: 1px solid #30363d; color: #e6edf3; cursor: pointer; font-weight: 600; }
  .vid-btn.active { background: #1f6feb; border-color: #58a6ff; }
  .player-row {
    display: grid; grid-template-columns: 1.6fr 1.6fr 1fr;
    gap: 10px; align-items: stretch;
    width: 100%;
  }
  @media (max-width: 1100px) {
    .player-row { grid-template-columns: 1fr 1fr; }
    .player-cell.topdown { grid-column: 1 / -1; }
    .player-cell.topdown video { max-width: 400px; margin: 0 auto; }
  }
  .player-cell {
    background: #161b22; border-radius: 8px; padding: 8px;
    display: flex; flex-direction: column;
  }
  .player-cell h4 {
    font-size: 12px; color: #8b949e; margin-bottom: 6px;
    text-transform: uppercase; letter-spacing: 0.5px;
  }
  .player-cell video {
    width: 100%; height: auto; max-height: 60vh;
    border-radius: 6px; background: #000; display: block;
  }
  .controls {
    display: flex; gap: 8px; align-items: center;
    margin-top: 8px; flex-wrap: wrap;
  }
  .controls button { padding: 8px 14px; border-radius: 6px; border: 1px solid #30363d; background: #21262d; color: #e6edf3; cursor: pointer; font-weight: 600; min-height: 38px; }
  .controls button.primary { background: #2da44e; border-color: #2da44e; color: white; }
  .controls .time { color: #8b949e; font-family: monospace; font-size: 13px; margin-left: 8px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
  .card { background: #161b22; border-radius: 8px; padding: 12px; }
  .card h3 { font-size: 13px; color: #8b949e; margin-bottom: 6px; text-transform: uppercase; }
  .stat-row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 14px; }
  .stat-row .v { color: #7ee787; font-weight: 600; }
  .events { max-height: 220px; overflow-y: auto; font-family: monospace; font-size: 12px; }
  .events div { padding: 2px 0; color: #c9d1d9; cursor: pointer; }
  .events div:hover { background: #21262d; }
  a { color: #58a6ff; text-decoration: none; }
  @media (max-width:760px) {
    .player-row { grid-template-columns: 1fr; }
    .grid { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<h1>Diagrama 2D simbólico — vídeo real + esquema sincronizados</h1>
<div class="vids" id="vids"></div>

<div class="player-row">
  <div class="player-cell">
    <h4>🎥 vídeo real (interior — BL)</h4>
    <video id="v-real" controls playsinline preload="auto" muted></video>
  </div>
  <div class="player-cell">
    <h4>🧩 diagrama simbólico (mãos × zonas)</h4>
    <video id="v-sym" controls playsinline preload="auto"></video>
  </div>
  <div class="player-cell topdown">
    <h4>🚗 vista superior (estilo Tesla)</h4>
    <video id="v-top" controls playsinline preload="auto"></video>
  </div>
</div>

<div class="controls">
  <button class="primary" onclick="syncPlay()">▶ Play sincronizado</button>
  <button onclick="syncPause()">⏸ Pause</button>
  <button onclick="seek(-10)">−10s</button>
  <button onclick="seek(+10)">+10s</button>
  <button onclick="rewind()">↺ início</button>
  <span class="time" id="time-display">0.0s / 0s</span>
  <span class="time">drift: <span id="drift">0.00s</span></span>
</div>

<div class="grid">
  <div class="card">
    <h3>Mão D — direita</h3>
    <div id="stats-d"></div>
  </div>
  <div class="card">
    <h3>Mão E — esquerda</h3>
    <div id="stats-e"></div>
  </div>
</div>
<div class="card" style="margin-top:12px">
  <h3>Eventos (clique pra pular) — <span id="ev-count">0</span></h3>
  <div class="events" id="events"></div>
</div>
<p style="margin-top:12px;font-size:13px"><a href="/">← revisão</a> · <a href="/calibrate-rel">calibrar zonas</a></p>

<script>
const VIDS = ['vid1','vid2','vid3','vid4'];
let current = 'vid1';
const vReal = document.getElementById('v-real');
const vSym  = document.getElementById('v-sym');
const vTop  = document.getElementById('v-top');
const ALL = [vReal, vSym, vTop];

vReal.muted = false; vSym.muted = true; vTop.muted = true;

function syncPlay()  { ALL.forEach(v => v.play()); }
function syncPause() { ALL.forEach(v => v.pause()); }
function seek(delta) {
  const t = Math.max(0, vReal.currentTime + delta);
  ALL.forEach(v => v.currentTime = t);
}
function rewind() { ALL.forEach(v => v.currentTime = 0); }
function jumpTo(t) { ALL.forEach(v => { v.currentTime = t; v.play(); }); }

vReal.addEventListener('timeupdate', () => {
  const t = vReal.currentTime;
  const driftSym = Math.abs(t - vSym.currentTime);
  const driftTop = Math.abs(t - vTop.currentTime);
  if (driftSym > 0.4) vSym.currentTime = t;
  if (driftTop > 0.4) vTop.currentTime = t;
  document.getElementById('drift').textContent =
    `sym ${driftSym.toFixed(2)}s · top ${driftTop.toFixed(2)}s`;
  document.getElementById('time-display').textContent =
    `${t.toFixed(1)}s / ${(vReal.duration||0).toFixed(0)}s`;
});

// Cross-sync entre os 3
function bindCrossSync() {
  ALL.forEach(src => {
    src.addEventListener('play',   () => ALL.forEach(o => { if (o!==src && o.paused) o.play(); }));
    src.addEventListener('pause',  () => ALL.forEach(o => { if (o!==src && !o.paused) o.pause(); }));
    src.addEventListener('seeked', () => ALL.forEach(o => { if (o!==src) o.currentTime = src.currentTime; }));
  });
}
bindCrossSync();

async function load(vid) {
  current = vid;
  document.querySelectorAll('.vid-btn').forEach(b => b.classList.toggle('active', b.dataset.vid === vid));
  const r = await fetch(`/api/diagrama/${vid}`);
  if (!r.ok) {
    document.getElementById('events').innerHTML = `<div style="color:#f85149">Diagrama de ${vid} ainda não gerado</div>`;
    vReal.src = ''; vSym.src = '';
    document.getElementById('stats-d').innerHTML = '';
    document.getElementById('stats-e').innerHTML = '';
    return;
  }
  const data = await r.json();
  vSym.src = data.mp4_url;
  vReal.src = data.real_url || data.mp4_url;
  vTop.src = data.topdown_url || '';
  vSym.load(); vReal.load(); vTop.load();
  // stats
  const sd = document.getElementById('stats-d');
  sd.innerHTML = Object.entries(data.resumo.mao_D_por_zona)
    .map(([k,v]) => `<div class="stat-row"><span>${k}</span><span class="v">${v}</span></div>`).join('');
  const se = document.getElementById('stats-e');
  se.innerHTML = Object.entries(data.resumo.mao_E_por_zona)
    .map(([k,v]) => `<div class="stat-row"><span>${k}</span><span class="v">${v}</span></div>`).join('');
  // eventos clicáveis
  document.getElementById('ev-count').textContent = data.eventos.length;
  const ev = document.getElementById('events');
  ev.innerHTML = data.eventos.map(e =>
    `<div onclick="jumpTo(${e.ts})">${e.ts.toFixed(1)}s · mao_${e.hand} · ${e.from} → ${e.to}</div>`
  ).join('');
}

const vbar = document.getElementById('vids');
VIDS.forEach(v => {
  const b = document.createElement('button');
  b.className = 'vid-btn' + (v===current?' active':'');
  b.textContent = v; b.dataset.vid = v;
  b.onclick = () => load(v);
  vbar.appendChild(b);
});
load(current);
</script>
</body>
</html>
"""


LAUDOS_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VALBOT — Laudos finais</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0e1116; color: #e6edf3; font-family: -apple-system, sans-serif; padding: 12px; }
  h1 { font-size: 20px; margin-bottom: 8px; }
  .nav { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .nav a { padding: 8px 14px; border-radius: 6px; background: #21262d; color: #58a6ff; text-decoration: none; font-size: 14px; }
  .nav a:hover { background: #30363d; }
  .vids { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .vid-btn { padding: 10px 18px; border-radius: 8px; background: #21262d; border: 1px solid #30363d; color: #e6edf3; cursor: pointer; font-weight: 600; }
  .vid-btn.active { background: #1f6feb; border-color: #58a6ff; }
  .laudo-img { display: block; max-width: 100%; border-radius: 8px; box-shadow: 0 4px 24px rgba(0,0,0,0.5); }
  .summary { background: #161b22; border-radius: 8px; padding: 14px; margin-top: 16px; }
  .summary h3 { font-size: 14px; color: #8b949e; margin-bottom: 10px; text-transform: uppercase; }
  .stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
  .stat { padding: 12px; background: #21262d; border-radius: 6px; }
  .stat .label { font-size: 11px; color: #8b949e; text-transform: uppercase; }
  .stat .value { font-size: 22px; font-weight: bold; margin-top: 4px; }
  .infr-list { font-family: monospace; font-size: 12px; color: #c9d1d9; }
</style>
</head>
<body>
<h1>📋 Laudos finais — Iteração 4 (detectores reais)</h1>
<div class="nav">
  <a href="/">← revisão</a>
  <a href="/diagrama">diagrama 2D</a>
  <a href="/calibrate-rel">calibrar zonas</a>
  <a href="/debug">modo debug</a>
</div>
<div class="vids" id="vids"></div>
<img id="laudo-img" class="laudo-img" src="">
<div class="summary" id="summary"></div>

<script>
const VIDS = ['vid1','vid2','vid3','vid4'];
let current = 'vid1';
let LAUDOS = {};

async function loadAll() {
  const r = await fetch('/api/laudos');
  const data = await r.json();
  LAUDOS = data.laudos;
  show(current);
}

function show(vid) {
  current = vid;
  document.querySelectorAll('.vid-btn').forEach(b => b.classList.toggle('active', b.dataset.vid === vid));
  document.getElementById('laudo-img').src = `/img/simulacoes/${vid}_laudo.jpg?_=${Date.now()}`;
  const l = LAUDOS[vid];
  if (!l) { document.getElementById('summary').innerHTML = ''; return; }
  document.getElementById('summary').innerHTML = `
    <h3>Detalhes técnicos · ${vid}</h3>
    <div class="stat-grid">
      <div class="stat"><div class="label">veredito</div><div class="value" style="color:${l.aprovado?'#2da44e':'#cf222e'}">${l.aprovado?'APROVADO':'REPROVADO'}</div></div>
      <div class="stat"><div class="label">pontuação</div><div class="value">${l.pontuacao} / 10</div></div>
      <div class="stat"><div class="label">duração</div><div class="value">${l.duracao_s.toFixed(0)}s</div></div>
      <div class="stat"><div class="label">infrações</div><div class="value">${l.infracoes.length}</div></div>
      <div class="stat"><div class="label">obs. atenção</div><div class="value">${l.n_observacoes}</div></div>
      <div class="stat"><div class="label">avaliações</div><div class="value">${l.avaliacoes.length}</div></div>
    </div>
    <h3 style="margin-top:14px">Avaliações</h3>
    <div class="infr-list">${l.avaliacoes.map(a => '· ' + JSON.stringify(a, null, 0)).join('<br>')}</div>
  `;
}

const vbar = document.getElementById('vids');
VIDS.forEach(v => {
  const b = document.createElement('button');
  b.className = 'vid-btn' + (v===current?' active':'');
  b.textContent = v; b.dataset.vid = v;
  b.onclick = () => show(v);
  vbar.appendChild(b);
});
loadAll();
</script>
</body>
</html>
"""


DEBUG_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VALBOT — modo debug</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0e1116; color: #e6edf3; font-family: -apple-system, sans-serif; padding: 10px; }
  h1 { font-size: 18px; margin-bottom: 6px; }
  .nav { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
  .nav a { padding: 6px 12px; border-radius: 6px; background: #21262d; color: #58a6ff; text-decoration: none; font-size: 13px; }
  .vids { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
  .vid-btn { padding: 10px 16px; border-radius: 8px; background: #21262d; border: 1px solid #30363d; color: #e6edf3; cursor: pointer; font-weight: 600; }
  .vid-btn.active { background: #1f6feb; border-color: #58a6ff; }
  .grid {
    display: grid; grid-template-columns: 1.6fr 1.6fr 1fr;
    gap: 8px;
  }
  .cell { background: #161b22; border-radius: 8px; padding: 6px; }
  .cell h4 { font-size: 11px; color: #8b949e; margin-bottom: 4px; text-transform: uppercase; }
  .cell video, .cell img { display: block; width: 100%; height: auto; max-height: 50vh; border-radius: 4px; background: #000; }
  .cell.full { grid-column: 1 / -1; }
  .controls { display: flex; gap: 6px; margin: 8px 0; flex-wrap: wrap; align-items: center; }
  .controls button { padding: 8px 14px; border-radius: 6px; border: 1px solid #30363d; background: #21262d; color: #e6edf3; cursor: pointer; font-weight: 600; }
  .controls .primary { background: #2da44e; border-color: #2da44e; color: white; }
  .time { color: #8b949e; font-family: monospace; font-size: 12px; }
  @media (max-width: 1100px) {
    .grid { grid-template-columns: 1fr 1fr; }
    .cell.tesla { grid-column: 1 / -1; }
  }
</style>
</head>
<body>
<h1>🐛 Modo debug — todas as visualizações sincronizadas</h1>
<div class="nav">
  <a href="/">← revisão</a>
  <a href="/diagrama">diagrama 2D</a>
  <a href="/laudos">laudos</a>
  <a href="/calibrate-rel">calibrar zonas</a>
</div>
<div class="vids" id="vids"></div>

<div class="grid">
  <div class="cell"><h4>🎥 Real (interior BL)</h4><video id="v-real" controls playsinline preload="auto"></video></div>
  <div class="cell"><h4>🧩 Diagrama 2D (mãos × zonas)</h4><video id="v-sym" controls playsinline preload="auto" muted></video></div>
  <div class="cell tesla"><h4>🚗 Vista superior Tesla</h4><video id="v-top" controls playsinline preload="auto" muted></video></div>
  <div class="cell full"><h4>📋 Laudo gerado (iteração 4)</h4><img id="laudo-img" src=""></div>
</div>

<div class="controls">
  <button class="primary" onclick="syncPlay()">▶ Play tudo</button>
  <button onclick="syncPause()">⏸ Pause</button>
  <button onclick="seek(-10)">−10s</button>
  <button onclick="seek(+10)">+10s</button>
  <button onclick="rewind()">↺</button>
  <span class="time" id="td">0s/0s</span>
</div>

<script>
const VIDS = ['vid1','vid2','vid3','vid4'];
let current = 'vid1';
const vReal = document.getElementById('v-real');
const vSym = document.getElementById('v-sym');
const vTop = document.getElementById('v-top');
const ALL = [vReal, vSym, vTop];

function syncPlay()  { ALL.forEach(v => v.play()); }
function syncPause() { ALL.forEach(v => v.pause()); }
function seek(d)     { const t = Math.max(0, vReal.currentTime + d); ALL.forEach(v => v.currentTime = t); }
function rewind()    { ALL.forEach(v => v.currentTime = 0); }

vReal.addEventListener('timeupdate', () => {
  const t = vReal.currentTime;
  if (Math.abs(t - vSym.currentTime) > 0.4) vSym.currentTime = t;
  if (Math.abs(t - vTop.currentTime) > 0.4) vTop.currentTime = t;
  document.getElementById('td').textContent =
    `${t.toFixed(1)}s / ${(vReal.duration||0).toFixed(0)}s`;
});
ALL.forEach(src => {
  src.addEventListener('play',   () => ALL.forEach(o => { if (o!==src && o.paused) o.play(); }));
  src.addEventListener('pause',  () => ALL.forEach(o => { if (o!==src && !o.paused) o.pause(); }));
  src.addEventListener('seeked', () => ALL.forEach(o => { if (o!==src) o.currentTime = src.currentTime; }));
});

async function load(vid) {
  current = vid;
  document.querySelectorAll('.vid-btn').forEach(b => b.classList.toggle('active', b.dataset.vid === vid));
  const r = await fetch(`/api/diagrama/${vid}`);
  if (!r.ok) return;
  const d = await r.json();
  vReal.src = d.real_url || d.mp4_url;
  vSym.src = d.mp4_url;
  vTop.src = d.topdown_url || '';
  ALL.forEach(v => v.load());
  document.getElementById('laudo-img').src = `/img/simulacoes/${vid}_laudo.jpg?_=${Date.now()}`;
}

const vbar = document.getElementById('vids');
VIDS.forEach(v => {
  const b = document.createElement('button');
  b.className = 'vid-btn' + (v===current?' active':'');
  b.textContent = v; b.dataset.vid = v;
  b.onclick = () => load(v);
  vbar.appendChild(b);
});
load(current);
</script>
</body>
</html>
"""


ANOTAR_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>VALBOT — anotação manual</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-touch-callout: none; user-select: none; }
  html, body { overscroll-behavior: none; touch-action: manipulation; }
  body { background: #0e1116; color: #e6edf3; font-family: -apple-system, sans-serif; padding: 10px; }
  h1 { font-size: 17px; margin-bottom: 8px; }
  .nav { display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
  .nav a, .nav .vid { padding: 6px 12px; border-radius: 6px; background: #21262d; color: #58a6ff; text-decoration: none; font-size: 13px; cursor: pointer; border: none; font-family: inherit; }
  .nav .vid { color: #e6edf3; border: 1px solid #30363d; }
  .nav .vid.active { background: #1f6feb; border-color: #58a6ff; }
  .layout { display: grid; grid-template-columns: 1fr 320px; gap: 10px; }
  @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
  .video-wrap { position: relative; background: #161b22; border-radius: 8px; padding: 6px; }
  .stage { position: relative; display: inline-block; line-height: 0; }
  .stage img { display: block; width: 100%; height: auto; max-height: 70vh; border-radius: 4px; background: #000; user-select: none; -webkit-user-drag: none; pointer-events: none; }
  canvas {
    position: absolute; top: 0; left: 0; width: 100%; height: 100%;
    cursor: crosshair; touch-action: none;
  }
  .slider { width: 100%; margin-top: 6px; }
  input[type=range] { width: 100%; height: 32px; }
  .controls { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; align-items: center; }
  .controls button {
    padding: 10px 14px; border-radius: 8px; border: 1px solid #30363d; background: #21262d;
    color: #e6edf3; cursor: pointer; font-weight: 600; min-height: 44px;
    -webkit-tap-highlight-color: transparent;
  }
  .controls button.primary { background: #2da44e; border-color: #2da44e; color: white; }
  .controls .time { color: #8b949e; font-family: monospace; font-size: 13px; margin-left: 6px; }
  .labels { display: flex; gap: 4px; flex-wrap: wrap; margin: 8px 0; }
  .label-btn {
    padding: 8px 12px; border-radius: 6px; border: 2px solid;
    cursor: pointer; font-size: 12px; font-weight: 600; min-height: 38px;
    -webkit-tap-highlight-color: transparent;
  }
  .label-btn.active { box-shadow: 0 0 0 3px white inset; }
  .panel { background: #161b22; border-radius: 8px; padding: 10px; max-height: 80vh; overflow-y: auto; }
  .panel h3 { font-size: 12px; color: #8b949e; margin-bottom: 6px; text-transform: uppercase; }
  .annot-item {
    padding: 8px; border-radius: 6px; background: #21262d; margin-bottom: 4px;
    font-size: 12px; cursor: pointer; display: flex; justify-content: space-between; align-items: center;
  }
  .annot-item:hover { background: #30363d; }
  .annot-item .label-tag { padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
  .annot-item .x { color: #f85149; padding: 0 4px; cursor: pointer; }
  .hint { font-size: 11px; color: #8b949e; line-height: 1.4; margin-top: 6px; }
</style>
</head>
<body>
<h1>🖍 Anotação manual frame-a-frame</h1>
<div class="nav">
  <a href="/debug">debug</a>
  <a href="/diagrama">diagrama</a>
  <a href="/laudos">laudos</a>
  <a href="/">revisão</a>
  &nbsp;|&nbsp;
  <button class="vid" data-vid="vid1">vid1</button>
  <button class="vid" data-vid="vid2">vid2</button>
  <button class="vid" data-vid="vid3">vid3</button>
  <button class="vid" data-vid="vid4">vid4</button>
</div>

<div class="layout">
  <div class="video-wrap">
    <div class="stage" id="stage">
      <img id="frame-img" src="" alt="">
      <canvas id="cv"></canvas>
    </div>
    <input type="range" class="slider" id="slider" min="1" max="1" value="1" step="1">
    <div class="controls">
      <button onclick="goFrame(-50)">⏮ −10s</button>
      <button onclick="goFrame(-5)">−1s</button>
      <button onclick="goFrame(-1)">−0.2s</button>
      <button id="play-btn" onclick="togglePlay()">▶</button>
      <button onclick="goFrame(+1)">+0.2s</button>
      <button onclick="goFrame(+5)">+1s</button>
      <button onclick="goFrame(+50)">+10s ⏭</button>
      <span class="time" id="td">0.00s / 0s · frame 1/1</span>
    </div>
    <div class="labels" id="labels"></div>
    <button class="primary" onclick="saveAnnot()" id="save-btn" disabled>Salvar anotação atual</button>
    <div class="hint">
      Pause o vídeo, arraste no frame pra desenhar a box, escolha um label, e salve.
      Atalhos: <kbd>space</kbd>=play/pause, <kbd>1-9</kbd>=label, <kbd>S</kbd>=salvar, <kbd>delete</kbd>=limpar box.
    </div>
  </div>

  <div class="panel">
    <h3>Anotações deste vídeo (<span id="count">0</span>)</h3>
    <div id="annot-list"></div>
  </div>
</div>

<script>
// Labels propostos pelo análise — flexíveis, podem ser refinados
const LABELS = [
  {key: 'VOLANTE',         color: '#00c800'},
  {key: 'CAMBIO',          color: '#ffc800'},
  {key: 'FREIO_MAO',       color: '#c864c8'},
  {key: 'PAINEL_RADIO',    color: '#ff6432'},
  {key: 'CHAVE_IGNICAO',   color: '#ff64ff'},
  {key: 'PEITO_COLO',      color: '#80c0ff'},
  {key: 'JANELA_LATERAL',  color: '#80ff80'},
  {key: 'BAIXO_FRAME',     color: '#888888'},
  {key: 'OUTRO',           color: '#cccccc'},
];

const FPS = 5;
let currentVid = 'vid1';
let totalFrames = 1;
let curFrame = 1;
let activeLabel = LABELS[0];
let currentBox = null;
let isDragging = false; let dragStart = null;
let allAnnots = [];
let playInterval = null;

const img = document.getElementById('frame-img');
const slider = document.getElementById('slider');
const cv = document.getElementById('cv');
const ctx = cv.getContext('2d');

function syncCanvasSize() {
  cv.width = img.clientWidth;
  cv.height = img.clientHeight;
  draw();
}
img.addEventListener('load', syncCanvasSize);
window.addEventListener('resize', syncCanvasSize);

function setFrame(n) {
  curFrame = Math.max(1, Math.min(totalFrames, n));
  const padded = String(curFrame).padStart(5, '0');
  img.src = `/img/anotar_seq/${currentVid}/f${padded}.jpg`;
  slider.value = curFrame;
  const ts = (curFrame - 1) / FPS;
  document.getElementById('td').textContent =
    `${ts.toFixed(2)}s / ${((totalFrames-1)/FPS).toFixed(0)}s · frame ${curFrame}/${totalFrames}`;
}

function goFrame(d) { setFrame(curFrame + d); stopPlay(); }
function togglePlay() {
  if (playInterval) stopPlay(); else startPlay();
}
function startPlay() {
  document.getElementById('play-btn').textContent = '⏸';
  playInterval = setInterval(() => {
    if (curFrame >= totalFrames) { stopPlay(); return; }
    setFrame(curFrame + 1);
  }, 1000/FPS);
}
function stopPlay() {
  if (playInterval) clearInterval(playInterval);
  playInterval = null;
  document.getElementById('play-btn').textContent = '▶';
}
slider.addEventListener('input', () => setFrame(parseInt(slider.value)));

function getPos(e) {
  const r = cv.getBoundingClientRect();
  return { x: e.clientX - r.left, y: e.clientY - r.top };
}

cv.addEventListener('pointerdown', e => {
  e.preventDefault();
  cv.setPointerCapture(e.pointerId);
  stopPlay();
  dragStart = getPos(e);
  isDragging = true;
});
cv.addEventListener('pointermove', e => {
  if (!isDragging) return;
  e.preventDefault();
  const p = getPos(e);
  draw();
  ctx.strokeStyle = activeLabel.color;
  ctx.lineWidth = 3; ctx.setLineDash([6,6]);
  ctx.strokeRect(dragStart.x, dragStart.y, p.x-dragStart.x, p.y-dragStart.y);
  ctx.setLineDash([]);
});
function endDrag(e) {
  if (!isDragging) return;
  e.preventDefault?.();
  const p = getPos(e);
  const x1 = Math.max(0, Math.min(dragStart.x, p.x));
  const y1 = Math.max(0, Math.min(dragStart.y, p.y));
  const x2 = Math.min(cv.width, Math.max(dragStart.x, p.x));
  const y2 = Math.min(cv.height, Math.max(dragStart.y, p.y));
  if (x2 - x1 > 8 && y2 - y1 > 8) {
    // Converter pra coords reais 640x360 do BL
    // Vídeo é 640x360 mas exibido em qualquer tamanho — usar proporção
    const sx = 640 / cv.width;
    const sy = 360 / cv.height;
    currentBox = {
      x1: Math.round(x1 * sx), y1: Math.round(y1 * sy),
      x2: Math.round(x2 * sx), y2: Math.round(y2 * sy),
    };
    document.getElementById('save-btn').disabled = false;
  }
  isDragging = false;
  draw();
}
cv.addEventListener('pointerup', endDrag);
cv.addEventListener('pointercancel', endDrag);

function draw() {
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (currentBox) {
    const sx = cv.width / 640;
    const sy = cv.height / 360;
    const x1 = currentBox.x1 * sx;
    const y1 = currentBox.y1 * sy;
    const w = (currentBox.x2 - currentBox.x1) * sx;
    const h = (currentBox.y2 - currentBox.y1) * sy;
    ctx.strokeStyle = activeLabel.color;
    ctx.lineWidth = 3;
    ctx.fillStyle = activeLabel.color + '33';
    ctx.fillRect(x1, y1, w, h);
    ctx.strokeRect(x1, y1, w, h);
    ctx.fillStyle = activeLabel.color;
    ctx.font = 'bold 14px sans-serif';
    ctx.fillText(activeLabel.key, x1 + 4, y1 + 16);
  }
}

function renderLabels() {
  const c = document.getElementById('labels');
  c.innerHTML = '';
  LABELS.forEach((L, i) => {
    const b = document.createElement('button');
    b.className = 'label-btn' + (L.key === activeLabel.key ? ' active' : '');
    b.style.background = L.color;
    b.style.color = '#000';
    b.style.borderColor = L.color;
    b.textContent = `${i+1}. ${L.key}`;
    b.onclick = () => { activeLabel = L; renderLabels(); draw(); };
    c.appendChild(b);
  });
}

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === ' ') { e.preventDefault(); togglePlay(); }
  if (e.key === 'ArrowLeft') goFrame(-1);
  if (e.key === 'ArrowRight') goFrame(+1);
  if (e.key === 'Delete' || e.key === 'Backspace') { currentBox = null; draw(); document.getElementById('save-btn').disabled = true; }
  if (e.key === 's' || e.key === 'S') saveAnnot();
  const idx = parseInt(e.key) - 1;
  if (idx >= 0 && idx < LABELS.length) {
    activeLabel = LABELS[idx]; renderLabels(); draw();
  }
});

async function saveAnnot() {
  if (!currentBox) return;
  const ts = (curFrame - 1) / FPS;
  await fetch('/api/anotacoes', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      video: currentVid,
      ts: ts,
      box: [currentBox.x1, currentBox.y1, currentBox.x2, currentBox.y2],
      label: activeLabel.key,
    })
  });
  currentBox = null;
  document.getElementById('save-btn').disabled = true;
  draw();
  await loadAnnots();
}

async function loadAnnots() {
  const r = await fetch(`/api/anotacoes?video=${currentVid}`);
  const d = await r.json();
  allAnnots = d.annotations;
  document.getElementById('count').textContent = allAnnots.length;
  const list = document.getElementById('annot-list');
  list.innerHTML = '';
  allAnnots.forEach((a, i) => {
    const lbl = LABELS.find(L => L.key === a.label) || LABELS[LABELS.length-1];
    const div = document.createElement('div');
    div.className = 'annot-item';
    div.innerHTML = `
      <div onclick="setFrame(${Math.round(a.ts * FPS) + 1})">
        <span class="time">${a.ts.toFixed(2)}s</span>
        &nbsp;<span class="label-tag" style="background:${lbl.color};color:#000">${a.label}</span>
      </div>
      <span class="x" onclick="event.stopPropagation();delAnnot(${i})">✗</span>
    `;
    list.appendChild(div);
  });
}

async function delAnnot(idx) {
  await fetch(`/api/anotacoes?video=${currentVid}&idx=${idx}`, {method:'DELETE'});
  await loadAnnots();
}

async function loadVideo(vid) {
  currentVid = vid;
  document.querySelectorAll('.nav .vid').forEach(b => b.classList.toggle('active', b.dataset.vid === vid));
  stopPlay();
  // pegar quantos frames a sequência tem
  const r = await fetch(`/api/anotar/frames/${vid}`);
  const d = await r.json();
  totalFrames = d.total || 1;
  slider.max = totalFrames;
  setFrame(1);
  currentBox = null;
  document.getElementById('save-btn').disabled = true;
  loadAnnots();
}

document.querySelectorAll('.nav .vid').forEach(b => {
  b.onclick = () => loadVideo(b.dataset.vid);
});

renderLabels();
loadVideo('vid1');
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn

    print("VALBOT Review        → http://localhost:8003")
    print("Calibração ABSOLUTA → http://localhost:8003/calibrate")
    print("Calibração RELATIVA → http://localhost:8003/calibrate-rel")
    print("Diagrama 2D         → http://localhost:8003/diagrama")
    print("Laudos finais       → http://localhost:8003/laudos")
    print("Modo debug          → http://localhost:8003/debug")
    print("Anotação manual     → http://localhost:8003/anotar")
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="warning")
