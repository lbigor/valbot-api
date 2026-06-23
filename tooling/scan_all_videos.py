"""
scan_all_videos — simulação completa: roda detectores clássicos em todos os
vídeos de storage/videos/ usando a biblioteca sinalizacao/ como referência
de categorias.

Detectores aplicados:
  - PareSignDetector (vertical/pare-r1) → cam frontal + traseira
  - RoadTextDetector  (horizontal/pare-chao) → cam frontal
  - CrosswalkDetector (horizontal/faixa-pedestre) → cam frontal + traseira

Saída por vídeo:
  storage/analyses/<hash>/sinalizacao_scan.json   (hits temporais por categoria)

Saída agregada:
  storage/training/dataset_master/SIMULACAO_<TIMESTAMP>.json (resumo cross-vídeo)
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from src.detectors.crosswalk import CrosswalkDetector
from src.detectors.pare_sign import PareSignDetector
from src.detectors.road_text import RoadTextDetector
from src.ingestion.grid_slicer import GridSlicer

ROOT = Path(__file__).resolve().parents[1]
VIDEOS_DIR = ROOT / "storage" / "videos"
ANALYSES = ROOT / "storage" / "analyses"
DATASET_DIR = ROOT / "storage" / "training" / "dataset_master"


def video_hash(path: Path) -> str:
    """Hash compatível com a convenção do orchestrator (SHA-256 do path absoluto)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
            if h.block_size >= 1024 * 1024 * 8:  # primeiros 8MB já bastam
                break
    return h.hexdigest()


def existing_hash_for_video(video_path: Path) -> str | None:
    """Procura hash já existente em storage/analyses/<hash>/result.json."""
    if not ANALYSES.exists():
        return None
    target = str(video_path)
    for d in ANALYSES.iterdir():
        rp = d / "result.json"
        if not rp.exists():
            continue
        try:
            data = json.loads(rp.read_text())
            if data.get("video", {}).get("path") == target:
                return d.name
        except Exception:
            pass
    return None


def scan_video(video_path: Path, sample_fps: float = 1.0) -> dict:
    """Roda 3 detectores no vídeo e retorna estrutura agregada."""
    slicer = GridSlicer(video_path, sample_fps=sample_fps)
    pare = PareSignDetector()
    road = RoadTextDetector()
    cross = CrosswalkDetector()

    hits = {
        "vertical/pare-r1": [],
        "horizontal/pare-chao": [],
        "horizontal/faixa-pedestre": [],
    }

    n_frames = 0
    for grid in slicer.iter_frames():
        n_frames += 1
        ts = grid.timestamp_s

        # 1) placa R-1 (frontal + traseira)
        for cam_name, cam_img in [("frontal", grid.frontal), ("traseira_esq", grid.traseira_esq)]:
            try:
                r = pare.detect(cam_img, frame_idx=grid.frame_idx, timestamp_s=ts)
                if r and r.detected and r.confidence > 0.4:
                    hits["vertical/pare-r1"].append(
                        {
                            "ts": round(ts, 1),
                            "ts_label": f"{int(ts // 60):02d}:{int(ts % 60):02d}",
                            "camera": cam_name,
                            "bbox_xyxy": list(r.bbox) if r.bbox else None,
                            "confidence": float(r.confidence),
                        }
                    )
            except Exception:
                pass

        # 2) PARE chão (só frontal)
        try:
            r = road.detect(grid.frontal, frame_idx=grid.frame_idx, timestamp_s=ts)
            if r and r.detected and r.confidence > 0.4:
                hits["horizontal/pare-chao"].append(
                    {
                        "ts": round(ts, 1),
                        "ts_label": f"{int(ts // 60):02d}:{int(ts % 60):02d}",
                        "camera": "frontal",
                        "bbox_xyxy": list(r.bbox) if r.bbox else None,
                        "confidence": float(r.confidence),
                    }
                )
        except Exception:
            pass

        # 3) faixa pedestre (frontal + traseira)
        for cam_name, cam_img in [("frontal", grid.frontal), ("traseira_esq", grid.traseira_esq)]:
            try:
                r = cross.detect(cam_img, frame_idx=grid.frame_idx, timestamp_s=ts)
                if r and r.detected and r.confidence > 0.4:
                    hits["horizontal/faixa-pedestre"].append(
                        {
                            "ts": round(ts, 1),
                            "ts_label": f"{int(ts // 60):02d}:{int(ts % 60):02d}",
                            "camera": cam_name,
                            "bbox_xyxy": list(r.bbox) if r.bbox else None,
                            "confidence": float(r.confidence),
                        }
                    )
            except Exception:
                pass

    # dedupe temporal: agrupa hits da mesma categoria/câmera com gap <= 3s em
    # eventos contínuos. Evita inflar contagem (mesma sinalização vista por
    # vários frames consecutivos = 1 evento, não N hits).
    eventos = {cat: [] for cat in hits}
    for cat, lst in hits.items():
        # ordena por câmera+ts
        lst_sorted = sorted(lst, key=lambda h: (h["camera"], h["ts"]))
        if not lst_sorted:
            continue
        cur = {
            "camera": lst_sorted[0]["camera"],
            "ts_start": lst_sorted[0]["ts"],
            "ts_end": lst_sorted[0]["ts"],
            "n_frames": 1,
            "max_confidence": lst_sorted[0]["confidence"],
            "bbox_first": lst_sorted[0]["bbox_xyxy"],
        }
        for h in lst_sorted[1:]:
            same_cam = h["camera"] == cur["camera"]
            close_ts = h["ts"] - cur["ts_end"] <= 3.0
            if same_cam and close_ts:
                cur["ts_end"] = h["ts"]
                cur["n_frames"] += 1
                cur["max_confidence"] = max(cur["max_confidence"], h["confidence"])
            else:
                eventos[cat].append(cur)
                cur = {
                    "camera": h["camera"],
                    "ts_start": h["ts"],
                    "ts_end": h["ts"],
                    "n_frames": 1,
                    "max_confidence": h["confidence"],
                    "bbox_first": h["bbox_xyxy"],
                }
        eventos[cat].append(cur)

    # filtro de confiança: só eventos com max_confidence >= 0.5
    eventos_filtrados = {
        cat: [e for e in evs if e["max_confidence"] >= 0.5 and e["n_frames"] >= 1]
        for cat, evs in eventos.items()
    }

    return {
        "video": str(video_path.relative_to(ROOT)),
        "duration_s": slicer.duration_s,
        "n_frames_scanned": n_frames,
        "sample_fps": sample_fps,
        "n_hits_brutos": {k: len(v) for k, v in hits.items()},
        "n_eventos": {k: len(v) for k, v in eventos_filtrados.items()},
        "eventos": eventos_filtrados,
        "hits_brutos": hits,
    }


def main():
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    videos = sorted(VIDEOS_DIR.glob("*.mp4"))
    if not videos:
        sys.exit(f"sem vídeos em {VIDEOS_DIR}")

    print(f"Simulação em {len(videos)} vídeos\n")
    summary = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "n_videos": len(videos),
        "videos": [],
    }

    for i, vp in enumerate(videos, 1):
        print(f"[{i}/{len(videos)}] {vp.name}")
        try:
            result = scan_video(vp, sample_fps=1.0)
        except Exception as e:
            print(f"  ERRO: {e}")
            continue

        # salva no diretório da análise se existe, senão cria pasta nova
        h = existing_hash_for_video(vp)
        if h is None:
            h = video_hash(vp)
        out_dir = ANALYSES / h
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "sinalizacao_scan.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))

        result["hash"] = h
        result["scan_path"] = str(out_path.relative_to(ROOT))
        summary["videos"].append(
            {
                "video": result["video"],
                "duration_s": result["duration_s"],
                "hash": h,
                "n_hits_brutos": result["n_hits_brutos"],
                "n_eventos": result["n_eventos"],
                "scan_path": result["scan_path"],
            }
        )
        ne = result["n_eventos"]
        nh = result["n_hits_brutos"]
        print(
            f"  eventos → R-1:{ne['vertical/pare-r1']:2d}  PARE-chao:{ne['horizontal/pare-chao']:2d}  faixa:{ne['horizontal/faixa-pedestre']:2d}"
            f"   (brutos: {sum(nh.values())})"
        )

    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_summary = DATASET_DIR / f"SIMULACAO_{ts_tag}.json"
    out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    # totais
    print("\n=== RESUMO (eventos dedupados, conf>=0.5) ===")
    totals_ev = defaultdict(int)
    totals_hits = defaultdict(int)
    for v in summary["videos"]:
        for cat, n in v["n_eventos"].items():
            totals_ev[cat] += n
        for cat, n in v["n_hits_brutos"].items():
            totals_hits[cat] += n
    for cat in totals_ev:
        print(f"  {cat}: {totals_ev[cat]} eventos  ({totals_hits[cat]} hits brutos)")
    print(f"\nResumo agregado: {out_summary.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
