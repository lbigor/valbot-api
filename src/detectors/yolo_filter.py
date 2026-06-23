"""
YOLO filter parametrizado pelos votos do avaliador DETRAN humano.

Estratégia (memory feedback_yolo_tier_a_filtros + retroalimentação):
    - Filtros estruturais sempre aplicados:
        1. is_overlay_bbox: descarta o canal "01-99" da câmera VIP Intelbras
        2. cluster temporal: ≥3 frames consecutivos = confiável; isolada-grande
           (stop sign bbox >25×25 + conf >0.28) = suspeita
    - Retroalimentação dos votos:
        a) Votos `y_*` com vote=N → bbox negativo (lista negra regional ±20px)
        b) Votos `c_*` com vote=S → timestamps validados (cinto presente)
        c) Curados 01-06 numéricos → regras nomeadas

Os votos vêm de storage/training/review_votes.json + review_items.json.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VOTES_PATH = PROJECT_ROOT / "storage" / "training" / "review_votes.json"
ITEMS_PATH = PROJECT_ROOT / "storage" / "training" / "review_items.json"
EXAMPLES_JSONL = PROJECT_ROOT / "storage" / "training" / "examples.jsonl"


# ---------- Filtros estruturais (do feedback_yolo_tier_a_filtros) ----------


def is_overlay_bbox(bbox, frame_w: int = 640, frame_h: int = 360) -> bool:
    """Bbox que coincide com o overlay '01'-'99' do canto TL da câmera VIP."""
    x1, y1, x2, y2 = bbox[:4]
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    return 180 <= cx <= 240 and 10 <= cy <= 50


# ---------- Retroalimentação dos votos ----------


@dataclass
class VotosFiltros:
    """Estado dos filtros derivados dos votos humanos."""

    blacklist_bbox: list[dict] = field(default_factory=list)  # bbox que JÁ foram refutadas
    cinto_validados_ts: list[tuple[str, float]] = field(default_factory=list)  # (vid, ts)
    regras_nomeadas: list[str] = field(default_factory=list)


def carregar_votos(
    votes_path: Path = VOTES_PATH,
    items_path: Path = ITEMS_PATH,
    examples_path: Path = EXAMPLES_JSONL,
) -> VotosFiltros:
    """
    Carrega votos de duas fontes:
      1. review_votes.json + review_items.json — 39 votos curados originais
      2. examples.jsonl — votos novos vindos da UI via POST /training-example

    Os dois alimentam o mesmo VotosFiltros, fechando o loop humano → filtro.
    """
    out = VotosFiltros()

    # ---- Fonte 1: legado (review_votes.json + review_items.json)
    if votes_path.exists() and items_path.exists():
        votes = json.loads(votes_path.read_text())
        items = {it["id"]: it for it in json.loads(items_path.read_text())}

        for vid, info in votes.items():
            v = info.get("vote")
            item = items.get(vid)

            # y_* — YOLO sinal vertical, voto N = bbox negativo
            if vid.startswith("y_") and v == "N" and item:
                ctx = (item.get("context") or "").lower()
                ts = item.get("timestamp_s")
                video = item.get("video")
                out.blacklist_bbox.append(
                    {
                        "video": video,
                        "ts": ts,
                        "claim": item.get("claim"),
                        "context": ctx[:200],
                        "source": "legacy",
                    }
                )

            # c_* — cinto, voto S = frame validado
            if vid.startswith("c_") and v == "S" and item:
                video = item.get("video")
                ts = item.get("timestamp_s")
                if video is not None and ts is not None:
                    out.cinto_validados_ts.append((video, ts))

            # Curados 01-06 numéricos
            if vid.lstrip("0").isdigit() and v in ("S", "N") and item:
                tag = "✓" if v == "S" else "✗"
                out.regras_nomeadas.append(f"item {vid} {tag}: {item.get('claim', '')[:80]}")

    # ---- Fonte 2: examples.jsonl (votos novos vindos da UI)
    if examples_path.exists():
        for line in examples_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                log.debug("yolo_filter: linha JSON invalida ignorada: %s", e)
                continue
            iid = rec.get("infracao_id")
            decisao = rec.get("decisao")
            vote = rec.get("vote")
            ts = rec.get("ts")
            hash_ = rec.get("hash")

            # R1020-G-a refutada → bbox negativo (mesmo efeito que y_* legacy)
            if (
                iid == "R1020-G-a"
                and decisao in ("refuted", "manual")
                and vote == "N"
                and ts is not None
            ):
                out.blacklist_bbox.append(
                    {
                        "video": hash_,  # usamos hash como chave de vídeo aqui
                        "ts": ts,
                        "claim": rec.get("evidencia", ""),
                        "context": f"voto novo via /training-example em {rec.get('saved_at', '')}",
                        "source": "live",
                    }
                )

            # R1020-GR-f confirmada → frame validado
            if (
                iid == "R1020-GR-f"
                and decisao == "approved"
                and vote == "S"
                and ts is not None
                and hash_
            ):
                out.cinto_validados_ts.append((hash_, float(ts)))

    return out


# ---------- Pipeline de filtragem ----------


def filtrar_yolo_com_votos(
    detections: list[dict],
    votos: VotosFiltros | None = None,
    video_filename: str | None = None,
    video_hash: str | None = None,
) -> dict:
    """
    Aplica filtros estruturais + retroalimentação dos votos.

    detections: lista no schema do yolo_explore (keys: ts, class, conf, bbox, frame_idx, track_id).
    votos: estado pre-carregado; se None, carrega do disco.
    video_filename: ex. "1.mp4". Se fornecido, casa votos negativos do mesmo vídeo.

    Retorno:
        {confiavel, suspeito, descartado, overlay_descartado, vetado_por_voto,
         stats: {...}}
    """
    if votos is None:
        votos = carregar_votos()

    def _norm(d: dict) -> dict:
        return {
            "frame_idx": d.get("frame_idx"),
            "timestamp_s": d.get("ts", d.get("timestamp_s", 0.0)),
            "class_name": d.get("class", d.get("class_name", "")),
            "confidence": d.get("conf", d.get("confidence", 0.0)),
            "bbox": d["bbox"],
            "track_id": d.get("track_id"),
        }

    detections = [_norm(d) for d in detections]
    relevantes = [d for d in detections if d["class_name"] in ("traffic light", "stop sign")]

    # 1) Overlay
    sem_overlay = [d for d in relevantes if not is_overlay_bbox(d["bbox"])]
    overlay = [d for d in relevantes if is_overlay_bbox(d["bbox"])]

    # 2) Voto negativo: casa por filename (legacy "vid1") OU por hash (live).
    def _voto_aplica_a_este_video(b: dict) -> bool:
        bv = str(b.get("video") or "")
        if not bv:
            return False
        # source live: bv é o hash sha256 do vídeo
        if b.get("source") == "live":
            return video_hash is not None and bv == video_hash
        # legacy: bv é "vid1", "vid2"… casa com filename "1.mp4"
        if not video_filename:
            return False
        return video_filename.startswith(bv.replace("vid", "")) or bv in video_filename

    blk_for_video = [b for b in votos.blacklist_bbox if _voto_aplica_a_este_video(b)]

    def _vetada_por_voto(d: dict) -> bool:
        for b in blk_for_video:
            ts = b.get("ts")
            if ts is None:
                continue
            if abs(d["timestamp_s"] - float(ts)) <= 1.5:
                return True
        return False

    sem_voto_neg = [d for d in sem_overlay if not _vetada_por_voto(d)]
    vetado_voto = [d for d in sem_overlay if _vetada_por_voto(d)]

    # 3) Cluster temporal por classe (mantida lógica existente)
    sem_voto_neg.sort(key=lambda d: (d["class_name"], d["timestamp_s"]))
    confiavel: list[dict] = []
    suspeito: list[dict] = []
    descartado: list[dict] = []

    by_class = defaultdict(list)
    for d in sem_voto_neg:
        by_class[d["class_name"]].append(d)

    for cls, group in by_class.items():
        clusters: list[list[dict]] = []
        cur: list[dict] = []
        for d in group:
            if not cur:
                cur = [d]
                continue
            last = cur[-1]
            dt = d["timestamp_s"] - last["timestamp_s"]
            cx_l = (last["bbox"][0] + last["bbox"][2]) / 2
            cy_l = (last["bbox"][1] + last["bbox"][3]) / 2
            cx_d = (d["bbox"][0] + d["bbox"][2]) / 2
            cy_d = (d["bbox"][1] + d["bbox"][3]) / 2
            if dt <= 1.0 and abs(cx_d - cx_l) <= 15 and abs(cy_d - cy_l) <= 15:
                cur.append(d)
            else:
                clusters.append(cur)
                cur = [d]
        if cur:
            clusters.append(cur)

        for c in clusters:
            if len(c) >= 3:
                best = max(c, key=lambda x: x["confidence"])
                confiavel.append({**best, "cluster_size": len(c)})
            else:
                d = c[0] if len(c) == 1 else max(c, key=lambda x: x["confidence"])
                bw = d["bbox"][2] - d["bbox"][0]
                bh = d["bbox"][3] - d["bbox"][1]
                if cls == "stop sign" and bw > 25 and bh > 25 and d["confidence"] > 0.28:
                    suspeito.append({**d, "cluster_size": len(c)})
                else:
                    for x in c:
                        descartado.append(x)

    return {
        "confiavel": confiavel,
        "suspeito": suspeito,
        "descartado": descartado,
        "overlay_descartado": overlay,
        "vetado_por_voto": vetado_voto,
        "stats": {
            "total_relevantes": len(relevantes),
            "overlay_fp": len(overlay),
            "vetado_por_voto": len(vetado_voto),
            "confiavel": len(confiavel),
            "suspeito": len(suspeito),
            "descartado": len(descartado),
        },
        "regras_aplicadas": votos.regras_nomeadas,
    }
