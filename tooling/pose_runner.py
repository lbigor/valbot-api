"""
Extrai pose (keypoints + bboxes anatômicos) da câmera INTERNA (BL) usando
yolo11s-pose.pt. Roda automaticamente no worker do upload pra que vídeos
novos tenham esqueleto disponível no modo Debug.

Saída: storage/analyses/<hash>/pose.json
    Schema compatível com pose_review_log.json (campo `vid` ausente; o frontend
    usa o array todo independente do nome).

Cada entrada:
    {
      "ts": 12.5, "frame_idx": 375,
      "persons": [
        {
          "role": "CONDUTOR" | "EXAMINADOR",
          "bbox": [x1,y1,x2,y2],         // bbox da pessoa no quadrante BL
          "kpts": {nome: [x,y,conf], ...}
        }
      ]
    }

Heurística de role:
    - CONDUTOR fica à DIREITA do quadrante BL (x_centro > 50% da largura).
    - EXAMINADOR à esquerda (x_centro < 50%).
    - Se houver mais de 2 pessoas, marca extras como "OUTRO".

Uso:
    .venv/bin/python -m tooling.pose_runner storage/videos/1.mp4
    .venv/bin/python -m tooling.pose_runner storage/videos/1.mp4 --sample-fps 1.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ultralytics import YOLO

from src.ingestion.grid_slicer import GridSlicer
from src.tier_a_pipeline import sha256_arquivo

PROJECT_ROOT = Path(__file__).parent.parent
STORAGE = PROJECT_ROOT / "storage"
POSE_MODEL = PROJECT_ROOT / "yolo11s-pose.pt"

KPT_NAMES = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]


def assign_role(persons: list[dict], frame_w: int) -> list[dict]:
    """
    CONDUTOR à direita (x > 50%), EXAMINADOR à esquerda. Demais = OUTRO.
    Se só 1 pessoa: tenta inferir pelo lado dominante.
    """
    if not persons:
        return persons
    sorted_p = sorted(persons, key=lambda p: -p["bbox"][2])  # mais à direita primeiro
    out = []
    seen = {"CONDUTOR": False, "EXAMINADOR": False}
    for p in sorted_p:
        cx = (p["bbox"][0] + p["bbox"][2]) / 2
        if cx > frame_w / 2 and not seen["CONDUTOR"]:
            p["role"] = "CONDUTOR"
            seen["CONDUTOR"] = True
        elif cx <= frame_w / 2 and not seen["EXAMINADOR"]:
            p["role"] = "EXAMINADOR"
            seen["EXAMINADOR"] = True
        else:
            p["role"] = "OUTRO"
        out.append(p)
    return out


def run(video_path: Path, sample_fps: float = 0.5, conf: float = 0.3) -> Path:
    if not video_path.is_absolute():
        video_path = (
            (STORAGE / "videos" / video_path).resolve()
            if (STORAGE / "videos" / video_path).exists()
            else video_path.resolve()
        )
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not POSE_MODEL.exists():
        raise FileNotFoundError(f"modelo de pose ausente: {POSE_MODEL}")

    h = sha256_arquivo(video_path)
    out_dir = STORAGE / "analyses" / h
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "pose.json"

    slicer = GridSlicer(video_path, sample_fps=sample_fps)
    meta = slicer.metadata()
    bl_w = slicer.half_w
    print(
        f"[pose] {video_path.name}  {meta['duration_s']:.1f}s @ {sample_fps}fps  → ~{int(meta['duration_s'] * sample_fps)} frames"
    )

    model = YOLO(str(POSE_MODEL))
    entries: list[dict] = []

    for grid in slicer.iter_frames():
        bl = grid.interna  # quadrante BL (câmera interna)
        # YOLO pose espera BGR
        result = model(bl, conf=conf, verbose=False)[0]
        if result.keypoints is None or result.boxes is None:
            continue

        persons = []
        for i in range(len(result.boxes)):
            kpts_arr = result.keypoints.data[i].cpu().numpy()  # (17, 3)
            box = result.boxes.xyxy[i].cpu().numpy().tolist()
            kpts = {}
            for j, name in enumerate(KPT_NAMES):
                if j < len(kpts_arr):
                    x, y, c = kpts_arr[j].tolist()
                    kpts[name] = [round(x, 1), round(y, 1), round(c, 3)]
            persons.append(
                {
                    "bbox": [round(v, 1) for v in box],
                    "kpts": kpts,
                }
            )

        persons = assign_role(persons, bl_w)
        entries.append(
            {
                "ts": round(grid.timestamp_s, 2),
                "frame_idx": grid.frame_idx,
                "persons": persons,
            }
        )

    out_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False))
    print(f"[pose] {len(entries)} entradas salvas em {out_path.relative_to(PROJECT_ROOT)}")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--sample-fps", type=float, default=0.5)
    ap.add_argument("--conf", type=float, default=0.3)
    args = ap.parse_args()
    run(args.video, sample_fps=args.sample_fps, conf=args.conf)


if __name__ == "__main__":
    main()
