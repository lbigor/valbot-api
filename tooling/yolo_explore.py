"""
Exploração bruta do YOLO11s na câmera frontal (quadrante TL).

Não usa VLM, não aplica regra de scoring. Só mostra o que o modelo vê.
Saídas em storage/analyses/<video_hash>/yolo_explore/:
  - overlay.mp4       vídeo da câmera frontal com bbox + classe + conf
  - detections.json   [{frame_idx, ts, class, conf, bbox:[x1,y1,x2,y2]}]
  - summary.json      {class: {count, mean_conf, first_ts, last_ts}}

Uso:
  .venv/bin/python -m tooling.yolo_explore 1.mp4
  .venv/bin/python -m tooling.yolo_explore storage/videos/1.mp4 --sample-fps 2 --model yolo11s.pt
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
from ultralytics import YOLO

from src.ingestion.grid_slicer import GridSlicer
from src.tier_a_pipeline import sha256_arquivo

PROJECT_ROOT = Path(__file__).parent.parent
STORAGE = PROJECT_ROOT / "storage"


def video_hash(path: Path) -> str:
    """SHA256 de conteúdo — padroniza com src.tier_a_pipeline e dev_backend_stub."""
    return sha256_arquivo(path)


def run(
    video_path: Path,
    model_name: str = "yolo11s.pt",
    sample_fps: float = 2.0,
    conf_threshold: float = 0.25,
    device: str = "mps",
) -> Path:
    if not video_path.is_absolute():
        video_path = (
            (STORAGE / "videos" / video_path).resolve()
            if (STORAGE / "videos" / video_path).exists()
            else video_path.resolve()
        )
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    vhash = video_hash(video_path)
    out_dir = STORAGE / "analyses" / vhash / "yolo_explore"
    out_dir.mkdir(parents=True, exist_ok=True)

    slicer = GridSlicer(video_path, sample_fps=sample_fps)
    meta = slicer.metadata()
    print(
        f"[video]      {video_path.name}  {meta['duration_s']:.1f}s @ {meta['fps']:.1f}fps  grid {meta['width']}x{meta['height']}"
    )
    print(f"[sample]     {sample_fps} fps  →  ~{int(meta['duration_s'] * sample_fps)} frames")
    print(f"[hash]       {vhash[:16]}…")
    print(f"[output]     {out_dir}")

    print(f"[model]      {model_name} (device={device}, conf≥{conf_threshold})")
    model = YOLO(model_name)

    frontal_w, frontal_h = slicer.half_w, slicer.half_h
    overlay_path = out_dir / "overlay.mp4"
    writer = cv2.VideoWriter(
        str(overlay_path),
        cv2.VideoWriter_fourcc(*"avc1"),
        sample_fps,
        (frontal_w, frontal_h),
    )
    if not writer.isOpened():
        writer = cv2.VideoWriter(
            str(overlay_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            sample_fps,
            (frontal_w, frontal_h),
        )

    # Aplica overrides manuais, se existirem (track_id → {class_override, note})
    overrides_path = out_dir.parent / "manual_overrides.json"
    overrides: dict[str, dict] = {}
    if overrides_path.exists():
        overrides = {str(k): v for k, v in json.loads(overrides_path.read_text()).items()}
        print(f"[overrides]  {overrides_path}  ({len(overrides)} tracks corrigidos)")

    detections: list[dict] = []
    per_class: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "sum_conf": 0.0, "first_ts": None, "last_ts": None, "examples": []}
    )
    tracks: dict[int, dict] = {}
    class_names = model.names

    n_frames = 0
    for grid in slicer.iter_frames():
        frame = grid.frontal
        result = model.track(
            frame,
            conf=conf_threshold,
            device=device,
            tracker="botsort.yaml",
            persist=True,
            verbose=False,
        )[0]

        annotated = frame.copy()
        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls.item())
                cls_original = class_names[cls_id]
                conf = float(box.conf.item())
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                track_id = int(box.id.item()) if box.id is not None else None

                # Aplica override manual se houver
                ov = overrides.get(str(track_id))
                cls = ov["class_override"] if ov else cls_original
                overridden = ov is not None

                color = (
                    _class_color(cls_id) if not overridden else (0, 255, 255)
                )  # amarelo se corrigido
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                parts = [cls]
                if track_id is not None:
                    parts.append(f"#{track_id}")
                parts.append(f"{conf:.2f}")
                if overridden:
                    parts.append("[corr]")
                label = " ".join(parts)
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
                cv2.putText(
                    annotated,
                    label,
                    (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

                detections.append(
                    {
                        "frame_idx": grid.frame_idx,
                        "ts": round(grid.timestamp_s, 2),
                        "track_id": track_id,
                        "class": cls,
                        "class_original": cls_original,
                        "overridden": overridden,
                        "class_id": cls_id,
                        "conf": round(conf, 3),
                        "bbox": [x1, y1, x2, y2],
                    }
                )

                pc = per_class[cls]
                pc["count"] += 1
                pc["sum_conf"] += conf
                pc["first_ts"] = (
                    grid.timestamp_s
                    if pc["first_ts"] is None
                    else min(pc["first_ts"], grid.timestamp_s)
                )
                pc["last_ts"] = (
                    grid.timestamp_s
                    if pc["last_ts"] is None
                    else max(pc["last_ts"], grid.timestamp_s)
                )
                if len(pc["examples"]) < 3:
                    pc["examples"].append(
                        {"ts": round(grid.timestamp_s, 2), "conf": round(conf, 3)}
                    )

                if track_id is not None:
                    t = tracks.setdefault(
                        track_id,
                        {
                            "track_id": track_id,
                            "class_original": cls_original,
                            "class_override": ov["class_override"] if ov else None,
                            "note": ov.get("note") if ov else None,
                            "n_frames": 0,
                            "sum_conf": 0.0,
                            "first_ts": None,
                            "last_ts": None,
                            "classes_seen": {},
                        },
                    )
                    t["n_frames"] += 1
                    t["sum_conf"] += conf
                    t["first_ts"] = (
                        grid.timestamp_s
                        if t["first_ts"] is None
                        else min(t["first_ts"], grid.timestamp_s)
                    )
                    t["last_ts"] = (
                        grid.timestamp_s
                        if t["last_ts"] is None
                        else max(t["last_ts"], grid.timestamp_s)
                    )
                    t["classes_seen"][cls_original] = t["classes_seen"].get(cls_original, 0) + 1

        ts_label = f"t={grid.timestamp_s:5.1f}s  frame {grid.frame_idx}"
        cv2.putText(
            annotated,
            ts_label,
            (10, frontal_h - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        writer.write(annotated)
        n_frames += 1

    writer.release()

    # Finaliza tracks (ordena por duração)
    tracks_list = []
    for t in tracks.values():
        n = t["n_frames"] or 1
        tracks_list.append(
            {
                "track_id": t["track_id"],
                "class_original": t["class_original"],
                "class_override": t["class_override"],
                "note": t["note"],
                "n_frames": t["n_frames"],
                "first_ts": round(t["first_ts"], 2),
                "last_ts": round(t["last_ts"], 2),
                "duration_s": round(t["last_ts"] - t["first_ts"], 2),
                "mean_conf": round(t["sum_conf"] / n, 3),
                "classes_seen": t["classes_seen"],
            }
        )
    tracks_list.sort(key=lambda x: (-x["n_frames"], x["first_ts"]))
    (out_dir / "tracks.json").write_text(json.dumps(tracks_list, indent=2, ensure_ascii=False))

    (out_dir / "detections.json").write_text(json.dumps(detections, indent=2, ensure_ascii=False))

    summary = {
        "video": str(video_path),
        "video_hash": vhash,
        "model": model_name,
        "sample_fps": sample_fps,
        "conf_threshold": conf_threshold,
        "device": device,
        "frames_processed": n_frames,
        "duration_s": meta["duration_s"],
        "total_detections": len(detections),
        "per_class": {
            cls: {
                "count": v["count"],
                "mean_conf": round(v["sum_conf"] / v["count"], 3) if v["count"] else 0.0,
                "first_ts": round(v["first_ts"], 2) if v["first_ts"] is not None else None,
                "last_ts": round(v["last_ts"], 2) if v["last_ts"] is not None else None,
                "examples": v["examples"],
            }
            for cls, v in sorted(per_class.items(), key=lambda kv: -kv[1]["count"])
        },
    }
    summary["n_tracks"] = len(tracks_list)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(
        f"[done]       {n_frames} frames  •  {len(detections)} detecções  •  "
        f"{len(per_class)} classes  •  {len(tracks_list)} tracks únicos"
    )
    print(f"             overlay.mp4 + detections.json + summary.json + tracks.json em {out_dir}")
    return out_dir


def _class_color(cls_id: int) -> tuple[int, int, int]:
    """Paleta determinística por class_id (BGR)."""
    palette = [
        (0, 255, 0),
        (255, 128, 0),
        (0, 128, 255),
        (255, 0, 128),
        (128, 255, 0),
        (255, 255, 0),
        (0, 255, 255),
        (255, 0, 255),
        (192, 192, 192),
        (0, 0, 255),
        (255, 255, 255),
        (128, 0, 128),
    ]
    return palette[cls_id % len(palette)]


def main():
    ap = argparse.ArgumentParser(description="Exploração YOLO bruta na câmera frontal")
    ap.add_argument("video", type=Path, help="1.mp4 ou storage/videos/1.mp4")
    ap.add_argument("--model", default="yolo11s.pt")
    ap.add_argument("--sample-fps", type=float, default=2.0)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--device", default="mps", help="mps (Mac GPU), cuda, cpu")
    args = ap.parse_args()
    run(
        args.video,
        model_name=args.model,
        sample_fps=args.sample_fps,
        conf_threshold=args.conf,
        device=args.device,
    )


if __name__ == "__main__":
    main()
