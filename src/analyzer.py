"""
VALBOT Analyzer — pipeline principal end-to-end.

Uso:
    python -m src.analyzer video.mp4 --output laudo.json
"""

import argparse
import json
import time
from pathlib import Path

from src.ingestion.grid_slicer import GridSlicer
from src.ingestion.keyframe_detector import KeyframeDetector
from src.rubrics.taxonomia import Rubrica


def run_pipeline(
    video_path: Path,
    rubrica: Rubrica,
    output_json: Path,
    sample_fps: float = 1.0,
    use_cloud: bool = True,
    max_frames: int | None = None,
) -> dict:
    t0 = time.time()

    # 1. Ingestão
    slicer = GridSlicer(video_path, sample_fps=sample_fps)
    meta = slicer.metadata()
    print(
        f"[ingestão] {meta['duration_s']:.1f}s @ {meta['fps']:.1f}fps, "
        f"grid {meta['width']}x{meta['height']}"
    )

    all_frames = list(slicer.iter_frames())
    if max_frames:
        all_frames = all_frames[:max_frames]
    print(f"[ingestão] {len(all_frames)} frames amostrados")

    # 2. Detecção de keyframes
    detector = KeyframeDetector()
    keyframes = detector.detect(all_frames)
    print(
        f"[keyframes] {len(keyframes)} de {len(all_frames)} "
        f"({100 * len(keyframes) / max(1, len(all_frames)):.1f}%)"
    )

    # 3. Aqui entraria o chamado ao VLM (HybridVLMEngine)
    # Por simplicidade, esta versão do analyzer apenas reporta keyframes
    report = {
        "video": meta,
        "rubrica": rubrica.value,
        "keyframes_detected": len(keyframes),
        "keyframes": [
            {
                "timestamp_s": kf.timestamp_s,
                "frame_idx": kf.frame_idx,
                "score": kf.score,
                "reasons": [r.value for r in kf.reasons],
                "camera_hint": kf.camera_hint,
            }
            for kf in keyframes[:50]
        ],
        "elapsed_s": round(time.time() - t0, 1),
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"[saída] {output_json}  — {report['elapsed_s']}s")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--rubrica", choices=["1020_2025"], default="1020_2025")
    ap.add_argument("--output", type=Path, default=Path("./output/report.json"))
    ap.add_argument("--sample-fps", type=float, default=1.0)
    ap.add_argument("--no-cloud", action="store_true")
    ap.add_argument("--max-frames", type=int, default=None)
    args = ap.parse_args()

    run_pipeline(
        video_path=args.video,
        rubrica=Rubrica(args.rubrica),
        output_json=args.output,
        sample_fps=args.sample_fps,
        use_cloud=not args.no_cloud,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    main()
