"""
Treina YOLO custom em cima dos 13 crops anotados em sinalizacao/.

Regra (definida pelo usuário): cada anotação em sinalizacao/ é ground truth.
O modelo só termina quando reconhece TODOS os crops na validação.

Pipeline:
  1. Lê todos os `*_crop.png` + `.json` em sinalizacao/
  2. Cada categoria vira uma classe (pare_r1, pare_chao, faixa_pedestre,
     seta_esquerda, seta_reta)
  3. Constrói dataset YOLO format em storage/training/dataset_sinalizacao/:
       - images/train/<slug>.png  (o crop, padded p/ 640x640)
       - labels/train/<slug>.txt  (bbox = região central, normalizado)
       - data.yaml
  4. Roda mosaic augmentation built-in do Ultralytics
  5. Treina com freeze=10 (transfer learning) + N épocas
  6. Valida no diretório original — `model.predict(crops/)`
  7. Loop até match=100% ou max_iterations

Uso:
  python tooling/yolo_train_sinalizacao.py --epochs 30 --max-iters 3
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SINALIZACAO_DIR = PROJECT_ROOT / "sinalizacao"
DATASET_DIR = PROJECT_ROOT / "storage" / "training" / "dataset_sinalizacao"
RUNS_DIR = PROJECT_ROOT / "storage" / "training" / "yolo_runs_sinalizacao"
WEIGHTS_BASE = PROJECT_ROOT / "yolo11s.pt"

CATEGORIAS = [
    "vertical/pare-r1",
    "horizontal/pare-chao",
    "horizontal/faixa-pedestre",
    "horizontal/seta-esquerda",
    "horizontal/seta-reta",
]
CLASS_NAMES = [c.split("/")[-1].replace("-", "_") for c in CATEGORIAS]
CAT_TO_CLS = {c: i for i, c in enumerate(CATEGORIAS)}

CANVAS_SIZE = 640


def _category_from_path(p: Path) -> str:
    parts = p.relative_to(SINALIZACAO_DIR).parts
    return "/".join(parts[:2]) if len(parts) >= 2 else "/".join(parts)


def _pad_to_canvas(
    img: np.ndarray, canvas_size: int = CANVAS_SIZE
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Centraliza img num canvas canvas_size×canvas_size, devolve (canvas, bbox_xyxy)."""
    h, w = img.shape[:2]
    if h > canvas_size or w > canvas_size:
        s = canvas_size / max(h, w)
        new_w, new_h = int(w * s), int(h * s)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        h, w = new_h, new_w
    canvas = np.full((canvas_size, canvas_size, 3), 114, dtype=np.uint8)
    x0 = (canvas_size - w) // 2
    y0 = (canvas_size - h) // 2
    canvas[y0 : y0 + h, x0 : x0 + w] = img
    return canvas, (x0, y0, x0 + w, y0 + h)


def _bbox_to_yolo(
    bbox_xyxy: tuple[int, int, int, int], canvas_size: int = CANVAS_SIZE
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = bbox_xyxy
    cx = (x0 + x1) / 2 / canvas_size
    cy = (y0 + y1) / 2 / canvas_size
    w = (x1 - x0) / canvas_size
    h = (y1 - y0) / canvas_size
    return cx, cy, w, h


def _build_dataset() -> dict:
    """Constrói dataset YOLO format e devolve estatísticas."""
    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)
    (DATASET_DIR / "images" / "train").mkdir(parents=True)
    (DATASET_DIR / "images" / "val").mkdir(parents=True)
    (DATASET_DIR / "labels" / "train").mkdir(parents=True)
    (DATASET_DIR / "labels" / "val").mkdir(parents=True)

    crops = sorted(SINALIZACAO_DIR.rglob("*_crop.png"))
    stats = {"total": 0, "por_classe": dict.fromkeys(CLASS_NAMES, 0)}
    samples_per_class: dict[int, list[str]] = {i: [] for i in range(len(CLASS_NAMES))}
    for crop in crops:
        cat = _category_from_path(crop)
        if cat not in CAT_TO_CLS:
            continue
        cls = CAT_TO_CLS[cat]
        cls_name = CLASS_NAMES[cls]
        img = cv2.imread(str(crop))
        if img is None:
            print(f"  warn: falha ao ler {crop}", file=sys.stderr)
            continue
        canvas, bbox = _pad_to_canvas(img, CANVAS_SIZE)
        cx, cy, w, h = _bbox_to_yolo(bbox, CANVAS_SIZE)

        slug = crop.stem
        out_img = DATASET_DIR / "images" / "train" / f"{slug}.png"
        out_lbl = DATASET_DIR / "labels" / "train" / f"{slug}.txt"
        cv2.imwrite(str(out_img), canvas)
        out_lbl.write_text(f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
        samples_per_class[cls].append(slug)
        stats["por_classe"][cls_name] += 1
        stats["total"] += 1

    # Val set: 1 amostra por classe (com ≥2 amostras), copiada de train.
    for cls, slugs in samples_per_class.items():
        if len(slugs) < 2:
            continue
        val_slug = slugs[-1]
        for sub in ("images", "labels"):
            ext = ".png" if sub == "images" else ".txt"
            src = DATASET_DIR / sub / "train" / f"{val_slug}{ext}"
            dst = DATASET_DIR / sub / "val" / f"{val_slug}{ext}"
            shutil.copy2(src, dst)

    # Se classe tem só 1 amostra, copia a mesma pra val pra não quebrar o val loop.
    for cls, slugs in samples_per_class.items():
        if len(slugs) == 1:
            for sub in ("images", "labels"):
                ext = ".png" if sub == "images" else ".txt"
                src = DATASET_DIR / sub / "train" / f"{slugs[0]}{ext}"
                dst = DATASET_DIR / sub / "val" / f"{slugs[0]}{ext}"
                shutil.copy2(src, dst)

    yaml_path = DATASET_DIR / "data.yaml"
    yaml_path.write_text(
        f"path: {DATASET_DIR}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n" + "\n".join(f"  {i}: {n}" for i, n in enumerate(CLASS_NAMES)) + "\n"
    )
    stats["yaml"] = str(yaml_path)
    return stats


def _validate_on_crops(weights_path: Path, conf: float = 0.25) -> dict:
    """Roda model.predict em cada crop, devolve {slug: (matched_class_id, conf)}."""
    from ultralytics import YOLO

    model = YOLO(str(weights_path))
    crops = sorted(SINALIZACAO_DIR.rglob("*_crop.png"))
    results: dict[str, dict] = {}
    for crop in crops:
        cat = _category_from_path(crop)
        if cat not in CAT_TO_CLS:
            continue
        expected_cls = CAT_TO_CLS[cat]
        # Roda no crop padded (mesmo input size do treino)
        img = cv2.imread(str(crop))
        canvas, _ = _pad_to_canvas(img, CANVAS_SIZE)
        r = model.predict(canvas, conf=conf, verbose=False, imgsz=CANVAS_SIZE)[0]
        match = None
        for cls, cf in zip(r.boxes.cls.cpu().numpy(), r.boxes.conf.cpu().numpy()):
            if int(cls) == expected_cls:
                if match is None or cf > match["conf"]:
                    match = {"cls": int(cls), "conf": round(float(cf), 3)}
        results[crop.stem] = {
            "expected": CLASS_NAMES[expected_cls],
            "matched": match is not None,
            "match_conf": match["conf"] if match else None,
            "n_detections": len(r.boxes.cls),
        }
    return results


def _print_validation(results: dict) -> tuple[int, int]:
    n_ok = sum(1 for v in results.values() if v["matched"])
    n_total = len(results)
    print(f"\n  validação: {n_ok}/{n_total} crops com match")
    for slug, v in results.items():
        emoji = "✅" if v["matched"] else "❌"
        conf_s = f"conf={v['match_conf']}" if v["matched"] else f"n_det={v['n_detections']}"
        print(f"    {emoji} {slug:<48s} {v['expected']:<18s} {conf_s}")
    return n_ok, n_total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument(
        "--max-iters",
        type=int,
        default=3,
        help="quantas vezes retreinar caso match abaixo de 100 pct",
    )
    ap.add_argument("--imgsz", type=int, default=CANVAS_SIZE)
    ap.add_argument(
        "--freeze", type=int, default=10, help="qts camadas backbone congelar (transfer learning)"
    )
    ap.add_argument("--device", default="cpu", help="cpu | mps | 0")
    args = ap.parse_args()

    print("==> construindo dataset")
    stats = _build_dataset()
    print(f"    total: {stats['total']} amostras · classes: {stats['por_classe']}")
    print(f"    yaml: {stats['yaml']}")

    from ultralytics import YOLO

    weights_path = WEIGHTS_BASE
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    for it in range(1, args.max_iters + 1):
        run_name = f"sinal_iter{it}_{datetime.now().strftime('%H%M%S')}"
        print(f"\n==> iteração {it}/{args.max_iters} · base weights: {weights_path.name}")

        model = YOLO(str(weights_path))
        model.train(
            data=str(DATASET_DIR / "data.yaml"),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=4,
            freeze=args.freeze,
            device=args.device,
            project=str(RUNS_DIR),
            name=run_name,
            patience=10,
            mosaic=1.0,
            degrees=10.0,
            translate=0.1,
            scale=0.3,
            fliplr=0.0,  # desliga flip horizontal — setas são direcionais
            flipud=0.0,
            hsv_h=0.015,
            hsv_s=0.4,
            hsv_v=0.3,
            verbose=False,
            plots=False,
            save_period=-1,
            exist_ok=True,
        )

        weights_path = RUNS_DIR / run_name / "weights" / "best.pt"
        if not weights_path.exists():
            weights_path = RUNS_DIR / run_name / "weights" / "last.pt"
        if not weights_path.exists():
            print(f"  erro: sem weights gerados em {weights_path.parent}", file=sys.stderr)
            return 2

        print("==> validando contra os 13 crops originais (conf=0.25)…")
        results = _validate_on_crops(weights_path, conf=0.25)
        n_ok, n_total = _print_validation(results)
        if n_ok == n_total:
            print(f"\n🎯 100% match em {it} iteração(ões). Parando.")
            print(f"weights finais: {weights_path}")
            return 0
        # Próxima iteração: dobra épocas, retoma desse weights.
        args.epochs = int(args.epochs * 1.5)
        print(f"  {n_total - n_ok} ainda falham → próxima iter: {args.epochs} épocas")

    print(f"\n⚠️  parou após {args.max_iters} iter sem 100% match. weights finais: {weights_path}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
