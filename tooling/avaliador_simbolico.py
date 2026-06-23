"""
Avaliador IA simbólico — fecha o loop dos candidatos R1020-G-a SEM ver imagem.

Executa o protocolo da feedback_filosofia_central.md:
  1. Lê candidatos confiáveis + suspeitos do result.json (R1020-G-a).
  2. Agrupa em "eventos" temporais (Δt ≤ 5s entre vizinhos).
  3. Pra cada evento, gera um "gráfico simbólico" (números + texto, zero pixel).
  4. Aplica regras determinísticas locais e decide:
        - refuted        → assinatura de ruído (cluster pequeno isolado etc)
        - inconclusive   → plausível mas exige sensor de velocidade pra fechar
        - (silêncio)     → evento sem assinatura clara, deixa pro humano
  5. Persiste cada decisão via POST /api/analyses/<hash>/training-example.
  6. Retroalimenta filtrar_yolo_com_votos + _candidatos_cv no próximo run.

Uso:
    .venv/bin/python -m tooling.avaliador_simbolico --hash <h>
    .venv/bin/python -m tooling.avaliador_simbolico --all      # 4 vídeos do dataset
    .venv/bin/python -m tooling.avaliador_simbolico --all --dry-run  # só imprime
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import cv2
import httpx
import numpy as np

from src.detectors.stop_detector import StopDetector
from src.ingestion.grid_slicer import GridSlicer

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "storage"
ANALYSES = STORAGE / "analyses"
BACKEND = "http://127.0.0.1:8001"

DATASET = {
    "1.mp4": "2f8c79895388f4674cc737afc7cbaab2430175d70616eebf152ce7e3f81e0ce4",
    "2.mp4": "ef960aa49ebb560572bc380838c9a568d6ed139f53a8babc4430db177fb24fbd",
    "3.mp4": "f7c9e3095ab56b117f6fac5f681ef0c2e0cc069b2e0488b166500e669439b06f",
    "4.mp4": "19d72ba460e2ddb300f796306fc8a5c4e1a41e4d3fa60cc96b0b5677151753a4",
}


# ============================================================================
# Coletor — extrai candidatos R1020-G-a normalizados
# ============================================================================


def _origem(d: dict) -> str:
    """Devolve "yolo:stop_sign" / "cv:road_text" / etc, normalizado."""
    if d.get("origem"):
        return str(d["origem"])
    cls = (d.get("class_name") or "").lower()
    if cls in ("stop sign", "traffic light"):
        return f"yolo:{cls.replace(' ', '_')}"
    return "yolo:unknown"


def coletar_candidatos(hash_: str) -> list[dict]:
    """Lê result.json e devolve confiáveis ∪ suspeitos da R1020-G-a, ordenados por ts."""
    path = ANALYSES / hash_ / "result.json"
    if not path.exists():
        return []
    r = json.loads(path.read_text())
    inf = next((x for x in r["infracoes_avaliadas"] if x["id"] == "R1020-G-a"), None)
    if not inf:
        return []

    raw = list(inf.get("candidatos_confiavel", [])) + list(inf.get("candidatos_suspeito", []))
    out = []
    for d in raw:
        ts = d.get("timestamp_s") or d.get("ts")
        if ts is None:
            continue
        out.append(
            {
                "ts": float(ts),
                "frame_idx": d.get("frame_idx"),
                "bbox": d.get("bbox") or [0, 0, 0, 0],
                "confidence": float(d.get("confidence") or 0.0),
                "class_name": d.get("class_name", ""),
                "origem": _origem(d),
                "evidence": d.get("evidence", ""),
                "cluster_size": int(d.get("cluster_size") or 1),
            }
        )
    out.sort(key=lambda x: x["ts"])
    return out


# ============================================================================
# Resumidor — agrupa em eventos temporais
# ============================================================================


@dataclass
class Evento:
    evento_id: str
    hash_: str
    ts_inicio: float
    ts_fim: float
    n_frames: int
    fontes: dict[str, int]  # {"cv:road_text": 4, ...}
    bbox_resumo: dict
    confidence: dict
    narrativa: str
    candidatos: list[dict] = field(default_factory=list)

    @property
    def duracao_s(self) -> float:
        return round(self.ts_fim - self.ts_inicio, 2)


def _quadrante(cx: float, cy: float, w: int = 640, h: int = 360) -> str:
    """Discretiza centro em 9 zonas do quadrante TL (frontal)."""
    horiz = "esq" if cx < w / 3 else ("centro" if cx < 2 * w / 3 else "dir")
    vert = "alta" if cy < h / 3 else ("media" if cy < 2 * h / 3 else "baixa")
    return f"{horiz}_{vert}"


def agrupar_em_eventos(candidatos: list[dict], hash_: str, gap_s: float = 5.0) -> list[Evento]:
    if not candidatos:
        return []
    eventos: list[Evento] = []
    cur: list[dict] = [candidatos[0]]
    for c in candidatos[1:]:
        if c["ts"] - cur[-1]["ts"] <= gap_s:
            cur.append(c)
        else:
            eventos.append(_resumir(cur, hash_, len(eventos) + 1))
            cur = [c]
    eventos.append(_resumir(cur, hash_, len(eventos) + 1))
    return eventos


def _resumir(grupo: list[dict], hash_: str, n: int) -> Evento:
    fontes = Counter(c["origem"] for c in grupo)
    confs = [c["confidence"] for c in grupo]
    bbs = [c["bbox"] for c in grupo if c["bbox"] and any(c["bbox"])]
    if bbs:
        cxs = [(b[0] + b[2]) / 2 for b in bbs]
        cys = [(b[1] + b[3]) / 2 for b in bbs]
        areas = [max(0, (b[2] - b[0]) * (b[3] - b[1])) for b in bbs]
        bbox_resumo = {
            "n_distintos": len({(round(b[0] / 15), round(b[1] / 15)) for b in bbs}),
            "centro_x_medio": round(sum(cxs) / len(cxs)),
            "centro_y_medio": round(sum(cys) / len(cys)),
            "area_px_max": int(max(areas)) if areas else 0,
            "area_px_media": int(sum(areas) / len(areas)) if areas else 0,
            "regiao": _quadrante(sum(cxs) / len(cxs), sum(cys) / len(cys)),
        }
    else:
        bbox_resumo = {"n_distintos": 0, "regiao": "?"}

    # Narrativa textual curta — feita pra humanos lerem o examples.jsonl depois
    partes = []
    for fonte, cnt in fontes.most_common():
        partes.append(f"{fonte} × {cnt}")
    narrativa = " + ".join(partes)
    if grupo[0].get("cluster_size", 1) >= 3:
        narrativa += f" (yolo cluster size {grupo[0]['cluster_size']})"

    return Evento(
        evento_id=f"{hash_[:8]}_e{n:02d}",
        hash_=hash_,
        ts_inicio=round(grupo[0]["ts"], 2),
        ts_fim=round(grupo[-1]["ts"], 2),
        n_frames=len(grupo),
        fontes=dict(fontes),
        bbox_resumo=bbox_resumo,
        confidence={
            "max": round(max(confs), 3),
            "media": round(sum(confs) / len(confs), 3),
            "min": round(min(confs), 3),
        },
        narrativa=narrativa,
        candidatos=grupo,
    )


# ============================================================================
# Verificador de parada — Princípio 2: âncora visual via optical flow
# ============================================================================
#
# Em vez de OBD2/GPS, usa o que o usuário propôs: ancorar em pontos fixos do
# entorno (placa, asfalto, postes). Se as âncoras NÃO se mexem entre frames
# consecutivos = veículo parado. Cruza frontal (TL) + traseira (BR) como
# duas fontes independentes — paisagem nas duas tem que congelar pra dar OK.

_STOP = StopDetector(motion_threshold=0.8, min_stop_duration_s=0.8)


def _frame_at(cap: cv2.VideoCapture, fps: float, ts: float) -> np.ndarray | None:
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(ts * fps)))
    ok, f = cap.read()
    return f if ok else None


def _split_quadrant(frame: np.ndarray, quad: str) -> np.ndarray:
    """quad in {'TL','TR','BL','BR'}. Recorta o quadrante absoluto do grid 2x2."""
    h, w = frame.shape[:2]
    hh, hw = h // 2, w // 2
    if quad == "TL":
        return frame[:hh, :hw]
    if quad == "TR":
        return frame[:hh, hw:]
    if quad == "BL":
        return frame[hh:, :hw]
    return frame[hh:, hw:]


# cache: hash do path → slicer (auto-detecta layout 1x por vídeo)
_SLICER_CACHE: dict[str, GridSlicer] = {}


def _get_slicer(video_path: Path) -> GridSlicer:
    key = str(video_path)
    if key not in _SLICER_CACHE:
        _SLICER_CACHE[key] = GridSlicer(video_path, sample_fps=0.0)
    return _SLICER_CACHE[key]


@dataclass
class MotionCheck:
    parou_frontal: bool
    parou_traseira: bool
    dur_max_s: float
    fps_amostra: float
    n_frames: int
    narrativa: str


def verificar_parada(
    video_path: Path,
    ts_inicio: float,
    ts_fim: float,
    pad_pre: float = 3.0,
    pad_pos: float = 5.0,
    sample_fps: float = 4.0,
    max_frames: int = 80,
) -> MotionCheck | None:
    """
    Extrai janela [ts_inicio - pad_pre, ts_fim + pad_pos] no vídeo,
    amostra `sample_fps` frames/s (cap em max_frames pra evitar
    explosão de RAM em eventos longos), roda StopDetector na frontal (TL)
    e na traseira (BR). Devolve o que cada câmera diz.
    """
    if not video_path.exists():
        print(f"  [motion] vídeo não existe: {video_path}")
        return None
    try:
        slicer = _get_slicer(video_path)
        # quadrantes da câmera frontal e traseira_esq conforme layout
        # detectado (VIP Intelbras: TL/BR; Hikvision: TR/BL)
        front_quad = slicer.quadrant_for("frontal")
        back_quad = slicer.quadrant_for("traseira_esq")

        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        t0 = max(0.0, ts_inicio - pad_pre)
        t1 = min(total / fps if fps else ts_fim + pad_pos, ts_fim + pad_pos)
        if t1 - t0 < 1.0:
            cap.release()
            print(f"  [motion] janela curta demais: {t0:.1f}-{t1:.1f}")
            return None

        n_full = max(2, int((t1 - t0) * sample_fps))
        n = min(n_full, max_frames)
        timestamps = [t0 + i * (t1 - t0) / (n - 1) for i in range(n)]

        frontal_frames: list[np.ndarray] = []
        traseira_frames: list[np.ndarray] = []
        for ts in timestamps:
            f = _frame_at(cap, fps, ts)
            if f is None:
                continue
            frontal_frames.append(_split_quadrant(f, front_quad))
            traseira_frames.append(_split_quadrant(f, back_quad))
        cap.release()

        if len(frontal_frames) < 2:
            print(f"  [motion] frames insuficientes: {len(frontal_frames)} de {n} esperados")
            return None
    except Exception as e:
        print(f"  [motion] EXCEPTION: {e}")
        return None

    try:
        ev_front = _STOP.is_stopped_in_window(frontal_frames, timestamps[: len(frontal_frames)])
        ev_back = _STOP.is_stopped_in_window(traseira_frames, timestamps[: len(traseira_frames)])
    except Exception as e:
        print(f"  [motion] EXCEPTION em StopDetector: {e}")
        return None

    parou_f = ev_front is not None
    parou_b = ev_back is not None
    dur_max = max(
        ev_front.duration_s if ev_front else 0.0,
        ev_back.duration_s if ev_back else 0.0,
    )
    if parou_f and parou_b:
        narr = f"parado nas 2 câmeras por {dur_max:.1f}s"
    elif parou_f:
        narr = f"parado só na frontal por {ev_front.duration_s:.1f}s"
    elif parou_b:
        narr = f"parado só na traseira por {ev_back.duration_s:.1f}s"
    else:
        narr = "veículo seguiu se movendo"

    return MotionCheck(
        parou_frontal=parou_f,
        parou_traseira=parou_b,
        dur_max_s=round(dur_max, 2),
        fps_amostra=sample_fps,
        n_frames=len(frontal_frames),
        narrativa=narr,
    )


# ============================================================================
# VLM gatekeeper — LLaVA via Ollama valida visualmente antes de approved
# ============================================================================

_VLM_CACHE: dict[str, dict] = {}  # evento_id → resultado


def _vlm_validar_evento(ev: Evento) -> dict | None:
    """Extrai crop do evento + chama LLaVA. Retorna {"resposta": "a|b|c|d|?",
    "raw": str} ou None se VLM indisponível.

    Cache por evento_id (mesmo evento revisado 2× não chama VLM 2×).
    """
    if ev.evento_id in _VLM_CACHE:
        return _VLM_CACHE[ev.evento_id]
    try:
        from tooling.extrair_crop import extrair_crop
        from tooling.vlm_validator import ollama_status, validar_crop

        # checa se Ollama tá vivo antes de extrair crop (poupa I/O)
        st = ollama_status(timeout=1.5)
        if not st.get("running") or not any("llava" in m.lower() for m in st.get("models", [])):
            return None
        crop_path = extrair_crop(ev.hash_, evento_id=ev.evento_id)
        if crop_path is None:
            return None
        # usa _full (com bbox marcada) — mostra contexto + região destacada
        full_path = crop_path  # extrair_crop retorna o _full.png
        res = validar_crop(full_path)
        if not res.get("ok"):
            return None
        _VLM_CACHE[ev.evento_id] = res
        return res
    except Exception as e:
        print(f"  [vlm] erro: {e}")
        return None


# ============================================================================
# Avaliador — regras determinísticas; sem LLM, sem imagem
# ============================================================================

Decisao = Literal["approved", "refuted", "inconclusive", "skip"]


def avaliar_evento(ev: Evento, motion: MotionCheck | None = None) -> tuple[Decisao, str]:
    """
    Decide refuted / inconclusive / skip baseado só na assinatura simbólica.

    Princípios:
      - "stop sign" do YOLO base é cego pra placa BR, conf <0.30 + bbox pequeno
        + isolado = quase certeza de árvore/silhueta.
      - cv:road_text isolado (1 frame) na região central baixa = provável faixa
        de pedestre. Cluster ≥3 hits agrupados = plausível PARE pintado.
      - cv:traffic_light heurística HSV é mudo no nosso setup (1 hit em todo
        dataset); hit isolado é praticamente sempre FP.
      - YOLO traffic_light com cluster ≥3 frames = semáforo plausível.
      - Sem `velocity → 0` (futuro), nada pode virar approved aqui.
    """
    n = ev.n_frames
    fontes = ev.fontes
    conf_max = ev.confidence["max"]
    area_max = ev.bbox_resumo.get("area_px_max", 0)
    regiao = ev.bbox_resumo.get("regiao", "?")
    centro_y = ev.bbox_resumo.get("centro_y_medio", 0)

    only_cv_road = set(fontes) == {"cv:road_text"}
    only_cv_tl = set(fontes) == {"cv:traffic_light"}
    has_yolo_cluster = any(
        c.get("cluster_size", 1) >= 3 and c["origem"].startswith("yolo:") for c in ev.candidatos
    )

    # ---- regras de REFUTE -----------------------------------------------
    if only_cv_road and n == 1 and centro_y >= 240:
        return "refuted", (
            f"1 frame cv:road_text isolado em região {regiao} "
            f"(provável faixa de pedestre, não placa)"
        )

    # Regra 1.4 do plano: cv:road_text isolado em centro-baixa (próximo do
    # veículo, atravessando a pista) é assinatura clássica de FAIXA DE
    # PEDESTRE listrada — não confundir com PARE pintado (que fica mais
    # longe na perspectiva, centro-alta). Recusa cluster pequeno (n<=4)
    # nessa região mesmo se motion check disser que carro andou.
    n_distintos = ev.bbox_resumo.get("n_distintos", 0)
    if only_cv_road and n <= 4 and centro_y >= 200 and n_distintos <= 2 and area_max >= 8000:
        return "refuted", (
            f"{n} hits cv:road_text agrupados em região {regiao} "
            f"(centro_y={centro_y}, area_max={area_max}px, n_distintos={n_distintos}) "
            f"— assinatura clássica de FAIXA DE PEDESTRE atravessando a pista, "
            f"não placa Pare pintada"
        )

    if only_cv_tl and n == 1:
        return "refuted", (
            "cv:traffic_light isolado — heurística HSV mudo, hit único é FP recorrente"
        )

    # YOLO base COCO é cego pra placa BR — hits isolados abaixo de 0.32 sem
    # nenhum reforço temporal são quase sempre árvore/silhueta/sombra.
    yolo_isolated_low = (
        n == 1
        and any(c["origem"].startswith("yolo:") for c in ev.candidatos)
        and conf_max < 0.32
        and not has_yolo_cluster
    )
    if yolo_isolated_low:
        return "refuted", (
            f"yolo {ev.candidatos[0]['origem']} isolado conf={conf_max} "
            f"area={area_max}px sem cluster — modelo COCO cego pra placa BR, "
            f"assinatura típica de árvore/silhueta"
        )

    # ---- sinal forte (yolo cluster OU ≥3 hits CV agrupados, qualquer mistura) --
    n_cv = sum(c for k, c in fontes.items() if k.startswith("cv:"))
    sinal_forte = has_yolo_cluster or n_cv >= 3

    if sinal_forte and motion is not None:
        # Princípio 2 — placa detectada + motion check fecha o veredito
        if motion.parou_frontal and motion.parou_traseira:
            return "refuted", (
                f"sinal {ev.narrativa} mas {motion.narrativa} — "
                f"cumprimento confirmado, não é infração"
            )
        if motion.parou_frontal or motion.parou_traseira:
            # confirmação parcial — atenção mas inconclusivo (1 câmera só)
            return "inconclusive", (
                f"sinal {ev.narrativa}; {motion.narrativa} — parada parcial, revisar"
            )
        # Carro NÃO parou em nenhuma câmera + sinal forte
        # Iteração 1 do loop: 15/15 approveds via cv:road_text isolado = FP.
        # Iteração 2 do loop: 6/6 approveds via cv:road_text + cv:traffic_light
        #   HSV = FP (paralelepípedo + cabos/lâmpadas distantes).
        # Conclusão: detectores heurísticos não distinguem placa Pare de
        # faixa pedestre/outdoor. Adicionada camada VLM (LLaVA via Ollama)
        # como gatekeeper visual final.
        co_evidencia_forte = has_yolo_cluster or "cv:pare_sign" in fontes
        if not co_evidencia_forte:
            # Sinal só com cv:road_text/traffic_light HSV — passa pelo VLM.
            # Se VLM rejeita = refuted. Se VLM confirma = approved.
            # Se VLM indisponível/erro = inconclusive (degradação graciosa).
            vlm_res = _vlm_validar_evento(ev)
            if vlm_res is None:
                return "inconclusive", (
                    f"sinal {ev.narrativa} + {motion.narrativa} sem co-evidência "
                    f"forte e VLM indisponível. Revisar manualmente."
                )
            if vlm_res["resposta"] == "a":
                return "approved", (
                    f"sinal {ev.narrativa} + {motion.narrativa} + LLaVA "
                    f"confirmou (a) PARE/semáforo: '{vlm_res['raw'][:60]}' "
                    f"— R1020-G-a confirmada"
                )
            labels = {
                "b": "faixa de pedestre",
                "c": "parede/prédio/cenário",
                "d": "asfalto vazio/nada",
                "?": "indeterminado",
            }
            return "refuted", (
                f"sinal {ev.narrativa} + carro andou MAS LLaVA categorizou como "
                f"({vlm_res['resposta']}) {labels.get(vlm_res['resposta'], '?')}: "
                f"'{vlm_res['raw'][:60]}'"
            )
        return "approved", (
            f"sinal {ev.narrativa} + {motion.narrativa} (frontal+traseira) — "
            f"R1020-G-a confirmada (carro avançou sinalização)"
        )

    if sinal_forte:
        # sem motion check, mantém comportamento anterior
        return "inconclusive", (f"sinal forte ({ev.narrativa}) sem motion check disponível")

    if conf_max >= 0.45 and area_max >= 1000:
        return "inconclusive", (
            f"evidência média/forte ({ev.narrativa} conf_max={conf_max} "
            f"area_max={area_max}px) — exige revisão humana"
        )

    # ---- ruído passivo: deixa quieto, sem voto ---------------------------
    return "skip", "sem assinatura clara — deixa para humano sem voto"


# ============================================================================
# Persistência via curl
# ============================================================================


def emitir_voto(
    hash_: str, ev: Evento, decisao: Decisao, motivo: str, client: httpx.Client
) -> dict | None:
    if decisao == "skip":
        return None
    vote_map = {"approved": "S", "refuted": "N", "inconclusive": ""}
    payload = {
        "infracao_id": "R1020-G-a",
        "frame_idx": ev.candidatos[0].get("frame_idx"),
        "ts": ev.ts_inicio,
        "decisao": decisao,
        "evidencia": f"[{ev.evento_id}] {motivo}",
        "vote": vote_map.get(decisao, ""),
    }
    url = f"{BACKEND}/api/analyses/{hash_}/training-example"
    r = client.post(url, json=payload, timeout=10.0)
    r.raise_for_status()
    return r.json()


# ============================================================================
# CLI
# ============================================================================


def _video_path_para_hash(hash_: str) -> Path | None:
    res = ANALYSES / hash_ / "result.json"
    if not res.exists():
        return None
    p = json.loads(res.read_text()).get("video", {}).get("path")
    if not p:
        return None
    pp = Path(p)
    return pp if pp.exists() else None


def processar_hash(
    hash_: str, dry_run: bool = False, client: httpx.Client | None = None, skip_motion: bool = False
) -> dict:
    cands = coletar_candidatos(hash_)
    eventos = agrupar_em_eventos(cands, hash_)
    video_path = None if skip_motion else _video_path_para_hash(hash_)

    print(f"\n══════ {hash_[:8]}… ({len(cands)} candidatos → {len(eventos)} eventos) ══════")
    if video_path is None and not skip_motion:
        print("  ⚠ vídeo não encontrado — motion check desabilitado")
    counts = Counter()
    decisoes = []
    own_client = client is None
    if own_client:
        client = httpx.Client()
    try:
        for ev in eventos:
            motion = None
            if video_path is not None:
                # Pre-filtro: só roda motion check em sinal_forte (poupa CPU)
                tem_yolo_cluster = any(
                    c.get("cluster_size", 1) >= 3 and c["origem"].startswith("yolo:")
                    for c in ev.candidatos
                )
                # Qualquer cluster CV ≥3 hits é sinal forte — inclui road_text,
                # pare_sign, traffic_light, ou misturas (eventos misturados são
                # ainda melhores candidatos: múltiplos detectores concordando).
                tem_cv_cluster = sum(c for k, c in ev.fontes.items() if k.startswith("cv:")) >= 3
                if tem_yolo_cluster or tem_cv_cluster:
                    motion = verificar_parada(video_path, ev.ts_inicio, ev.ts_fim)

            decisao, motivo = avaliar_evento(ev, motion=motion)
            counts[decisao] += 1
            mflag = ""
            if motion is not None:
                mflag = f" [motion: {motion.narrativa}]"
            print(
                f"  {ev.evento_id}  ts={ev.ts_inicio:>6.1f}–{ev.ts_fim:<6.1f} "
                f"n={ev.n_frames:>2} conf_max={ev.confidence['max']:.2f} "
                f"region={ev.bbox_resumo.get('regiao', '?'):<13}"
                f" → {decisao}{mflag}"
            )
            print(f"       narrativa: {ev.narrativa}")
            print(f"       motivo:    {motivo}")
            if not dry_run:
                resp = emitir_voto(hash_, ev, decisao, motivo, client)
                if resp:
                    print(f"       persistido (total examples.jsonl: {resp.get('total_examples')})")
            decisoes.append(
                {
                    "evento_id": ev.evento_id,
                    "decisao": decisao,
                    "motivo": motivo,
                    "ts": ev.ts_inicio,
                    "motion": motion.__dict__ if motion else None,
                }
            )
    finally:
        if own_client:
            client.close()
    print(f"  → {dict(counts)}")
    return {
        "hash": hash_,
        "n_candidatos": len(cands),
        "n_eventos": len(eventos),
        "counts": dict(counts),
        "decisoes": decisoes,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hash", help="hash sha256 da análise")
    ap.add_argument("--all", action="store_true", help="processa os 4 vídeos do dataset")
    ap.add_argument("--dry-run", action="store_true", help="não envia votos")
    ap.add_argument(
        "--skip-motion", action="store_true", help="pula verificação de parada (mais rápido)"
    )
    args = ap.parse_args()

    if not args.hash and not args.all:
        ap.error("forneça --hash <h> ou --all")

    hashes = list(DATASET.values()) if args.all else [args.hash]
    summary = {}
    with httpx.Client() as client:
        for h in hashes:
            summary[h[:8]] = processar_hash(
                h,
                dry_run=args.dry_run,
                client=client,
                skip_motion=args.skip_motion,
            )

    print("\n══════ RESUMO ══════")
    for h8, s in summary.items():
        print(f"  {h8}…: {s['n_candidatos']} cand → {s['n_eventos']} eventos · {s['counts']}")


if __name__ == "__main__":
    main()
