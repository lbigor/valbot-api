"""
Roda YOLO custom (treinado em sinalizacao/) em todos os 9 vídeos do dataset
e persiste as detecções validadas como `yolo_custom_detections.json` por hash.

Regra dura (definida pelo usuário): nada sobe pro painel sem timestamp validado.
Detecção do YOLO só é aceita se passar **template matching** (NCC) contra ao
menos um crop_png da mesma classe na biblioteca — exatamente o filtro do
`sync_sinalizacao_to_panel.py`. YOLO encontra "candidato"; biblioteca confirma
"é mesmo a placa".

Saída por hash:
  storage/analyses/<hash>/yolo_custom_detections.json
  storage/analyses/<hash>/yolo_custom/<ts>_<cls>_<cam>.png  (evidência)

Uso:
    .venv/bin/python tooling/run_yolo_custom_all_videos.py
    .venv/bin/python tooling/run_yolo_custom_all_videos.py --conf 0.25 --ncc 0.35
    .venv/bin/python tooling/run_yolo_custom_all_videos.py --only-hash 19d72ba4
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
WEIGHTS = (
    PROJECT_ROOT
    / "storage"
    / "training"
    / "yolo_runs_sinalizacao"
    / "sinal_iter1_104852"
    / "weights"
    / "best.pt"
)

CATEGORIAS = [
    "vertical/pare-r1",
    "horizontal/pare-chao",
    "horizontal/faixa-pedestre",
    "horizontal/seta-esquerda",
    "horizontal/seta-reta",
]
CLASS_NAMES = [c.split("/")[-1].replace("-", "_") for c in CATEGORIAS]
CLASS_TO_CATEGORIA = dict(zip(CLASS_NAMES, CATEGORIAS))

# Layout de quadrantes do mosaic 1280×720 (camera_resolution 640×360 cada).
QUADRANTE = {
    "frontal": (0, 0, 640, 360),
    "lateral_direita": (640, 0, 1280, 360),
    "interna": (0, 360, 640, 720),
    "traseira_esq": (640, 360, 1280, 720),
}


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


def _load_templates() -> dict[str, list[tuple[str, np.ndarray]]]:
    """Lê todos os _crop.png da biblioteca, indexados por classe (já no tamanho real)."""
    out: dict[str, list[tuple[str, np.ndarray]]] = {n: [] for n in CLASS_NAMES}
    for crop_path in sorted(SINALIZACAO_DIR.rglob("*_crop.png")):
        rel = crop_path.relative_to(SINALIZACAO_DIR)
        cat = "/".join(rel.parts[:2])
        cls = next((n for n, c in CLASS_TO_CATEGORIA.items() if c == cat), None)
        if cls is None:
            continue
        meta_json = Path(str(crop_path).replace("_crop.png", ".json"))
        if not meta_json.exists():
            continue
        try:
            meta = json.loads(meta_json.read_text())
        except Exception:
            continue
        img = cv2.imread(str(crop_path))
        if img is None:
            continue
        upscale = meta.get("crop_upscale", 1) or 1
        if upscale > 1:
            h, w = img.shape[:2]
            img = cv2.resize(img, (w // upscale, h // upscale), interpolation=cv2.INTER_AREA)
        out[cls].append((crop_path.name, img))
    return out


def _ncc_best(
    region: np.ndarray, templates: list[tuple[str, np.ndarray]]
) -> tuple[float, str | None]:
    """Match NCC do recorte contra todos os templates da classe; devolve (best_score, template_name)."""
    rh, rw = region.shape[:2]
    best_score = -1.0
    best_name = None
    for name, tpl in templates:
        th, tw = tpl.shape[:2]
        if th >= rh or tw >= rw or th < 4 or tw < 4:
            # Tenta match no inverso: redimensiona o template pra caber
            scale = min(rh / max(th, 1), rw / max(tw, 1)) * 0.9
            if scale <= 0.2:
                continue
            tpl_r = cv2.resize(tpl, (max(4, int(tw * scale)), max(4, int(th * scale))))
            th, tw = tpl_r.shape[:2]
            if th >= rh or tw >= rw:
                continue
            tpl = tpl_r
        try:
            res = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if max_val > best_score:
                best_score = float(max_val)
                best_name = name
        except cv2.error:
            continue
    return best_score, best_name


def _cluster_temporal(entries: list[dict], gap_s: float = 3.0) -> list[dict]:
    """Agrupa detecções próximas no tempo (mesma class+camera) e fica com a peak NCC.

    YOLO custom é hiper-eager (overfittou em crops centrados); muitas detecções
    consecutivas no mesmo segundo são a "mesma observação". Clusterizar reduz
    ruído e mantém só o pico de cada janela contígua.
    """
    if not entries:
        return entries
    by_key: dict[tuple[str, str], list[dict]] = {}
    for e in entries:
        by_key.setdefault((e["class_name"], e["camera"]), []).append(e)
    out: list[dict] = []
    for key, items in by_key.items():
        items.sort(key=lambda x: x["ts"])
        cluster: list[dict] = []
        for e in items:
            if not cluster:
                cluster = [e]
                continue
            if e["ts"] - cluster[-1]["ts"] <= gap_s:
                cluster.append(e)
            else:
                # fecha cluster: pega o de maior match_score
                best = max(cluster, key=lambda x: (x["match_score"], x["yolo_conf"]))
                best["cluster_size"] = len(cluster)
                best["cluster_ts_range"] = [round(cluster[0]["ts"], 1), round(cluster[-1]["ts"], 1)]
                out.append(best)
                cluster = [e]
        if cluster:
            best = max(cluster, key=lambda x: (x["match_score"], x["yolo_conf"]))
            best["cluster_size"] = len(cluster)
            best["cluster_ts_range"] = [round(cluster[0]["ts"], 1), round(cluster[-1]["ts"], 1)]
            out.append(best)
    out.sort(key=lambda e: e["ts"])
    return out


def _process_video(
    hash_: str,
    video_path: Path,
    templates: dict[str, list],
    model,
    conf_thr: float,
    ncc_thr: float,
    sample_fps: float = 1.0,
    progress_each: int = 30,
    cluster_gap_s: float = 3.0,
    min_cluster_size: int = 2,
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

    entries: list[dict] = []
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
            for cam, (qx0, qy0, qx1, qy1) in QUADRANTE.items():
                region = frame[qy0:qy1, qx0:qx1]
                r = model.predict(region, conf=conf_thr, imgsz=640, verbose=False)[0]
                for cls_t, conf_t, bb in zip(
                    r.boxes.cls.cpu().numpy(),
                    r.boxes.conf.cpu().numpy(),
                    r.boxes.xyxy.cpu().numpy(),
                ):
                    cls_id = int(cls_t)
                    cls_name = r.names[cls_id]
                    bx0, by0, bx1, by1 = [int(v) for v in bb]
                    bx0 = max(0, bx0)
                    by0 = max(0, by0)
                    bx1 = min(region.shape[1], bx1)
                    by1 = min(region.shape[0], by1)
                    if (bx1 - bx0) < 8 or (by1 - by0) < 8:
                        continue
                    crop = region[by0:by1, bx0:bx1]
                    score, tpl_name = _ncc_best(crop, templates.get(cls_name, []))
                    if score < ncc_thr:
                        continue
                    # Salva evidência
                    safe_cam = cam.replace("/", "_")
                    ev_name = f"{ts:09.2f}_{cls_name}_{safe_cam}.png"
                    ev_path = out_dir / ev_name
                    cv2.imwrite(str(ev_path), crop)
                    entries.append(
                        {
                            "ts": round(float(ts), 3),
                            "frame_idx": frame_idx,
                            "camera": cam,
                            "class_name": cls_name,
                            "yolo_conf": round(float(conf_t), 3),
                            "match_score": round(float(score), 3),
                            "match_template": tpl_name,
                            "bbox_quadrante_xyxy": [bx0, by0, bx1, by1],
                            "evidence_path": str(ev_path.relative_to(PROJECT_ROOT)),
                        }
                    )
            n_frames_processados += 1
            if n_frames_processados % progress_each == 0:
                pct = (frame_idx / max(1, n_frames)) * 100
                print(
                    f"    {video_path.name}: ts={ts:6.1f}s ({pct:5.1f}%) · "
                    f"detecções acumuladas: {len(entries)}",
                    flush=True,
                )
        frame_idx += 1
    cap.release()

    n_raw = len(entries)
    clustered = _cluster_temporal(entries, gap_s=cluster_gap_s)
    # Filtro pós-cluster: só aceita se cluster tem ≥ min_cluster_size frames
    # (sinal que persistiu pelo menos N amostragens, ≈ ruído filtrado)
    clustered = [e for e in clustered if e.get("cluster_size", 1) >= min_cluster_size]
    n_clusters = len(clustered)

    return {
        "hash": hash_,
        "video": video_path.name,
        "duration_s": round(duration, 2),
        "fps": fps,
        "sample_fps": sample_fps,
        "n_frames_amostrados": n_frames_amostrados,
        "conf_threshold": conf_thr,
        "ncc_threshold": ncc_thr,
        "cluster_gap_s": cluster_gap_s,
        "min_cluster_size": min_cluster_size,
        "n_raw_detections": n_raw,
        "n_after_cluster": n_clusters,
        "model": WEIGHTS.name,
        "synced_at": datetime.now().isoformat(timespec="seconds"),
        "entries": clustered,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--conf", type=float, default=0.55, help="conf threshold YOLO")
    ap.add_argument("--ncc", type=float, default=0.55, help="NCC mínimo p/ aceitar")
    ap.add_argument("--sample-fps", type=float, default=1.0, help="frames/seg amostrados")
    ap.add_argument(
        "--cluster-gap-s",
        type=float,
        default=3.0,
        help="agrupa detecções consecutivas dentro desse gap em 1 evento",
    )
    ap.add_argument(
        "--min-cluster-size",
        type=int,
        default=2,
        help="rejeita evento que não persistiu por ao menos N amostragens",
    )
    ap.add_argument("--only-hash", default=None, help="processar só o hash que comece com isso")
    args = ap.parse_args()

    if not WEIGHTS.exists():
        print(f"erro: weights não encontrados em {WEIGHTS}", file=sys.stderr)
        return 2

    from ultralytics import YOLO

    print(f"carregando {WEIGHTS.relative_to(PROJECT_ROOT)}…")
    model = YOLO(str(WEIGHTS))
    print(f"classes: {list(model.names.values())}")

    templates = _load_templates()
    print("templates por classe: " + ", ".join(f"{k}={len(v)}" for k, v in templates.items()))

    h2f = _hash_to_video_filename()
    if args.only_hash:
        h2f = {h: f for h, f in h2f.items() if h.startswith(args.only_hash)}
    if not h2f:
        print("nenhum hash encontrado", file=sys.stderr)
        return 2

    print(
        f"\nprocessando {len(h2f)} vídeos (conf>={args.conf}, NCC>={args.ncc}, sample={args.sample_fps}fps)\n"
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
            model,
            args.conf,
            args.ncc,
            args.sample_fps,
            cluster_gap_s=args.cluster_gap_s,
            min_cluster_size=args.min_cluster_size,
        )
        if out.get("error"):
            print(f"    ERRO: {out['error']}")
            continue
        # Conta por classe
        from collections import Counter

        c = Counter(e["class_name"] for e in out["entries"])
        n = len(out["entries"])
        print(f"    → {n} detecções aceitas: {dict(c)}")
        # Persiste
        out_path = ANALYSES_DIR / hash_ / "yolo_custom_detections.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        sumario.append({"hash": hash_, "video": vid_fn, "n": n, "por_classe": dict(c)})

    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    total = 0
    for s in sumario:
        total += s["n"]
        print(f"  {s['hash'][:12]}  {s['video']:50s} {s['n']:3d}  {s['por_classe']}")
    print(f"\n  TOTAL: {total} detecções validadas em {len(sumario)} vídeos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
