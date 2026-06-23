"""
scan_vid3_circuito — varre storage/videos/3.mp4 (mesmo circuito de 2.mp4)
buscando sinalização horizontal e vertical, salva crops + JSON em
sinalizacao/circuitos/circuito-vid2-vid3/vid3/.

Detectores combinados:
  1. R-1 vertical: src.detectors.pare_sign.PareSignDetector (HSV vermelho).
  2. Cluster branco grande na metade inferior frontal — candidato a PARE chão
     ou seta direcional. Não distingue — deixa pra revisor humano/VLM.

Saída: JSON `scan_results.json` com lista de hits temporais.
PNGs: <NN>_vid3_t<MM-SS>_frontal_raw.png pra cada hit.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from src.detectors.pare_sign import PareSignDetector
from src.ingestion.grid_slicer import GridSlicer

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "storage" / "videos" / "3.mp4"
OUT_DIR = ROOT / "sinalizacao" / "circuitos" / "circuito-vid2-vid3" / "vid3"


def detect_white_cluster(frontal: np.ndarray) -> tuple[int, int, int, int, int] | None:
    """Procura cluster branco grande na metade inferior. Retorna
    (x1,y1,x2,y2,area) do maior cluster ou None."""
    gray = cv2.cvtColor(frontal, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    mask = (gray > 175).astype(np.uint8) * 255
    mask[: int(h * 0.55), :] = 0  # só metade inferior
    mask[int(h * 0.95) :, :] = 0  # ignora overlay câmera
    mask[:, : int(w * 0.05)] = 0
    mask[:, int(w * 0.95) :] = 0
    # dilate forte pra unir letras de "PARE" e haste+ponta de seta
    mask = cv2.dilate(mask, np.ones((5, 15), np.uint8), iterations=2)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    best = max(cnts, key=cv2.contourArea)
    area = cv2.contourArea(best)
    if area < 800:
        return None
    x, y, ww, hh = cv2.boundingRect(best)
    return (x, y, x + ww, y + hh, int(area))


def main():
    if not VIDEO.exists():
        raise SystemExit(f"vídeo não encontrado: {VIDEO}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    slicer = GridSlicer(VIDEO, sample_fps=1.0)  # 1 frame/s
    pare_det = PareSignDetector()

    hits = []
    last_white_ts = -10.0  # debounce 5s

    print(f"varrendo {VIDEO.name} (1 fps, duração {slicer.duration_s:.1f}s)...")
    for grid in slicer.iter_frames():
        ts = grid.timestamp_s
        frontal = grid.frontal

        # 1) placa R-1
        try:
            cand = pare_det.detect(frontal, frame_idx=grid.frame_idx, timestamp_s=ts)
            if cand and getattr(cand, "confidence", 0) > 0.4:
                bbox = list(getattr(cand, "bbox", [0, 0, 0, 0]))
                hits.append(
                    {
                        "ts": round(ts, 1),
                        "ts_label": f"{int(ts // 60):02d}:{int(ts % 60):02d}",
                        "detector": "pare_sign_r1",
                        "category_hint": "vertical/pare-r1",
                        "bbox_xyxy": bbox,
                        "confidence": float(getattr(cand, "confidence", 0)),
                    }
                )
        except Exception:
            pass

        # 2) cluster branco grande inferior (PARE chão / seta)
        if ts - last_white_ts > 4.0:
            cluster = detect_white_cluster(frontal)
            if cluster is not None:
                x1, y1, x2, y2, area = cluster
                hits.append(
                    {
                        "ts": round(ts, 1),
                        "ts_label": f"{int(ts // 60):02d}:{int(ts % 60):02d}",
                        "detector": "white_cluster_lower",
                        "category_hint": "horizontal/seta-ou-pare-chao",
                        "bbox_xyxy": [x1, y1, x2, y2],
                        "area": area,
                    }
                )
                last_white_ts = ts

                # salva crop frontal (raw) pro hit
                idx = len([h for h in hits if h["detector"] == "white_cluster_lower"])
                slug = f"{idx:02d}_vid3_t{int(ts // 60):02d}-{int(ts % 60):02d}_frontal"
                cv2.imwrite(str(OUT_DIR / f"{slug}_raw.png"), frontal)

    summary = {
        "video": str(VIDEO.relative_to(ROOT)),
        "duration_s": slicer.duration_s,
        "n_hits_total": len(hits),
        "n_hits_r1": sum(1 for h in hits if h["detector"] == "pare_sign_r1"),
        "n_hits_horizontal": sum(1 for h in hits if h["detector"] == "white_cluster_lower"),
        "hits": hits,
    }
    out = OUT_DIR.parent / "scan_results.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(
        f"  total: {summary['n_hits_total']} hits  "
        f"(R-1: {summary['n_hits_r1']}, horizontal: {summary['n_hits_horizontal']})"
    )
    print(f"  resultados: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
