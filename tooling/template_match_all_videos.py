"""
Template matching denso em todos os 9 vídeos usando os crops da biblioteca
`sinalizacao/<categoria>/*_crop.png` como templates.

Diferença do `run_yolo_custom_all_videos.py`: aqui não usamos YOLO custom
(que overfittou em padded crops e não generaliza pra frame real). Usamos
direto `cv2.matchTemplate` com NCC, em múltiplas escalas, sobre cada
quadrante de cada frame amostrado.

Saída: `storage/analyses/<hash>/yolo_custom_detections.json` (mesmo schema
do runner anterior — bridge consome igual). Cada entrada tem `class_name`
casando uma das 5 classes da biblioteca, `match_score` (NCC peak), e o
`match_template` que casou (slug da biblioteca).

Regra: NCC >= --ncc (default 0.55) **E** persistência ≥ --min-cluster-size
(default 2 amostragens consecutivas) — filtra ruído.

Uso:
    .venv/bin/python tooling/template_match_all_videos.py
    .venv/bin/python tooling/template_match_all_videos.py --ncc 0.6 --sample-fps 1.0
    .venv/bin/python tooling/template_match_all_videos.py --only-hash 19d72ba4
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSES_DIR = PROJECT_ROOT / "storage" / "analyses"
SINALIZACAO_DIR = PROJECT_ROOT / "sinalizacao"

CATEGORIAS = [
    "vertical/pare-r1",
    "horizontal/pare-chao",
    "horizontal/faixa-pedestre",
    "horizontal/seta-esquerda",
    "horizontal/seta-reta",
]
CLASS_NAMES = [c.split("/")[-1].replace("-", "_") for c in CATEGORIAS]
CAT_TO_CLASS = dict(zip(CATEGORIAS, CLASS_NAMES))

QUADRANTE = {
    "frontal": (0, 0, 640, 360),
    "lateral_direita": (640, 0, 1280, 360),
    "interna": (0, 360, 640, 720),
    "traseira_esq": (640, 360, 1280, 720),
}

# Pra cada categoria, em quais câmeras fazer scan. Reduz custo+FP enormemente.
# (Ex.: PARE-r1 vertical não aparece na "interna" do carro.)
CATEGORIA_CAMERAS = {
    "vertical/pare-r1": ["frontal", "lateral_direita"],
    "horizontal/pare-chao": ["frontal", "traseira_esq"],
    "horizontal/faixa-pedestre": ["frontal", "lateral_direita", "traseira_esq"],
    "horizontal/seta-esquerda": ["frontal", "traseira_esq"],
    "horizontal/seta-reta": ["frontal", "traseira_esq"],
}

# Escalas relativas pra tentar match em zoom diferente (placa fica menor/maior)
SCALES = [0.7, 0.85, 1.0, 1.2, 1.5]


def _hash_to_video_filename() -> dict[str, str]:
    out: dict[str, str] = {}
    for d in ANALYSES_DIR.iterdir():
        rj = d / "result.json"
        if not rj.exists():
            continue
        try:
            data = json.loads(rj.read_text())
            fn = (data.get("video") or {}).get("filename")
            if fn:
                out[d.name] = fn
        except Exception:
            continue
    return out


def _load_templates() -> list[tuple[str, str, str, np.ndarray]]:
    """Devolve [(slug, categoria, class_name, image)]"""
    out = []
    for crop_path in sorted(SINALIZACAO_DIR.rglob("*_crop.png")):
        rel = crop_path.relative_to(SINALIZACAO_DIR)
        cat = "/".join(rel.parts[:2])
        cls = CAT_TO_CLASS.get(cat)
        if cls is None:
            continue
        meta_json = Path(str(crop_path).replace("_crop.png", ".json"))
        meta = {}
        if meta_json.exists():
            try:
                meta = json.loads(meta_json.read_text())
            except Exception:
                pass
        img = cv2.imread(str(crop_path))
        if img is None:
            continue
        upscale = meta.get("crop_upscale", 1) or 1
        if upscale > 1:
            h, w = img.shape[:2]
            img = cv2.resize(
                img, (max(8, w // upscale), max(8, h // upscale)), interpolation=cv2.INTER_AREA
            )
        out.append((crop_path.stem, cat, cls, img))
    return out


def _match_template_multiscale(
    region: np.ndarray, tpl: np.ndarray
) -> tuple[float, tuple[int, int], float]:
    """Rola NCC em múltiplas escalas; devolve (best_score, (x, y), best_scale)."""
    best = (-1.0, (0, 0), 1.0)
    th0, tw0 = tpl.shape[:2]
    rh, rw = region.shape[:2]
    for s in SCALES:
        th = max(8, int(th0 * s))
        tw = max(8, int(tw0 * s))
        if th >= rh or tw >= rw:
            continue
        if s == 1.0:
            tpl_s = tpl
        else:
            tpl_s = cv2.resize(tpl, (tw, th), interpolation=cv2.INTER_AREA)
        try:
            res = cv2.matchTemplate(region, tpl_s, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > best[0]:
                best = (float(max_val), max_loc, s)
        except cv2.error:
            continue
    return best


def _cluster_temporal(entries: list[dict], gap_s: float = 3.0) -> list[dict]:
    if not entries:
        return entries
    by_key: dict[tuple[str, str], list[dict]] = {}
    for e in entries:
        by_key.setdefault((e["class_name"], e["camera"]), []).append(e)
    out: list[dict] = []
    for items in by_key.values():
        items.sort(key=lambda x: x["ts"])
        cluster: list[dict] = []
        for e in items:
            if not cluster:
                cluster = [e]
                continue
            if e["ts"] - cluster[-1]["ts"] <= gap_s:
                cluster.append(e)
            else:
                best = max(cluster, key=lambda x: x["match_score"])
                best["cluster_size"] = len(cluster)
                best["cluster_ts_range"] = [round(cluster[0]["ts"], 1), round(cluster[-1]["ts"], 1)]
                out.append(best)
                cluster = [e]
        if cluster:
            best = max(cluster, key=lambda x: x["match_score"])
            best["cluster_size"] = len(cluster)
            best["cluster_ts_range"] = [round(cluster[0]["ts"], 1), round(cluster[-1]["ts"], 1)]
            out.append(best)
    out.sort(key=lambda e: e["ts"])
    return out


def _process_video(
    hash_: str,
    video_path: Path,
    templates: list,
    ncc_thr: float,
    sample_fps: float,
    cluster_gap_s: float,
    min_cluster_size: int,
    progress_each: int = 30,
) -> dict:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"error": f"falha ao abrir {video_path}"}
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = n_frames / fps if fps > 0 else 0.0
    step = max(1, int(round(fps / sample_fps)))

    out_dir = ANALYSES_DIR / hash_ / "yolo_custom"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_entries: list[dict] = []
    n_frames_amostrados = 0
    n_frames_processados = 0
    frame_idx = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if frame_idx % step == 0:
            ok, frame = cap.retrieve()
            if not ok or frame is None:
                frame_idx += 1
                continue
            ts = frame_idx / fps
            n_frames_amostrados += 1

            # Pra cada template, tenta match no(s) quadrante(s) plausíveis
            for slug, cat, cls, tpl in templates:
                cams = CATEGORIA_CAMERAS.get(cat, ["frontal"])
                for cam in cams:
                    qx0, qy0, qx1, qy1 = QUADRANTE[cam]
                    region = frame[qy0:qy1, qx0:qx1]
                    score, (mx, my), scale = _match_template_multiscale(region, tpl)
                    if score < ncc_thr:
                        continue
                    th0, tw0 = tpl.shape[:2]
                    th, tw = int(th0 * scale), int(tw0 * scale)
                    raw_entries.append(
                        {
                            "ts": round(float(ts), 3),
                            "frame_idx": frame_idx,
                            "camera": cam,
                            "class_name": cls,
                            "yolo_conf": round(score, 3),  # mantém schema do bridge
                            "match_score": round(score, 3),
                            "match_template": f"{slug}_crop.png",
                            "match_scale": round(scale, 2),
                            "bbox_quadrante_xyxy": [mx, my, mx + tw, my + th],
                        }
                    )
            n_frames_processados += 1
            if n_frames_processados % progress_each == 0:
                pct = (frame_idx / max(1, n_frames)) * 100
                print(
                    f"    {video_path.name}: ts={ts:6.1f}s ({pct:5.1f}%) · "
                    f"raw acumulado: {len(raw_entries)}",
                    flush=True,
                )
        frame_idx += 1
    cap.release()

    # Agrupa por (cls, cam) e pega o pico de cada janela contígua
    clustered = _cluster_temporal(raw_entries, gap_s=cluster_gap_s)
    clustered = [e for e in clustered if e.get("cluster_size", 1) >= min_cluster_size]

    # Salva 1 evidência png por evento (o crop da bbox no frame do peak)
    for e in clustered:
        cap2 = cv2.VideoCapture(str(video_path))
        cap2.set(cv2.CAP_PROP_POS_MSEC, e["ts"] * 1000)
        ok, frame = cap2.read()
        cap2.release()
        if not ok:
            continue
        cam = e["camera"]
        qx0, qy0, _, _ = QUADRANTE[cam]
        bx0, by0, bx1, by1 = e["bbox_quadrante_xyxy"]
        crop = frame[qy0 + by0 : qy0 + by1, qx0 + bx0 : qx0 + bx1]
        if crop.size == 0:
            continue
        ev_name = f"{e['ts']:09.2f}_{e['class_name']}_{cam}.png"
        ev_path = out_dir / ev_name
        cv2.imwrite(str(ev_path), crop)
        e["evidence_path"] = str(ev_path.relative_to(PROJECT_ROOT))

    return {
        "hash": hash_,
        "video": video_path.name,
        "duration_s": round(duration, 2),
        "fps": fps,
        "sample_fps": sample_fps,
        "n_frames_amostrados": n_frames_amostrados,
        "engine": "template_match_multiscale",
        "ncc_threshold": ncc_thr,
        "cluster_gap_s": cluster_gap_s,
        "min_cluster_size": min_cluster_size,
        "n_raw_detections": len(raw_entries),
        "n_after_cluster": len(clustered),
        "synced_at": datetime.now().isoformat(timespec="seconds"),
        "entries": clustered,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--ncc", type=float, default=0.55, help="NCC mínimo aceito (peak após multiscale)"
    )
    ap.add_argument("--sample-fps", type=float, default=1.0)
    ap.add_argument("--cluster-gap-s", type=float, default=3.0)
    ap.add_argument("--min-cluster-size", type=int, default=2)
    ap.add_argument("--only-hash", default=None)
    args = ap.parse_args()

    templates = _load_templates()
    if not templates:
        print("erro: nenhum template encontrado em sinalizacao/", file=sys.stderr)
        return 2
    from collections import Counter

    print(f"templates: {len(templates)} · por classe: {dict(Counter(t[2] for t in templates))}")

    h2f = _hash_to_video_filename()
    if args.only_hash:
        h2f = {h: f for h, f in h2f.items() if h.startswith(args.only_hash)}
    if not h2f:
        print("nenhum hash", file=sys.stderr)
        return 2

    print(
        f"\nprocessando {len(h2f)} vídeos · NCC>={args.ncc} · sample={args.sample_fps}fps · "
        f"cluster={args.cluster_gap_s}s · min_size={args.min_cluster_size}\n"
    )
    sumario = []
    for i, (hash_, vid_fn) in enumerate(sorted(h2f.items()), 1):
        video_path = PROJECT_ROOT / "storage" / "videos" / vid_fn
        if not video_path.exists():
            print(f"  [{i}/{len(h2f)}] {vid_fn}: arquivo não encontrado, pulando")
            continue
        print(f"  [{i}/{len(h2f)}] {hash_[:12]}  {vid_fn}")
        out = _process_video(
            hash_,
            video_path,
            templates,
            args.ncc,
            args.sample_fps,
            args.cluster_gap_s,
            args.min_cluster_size,
        )
        if out.get("error"):
            print(f"    ERRO: {out['error']}")
            continue
        c = Counter(e["class_name"] for e in out["entries"])
        n = len(out["entries"])
        print(
            f"    → raw {out['n_raw_detections']} → cluster {out['n_after_cluster']} aceitas: {dict(c)}"
        )
        out_path = ANALYSES_DIR / hash_ / "yolo_custom_detections.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        sumario.append({"hash": hash_, "video": vid_fn, "n": n, "por_classe": dict(c)})

    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    total = 0
    for s in sumario:
        total += s["n"]
        print(f"  {s['hash'][:12]}  {s['video'][:50]:50s} {s['n']:3d}  {s['por_classe']}")
    print(f"\n  TOTAL: {total} detecções")
    return 0


if __name__ == "__main__":
    sys.exit(main())
