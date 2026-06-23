"""
Roda os detectores OpenCV (crosswalk, road_text, stop, traffic_light) em frames
amostrados do vídeo grid 2×2 e salva agregação em
storage/analyses/<hash>/cv_detections.json.

Diferente do YOLO (deep learning), estes são heurísticos OpenCV puros — rápidos,
determinísticos, e complementares ao YOLO. Servem como segunda fonte para
validar candidatos do YOLO ou pegar coisas que YOLO não vê (ex.: faixa de
pedestres, "PARE" pintado no chão).

Saída:
{
  "hash": "...",
  "n_frames_analisados": 12,
  "detections": [
    {"frame_idx": 0, "ts": 0.0, "camera": "frontal",
     "type": "crosswalk", "detected": true, "confidence": 0.7, "evidence": "..."},
    ...
  ],
  "summary": {"crosswalk": 3, "stop": 0, "traffic_light": 1, "road_text": 2}
}

Uso:
    .venv/bin/python -m tooling.cv_detectors_runner storage/videos/1.mp4
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2

from src.detectors.crosswalk import CrosswalkDetector
from src.detectors.pare_sign import PareSignDetector
from src.detectors.road_text import RoadTextDetector
from src.detectors.traffic_light import TrafficLightDetector

# StopDetector não expõe .detect() — wrapper especial seria necessário; skip por ora.
from src.ingestion.grid_slicer import GridSlicer
from src.tier_a_pipeline import sha256_arquivo

PROJECT_ROOT = Path(__file__).parent.parent
STORAGE = PROJECT_ROOT / "storage"


def run(video_path: Path, n_samples: int = 120) -> Path:
    if not video_path.is_absolute():
        video_path = (
            (STORAGE / "videos" / video_path).resolve()
            if (STORAGE / "videos" / video_path).exists()
            else video_path.resolve()
        )
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    h = sha256_arquivo(video_path)
    out_dir = STORAGE / "analyses" / h
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cv_detections.json"

    slicer = GridSlicer(video_path, sample_fps=0.0)
    meta = slicer.metadata()

    # Amostra n_samples frames distribuídos
    cap = cv2.VideoCapture(str(video_path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    indices = [int(total * (i + 0.5) / n_samples) for i in range(n_samples)]
    print(f"[cv] {video_path.name} {meta['duration_s']:.0f}s · amostrando {n_samples} frames")

    detectors = [
        ("crosswalk", CrosswalkDetector(camera="TL"), "frontal"),
        ("road_text", RoadTextDetector(), "frontal"),
        ("traffic_light", TrafficLightDetector(), "frontal"),
        ("pare_sign", PareSignDetector(camera="TL"), "frontal"),
    ]

    detections: list[dict] = []
    summary: dict[str, int] = defaultdict(int)

    print(f"[cv] layout detectado: {slicer.layout_name}")
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        ts = idx / fps
        # extrai a câmera FRONTAL conforme layout (varia entre VIP/Hikvision)
        frontal = slicer.extract_camera(frame, "frontal")
        for name, det, camera in detectors:
            try:
                result = det.detect(frontal, frame_idx=idx, timestamp_s=ts)
                if result.detected:
                    summary[name] += 1
                    detections.append(
                        {
                            "frame_idx": idx,
                            "ts": round(ts, 2),
                            "camera": camera,
                            "type": name,
                            "detected": True,
                            "confidence": round(result.confidence, 3),
                            "bbox": list(result.bbox) if result.bbox else None,
                            "evidence": (result.metadata or {}).get("evidence", "")
                            if isinstance(result.metadata, dict)
                            else "",
                        }
                    )
            except Exception as e:
                print(f"  [{name}@{idx}] falhou: {str(e)[:60]}")

    cap.release()

    out = {
        "hash": h,
        "n_frames_analisados": n_samples,
        "summary": dict(summary),
        "detections": detections,
    }
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(
        f"[cv] {len(detections)} detecções · summary {dict(summary)} → {out_path.relative_to(PROJECT_ROOT)}"
    )
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--samples", type=int, default=120)
    args = ap.parse_args()
    run(args.video, n_samples=args.samples)


if __name__ == "__main__":
    main()
