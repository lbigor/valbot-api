"""
Gera PNG de heatmap das mãos (mão_direita + mão_esquerda) sobre a câmera
INTERNA (BL) por vídeo. Salva em storage/analyses/<hash>/heatmap_maos.png.

Fonte de dados:
    storage/training/pose_review_log.json
        Cada entrada: {vid: "vidN", persons: [{role, kpts: {...}, hand_d, hand_e}]}
        kpts tem left_wrist/right_wrist como [x, y, confidence] em pixels do quadrante BL.

Uso:
    .venv/bin/python -m tooling.render_heatmap
    .venv/bin/python -m tooling.render_heatmap --only vid1
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from src.tier_a_pipeline import sha256_arquivo

PROJECT_ROOT = Path(__file__).parent.parent
STORAGE = PROJECT_ROOT / "storage"
POSE_LOG = STORAGE / "training" / "pose_review_log.json"
VIDEOS_DIR = STORAGE / "videos"
ANALYSES_DIR = STORAGE / "analyses"

BL_W, BL_H = 640, 360


def render_one(points: list[tuple[float, float]], sigma: int = 22) -> np.ndarray:
    """Render heatmap RGBA 640x360 a partir de uma lista de (x, y) em px."""
    canvas = np.zeros((BL_H, BL_W), dtype=np.float32)
    for x, y in points:
        if 0 <= x < BL_W and 0 <= y < BL_H:
            canvas[int(y), int(x)] += 1.0
    if canvas.max() > 0:
        # Gaussian blur (simétrico, sigma controla raio)
        ksize = max(3, sigma * 2 + 1)
        canvas = cv2.GaussianBlur(canvas, (ksize, ksize), sigma)
        canvas = canvas / canvas.max()
    # Colormap quente (vermelho/amarelo) com transparência proporcional
    color = cv2.applyColorMap((canvas * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    rgba = np.zeros((BL_H, BL_W, 4), dtype=np.uint8)
    rgba[:, :, :3] = color
    rgba[:, :, 3] = (canvas * 220).astype(np.uint8)  # alpha proporcional à densidade
    return rgba


def vid_to_hash(vid: str) -> str | None:
    """vid1 → sha256 de storage/videos/1.mp4."""
    n = vid.replace("vid", "")
    p = VIDEOS_DIR / f"{n}.mp4"
    if not p.exists():
        return None
    return sha256_arquivo(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="processar só um vid (ex: vid1)")
    ap.add_argument("--sigma", type=int, default=22)
    args = ap.parse_args()

    if not POSE_LOG.exists():
        raise SystemExit(f"pose_review_log.json não encontrado em {POSE_LOG}")

    log = json.loads(POSE_LOG.read_text())

    by_vid: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for entry in log:
        vid = entry.get("vid")
        if not vid or (args.only and vid != args.only):
            continue
        for person in entry.get("persons", []):
            kpts = person.get("kpts") or {}
            for k in ("left_wrist", "right_wrist"):
                kp = kpts.get(k)
                if not kp or len(kp) < 3:
                    continue
                x, y, conf = kp[:3]
                if conf is None or conf < 0.3:
                    continue
                by_vid[vid].append((float(x), float(y)))

    if not by_vid:
        raise SystemExit("nenhum keypoint válido encontrado")

    for vid, pts in sorted(by_vid.items()):
        h = vid_to_hash(vid)
        if not h:
            print(f"  ✗ {vid}: vídeo não encontrado em storage/videos/")
            continue
        out_dir = ANALYSES_DIR / h
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "heatmap_maos.png"
        rgba = render_one(pts, sigma=args.sigma)
        cv2.imwrite(str(out_path), rgba)
        print(
            f"  ✓ {vid} → {out_path.relative_to(PROJECT_ROOT)} ({len(pts)} pulsos, hash {h[:8]}…)"
        )


if __name__ == "__main__":
    main()
