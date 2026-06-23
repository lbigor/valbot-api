"""
Roda YOLO em cada crop anotado em sinalizacao/ e reporta:
- categoria esperada (do path: vertical/pare-r1, horizontal/seta-esquerda, etc)
- classes COCO detectadas (com conf por threshold) na imagem do crop
- gap: o que YOLO precisaria pra "entender" a anotação

Mapeamento categoria → classe COCO esperada:
  vertical/pare-r1     → stop sign        (id 11)
  horizontal/*         → (sem classe COCO; YOLO base não reconhece pintura no chão)

O script roda em múltiplos conf thresholds (0.05 → 0.50) pra encontrar o menor
threshold que ainda casa, e gera um relatório markdown salvando em
storage/training/yolo_validation_<timestamp>.md.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SINALIZACAO_DIR = PROJECT_ROOT / "sinalizacao"
OUT_DIR = PROJECT_ROOT / "storage" / "training"
WEIGHTS = PROJECT_ROOT / "yolo11s.pt"

# COCO class id que faz sentido pra cada categoria de sinalização da biblioteca.
# `None` = COCO não tem classe; modelo base é cego.
EXPECTED_COCO = {
    "vertical/pare-r1": ("stop sign", 11),
    "horizontal/pare-chao": (None, None),
    "horizontal/faixa-pedestre": (None, None),
    "horizontal/seta-esquerda": (None, None),
    "horizontal/seta-reta": (None, None),
}

CONF_THRESHOLDS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]


def _category_from_path(p: Path) -> str:
    parts = p.relative_to(SINALIZACAO_DIR).parts
    return "/".join(parts[:2]) if len(parts) >= 2 else "/".join(parts)


def main() -> int:
    from ultralytics import YOLO

    crops = sorted(SINALIZACAO_DIR.rglob("*_crop.png"))
    if not crops:
        print("nenhum crop encontrado em", SINALIZACAO_DIR, file=sys.stderr)
        return 2

    print(f"carregando {WEIGHTS.name}…")
    model = YOLO(str(WEIGHTS))
    print(f"validando {len(crops)} crops em {len(CONF_THRESHOLDS)} thresholds")

    rows: list[dict] = []
    for crop in crops:
        cat = _category_from_path(crop)
        expected_cls, expected_id = EXPECTED_COCO.get(cat, (None, None))
        meta_json = crop.with_suffix("").with_suffix(".json")
        if not meta_json.exists():
            meta_json = Path(str(crop).replace("_crop.png", ".json"))
        meta = json.loads(meta_json.read_text()) if meta_json.exists() else {}

        per_threshold: list[dict] = []
        primeiro_match_conf: float | None = None
        primeiro_match_real: float | None = None
        for thr in CONF_THRESHOLDS:
            results = model.predict(
                source=str(crop),
                conf=thr,
                verbose=False,
                save=False,
                imgsz=640,
            )
            r = results[0]
            detected = []
            for box, cls, conf in zip(
                r.boxes.xyxy.cpu().numpy(),
                r.boxes.cls.cpu().numpy(),
                r.boxes.conf.cpu().numpy(),
            ):
                detected.append(
                    {
                        "class_id": int(cls),
                        "class_name": r.names[int(cls)],
                        "conf": round(float(conf), 3),
                        "bbox": [round(float(x), 1) for x in box],
                    }
                )
            match = None
            if expected_id is not None:
                match = next(
                    (d for d in detected if d["class_id"] == expected_id),
                    None,
                )
            per_threshold.append(
                {
                    "threshold": thr,
                    "n_detected": len(detected),
                    "detected": detected[:5],
                    "match": match,
                }
            )
            if match and primeiro_match_conf is None:
                primeiro_match_conf = thr
                primeiro_match_real = match["conf"]

        row = {
            "crop": str(crop.relative_to(PROJECT_ROOT)),
            "categoria": cat,
            "tipo_contran": meta.get("tipo_contran", ""),
            "label_text": meta.get("label_text", ""),
            "expected_coco_class": expected_cls,
            "expected_coco_id": expected_id,
            "primeiro_match_threshold": primeiro_match_conf,
            "primeiro_match_conf_real": primeiro_match_real,
            "por_threshold": per_threshold,
        }
        rows.append(row)
        status = (
            f"✅ match em conf≥{primeiro_match_conf} (real={primeiro_match_real})"
            if primeiro_match_conf is not None
            else (
                "⛔ COCO não cobre"
                if expected_cls is None
                else "❌ não detectou em nenhum threshold"
            )
        )
        print(f"  {crop.name:<48s} {cat:<28s} {status}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = OUT_DIR / f"yolo_validation_{ts}.json"
    out_md = OUT_DIR / f"yolo_validation_{ts}.md"

    out_json.write_text(
        json.dumps(
            {
                "timestamp": ts,
                "weights": WEIGHTS.name,
                "thresholds": CONF_THRESHOLDS,
                "expected_coco": {k: v[0] for k, v in EXPECTED_COCO.items()},
                "rows": rows,
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    md = ["# YOLO validation por crop", f"_run: {ts} · weights: {WEIGHTS.name}_", ""]
    md.append("| crop | categoria | esperado COCO | match? | threshold mín | conf real |")
    md.append("|---|---|---|---|---|---|")
    for r in rows:
        thr = r["primeiro_match_threshold"]
        match_emoji = (
            "✅" if thr is not None else "⛔" if r["expected_coco_class"] is None else "❌"
        )
        md.append(
            f"| {Path(r['crop']).name} | {r['categoria']} | "
            f"{r['expected_coco_class'] or '—'} | {match_emoji} | "
            f"{thr or '—'} | {r['primeiro_match_conf_real'] or '—'} |"
        )
    md.append("")
    md.append("## Legenda")
    md.append("- ✅ YOLO detectou a classe COCO esperada em algum threshold")
    md.append("- ⛔ COCO não tem classe equivalente (sinal/pintura BR) — fine-tune obrigatório")
    md.append("- ❌ COCO tem a classe mas YOLO não detectou em nenhum threshold testado")
    out_md.write_text("\n".join(md))

    print()
    print(f"json: {out_json}")
    print(f"md:   {out_md}")

    n_ok = sum(1 for r in rows if r["primeiro_match_threshold"] is not None)
    n_no_coco = sum(1 for r in rows if r["expected_coco_class"] is None)
    n_miss = len(rows) - n_ok - n_no_coco
    print(
        f"\nresumo: ✅ {n_ok}/{len(rows)} matched · ⛔ {n_no_coco} sem cobertura COCO · ❌ {n_miss} miss"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
