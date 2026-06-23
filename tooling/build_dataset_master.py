"""
build_dataset_master — consolida TODAS as fontes de treino do projeto Valbot
num índice unificado pra alimentar VLM (few-shot + ground truth + sinais CV).

Fontes consolidadas:
  1. sinalizacao/<categoria>/*.json — crops anotados manualmente (few-shot)
  2. storage/training/examples.jsonl — decisões humanas (approved/refuted)
  3. storage/training/annotations_unified/annotations_unified.json — bboxes
     manuais de partes internas (volante, câmbio, freio_mão, cinto, etc.)
  4. storage/analyses/<hash>/cv_detections.json — detecções clássicas
     (crosswalk, road_text, stop_sign) com bbox
  5. storage/analyses/<hash>/result.json — vereditos do orchestrator
  6. examples/laudo_vid1.json — exemplo de saída VLM
  7. configs/references/*.pdf — referências CONTRAN/MBST
  8. tooling/cvat_workflow/valbot_labels.json — schema de labels

Saída: storage/training/dataset_master/INDEX.json
       sinalizacao/DATASET_MASTER.md
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "sinalizacao"
TRAINING = ROOT / "storage" / "training"
ANALYSES = ROOT / "storage" / "analyses"
OUT_DIR = TRAINING / "dataset_master"


# Mapeamento de tipos de detecção CV → categoria sinalização
CV_TYPE_TO_CATEGORY = {
    "stop_sign": "vertical/pare-r1",
    "road_text": "horizontal/pare-chao",  # easyocr lendo "PARE" no chão
    "crosswalk": "horizontal/faixa-pedestre",
}

# Mapeamento de infracao_id → categoria sinalização ou parte interna
INFRACAO_TO_CATEGORIA = {
    "R1020-G-a": "vertical/pare-r1",  # sinal de regulamentação (PARE/preferência)
    "R1020-GR-f": "interno/cinto",  # cinto de segurança
}


def load_few_shot_crops() -> dict:
    """Lê todos os JSONs em sinalizacao/ e agrupa por categoria."""
    by_cat = defaultdict(list)
    for json_path in LIB.rglob("*.json"):
        if json_path.name == "scan_results.json":
            continue
        try:
            d = json.loads(json_path.read_text())
        except Exception:
            continue
        cat = d.get("category")
        if not cat:
            continue
        by_cat[cat].append(
            {
                "slug": d["slug"],
                "video": d.get("video"),
                "ts": d.get("timestamp_seconds"),
                "ts_label": d.get("timestamp_label"),
                "camera": d.get("camera"),
                "bbox_xyxy": d.get("bbox_xyxy"),
                "tipo_contran": d.get("tipo_contran"),
                "espelhada": d.get("espelhada", False),
                "raw_png": d.get("raw_png"),
                "annotated_png": d.get("annotated_png"),
                "crop_png": d.get("crop_png"),
            }
        )
    return dict(by_cat)


def load_human_decisions() -> dict:
    """Lê examples.jsonl e agrupa por categoria."""
    path = TRAINING / "examples.jsonl"
    by_cat = defaultdict(list)
    if not path.exists():
        return {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        iid = d.get("infracao_id")
        cat = INFRACAO_TO_CATEGORIA.get(iid, f"infracao/{iid}")
        by_cat[cat].append(
            {
                "hash": d.get("hash"),
                "infracao_id": iid,
                "frame_idx": d.get("frame_idx"),
                "ts": d.get("ts"),
                "decisao": d.get("decisao"),
                "vote": d.get("vote"),
                "evidencia": d.get("evidencia"),
                "saved_at": d.get("saved_at"),
            }
        )
    return dict(by_cat)


def load_internal_parts() -> dict:
    """Lê annotations_unified.json e agrupa bboxes por label."""
    path = TRAINING / "annotations_unified" / "annotations_unified.json"
    by_label = defaultdict(list)
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    for vid_key, vid_data in data.items():
        for frame in vid_data.get("frames", []):
            ts = frame.get("ts")
            png = frame.get("png_simbolico")
            for ann in frame.get("anotacoes", []):
                label = ann.get("label")
                box = ann.get("box")
                if label and box:
                    by_label[label].append(
                        {
                            "video": vid_key,
                            "ts": ts,
                            "png": f"storage/training/annotations_unified/{png}",
                            "bbox_xyxy": box,
                        }
                    )
    return dict(by_label)


def load_cv_detections() -> dict:
    """Agrega cv_detections.json de todas as análises por categoria."""
    by_cat = defaultdict(list)
    if not ANALYSES.exists():
        return {}
    for hash_dir in ANALYSES.iterdir():
        if not hash_dir.is_dir():
            continue
        cv_path = hash_dir / "cv_detections.json"
        if not cv_path.exists():
            continue
        try:
            d = json.loads(cv_path.read_text())
        except Exception:
            continue
        for det in d.get("detections", []):
            cat = CV_TYPE_TO_CATEGORY.get(det.get("type"))
            if not cat:
                continue
            by_cat[cat].append(
                {
                    "hash": d.get("hash"),
                    "frame_idx": det.get("frame_idx"),
                    "ts": det.get("ts"),
                    "camera": det.get("camera"),
                    "type": det.get("type"),
                    "bbox_xyxy": det.get("bbox"),
                    "confidence": det.get("confidence"),
                    "source": str(cv_path.relative_to(ROOT)),
                }
            )
    return dict(by_cat)


def load_orchestrator_verdicts() -> list:
    """Lista vereditos finais por análise."""
    out = []
    if not ANALYSES.exists():
        return out
    for hash_dir in ANALYSES.iterdir():
        result = hash_dir / "result.json"
        if not result.exists():
            continue
        try:
            d = json.loads(result.read_text())
        except Exception:
            continue
        out.append(
            {
                "hash": hash_dir.name,
                "video": d.get("video", {}).get("path"),
                "infracoes_avaliadas": [
                    {
                        "infracao_id": i.get("infracao_id"),
                        "veredito": i.get("veredito"),
                        "n_candidatos_confiavel": len(i.get("candidatos_confiavel", [])),
                        "n_candidatos_suspeito": len(i.get("candidatos_suspeito", [])),
                    }
                    for i in d.get("tier_a", {}).get("infracoes_avaliadas", [])
                ],
            }
        )
    return out


def load_vlm_examples() -> dict:
    """Carrega exemplos de saída VLM (laudo_vid1.json etc)."""
    out = {}
    examples_dir = ROOT / "examples"
    if examples_dir.exists():
        for f in examples_dir.glob("*.json"):
            try:
                d = json.loads(f.read_text())
                out[f.name] = {
                    "path": str(f.relative_to(ROOT)),
                    "n_entries": len(d) if isinstance(d, list) else len(d.get("prompts", [])),
                    "schema_sample": d[0]
                    if isinstance(d, list) and d
                    else (list(d.values())[0] if isinstance(d, dict) and d else None),
                }
            except Exception:
                pass
    return out


def load_references() -> list:
    """Lista PDFs de referência CONTRAN/MBST."""
    refs = []
    for f in (ROOT / "configs" / "references").glob("*"):
        if f.suffix.lower() in (".pdf", ".md", ".txt"):
            refs.append(
                {
                    "path": str(f.relative_to(ROOT)),
                    "size_bytes": f.stat().st_size,
                }
            )
    return refs


def load_label_schema() -> dict | None:
    """Schema de labels do CVAT workflow."""
    p = ROOT / "tooling" / "cvat_workflow" / "valbot_labels.json"
    if p.exists():
        return {
            "path": str(p.relative_to(ROOT)),
            "content": json.loads(p.read_text()),
        }
    return None


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    few_shot = load_few_shot_crops()
    decisions = load_human_decisions()
    parts = load_internal_parts()
    cv_dets = load_cv_detections()
    verdicts = load_orchestrator_verdicts()
    vlm_examples = load_vlm_examples()
    refs = load_references()
    label_schema = load_label_schema()

    # Merge por categoria (sinalização)
    all_cats = set(few_shot.keys()) | set(decisions.keys()) | set(cv_dets.keys())
    categorias = {}
    for cat in sorted(all_cats):
        categorias[cat] = {
            "few_shot_crops": few_shot.get(cat, []),
            "decisoes_humanas": decisions.get(cat, []),
            "deteccoes_cv_classicas": cv_dets.get(cat, []),
            "n_few_shot": len(few_shot.get(cat, [])),
            "n_decisoes": len(decisions.get(cat, [])),
            "n_deteccoes_cv": len(cv_dets.get(cat, [])),
        }

    n_total = sum(
        c["n_few_shot"] + c["n_decisoes"] + c["n_deteccoes_cv"] for c in categorias.values()
    )

    index = {
        "version": "1.0",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project": "LaudoAI / Valbot",
        "n_categorias_sinalizacao": len(categorias),
        "n_amostras_total": n_total,
        "categorias_sinalizacao": categorias,
        "partes_internas_do_carro": {
            label: {"n_amostras": len(boxes), "amostras": boxes}
            for label, boxes in sorted(parts.items())
        },
        "vereditos_orchestrator": {
            "n_analises": len(verdicts),
            "lista": verdicts,
        },
        "exemplos_saida_vlm": vlm_examples,
        "documentos_referencia": refs,
        "schema_labels_cvat": label_schema,
    }

    out_path = OUT_DIR / "INDEX.json"
    out_path.write_text(json.dumps(index, ensure_ascii=False, indent=2))

    print(f"  categorias sinalização: {len(categorias)}")
    for cat, v in categorias.items():
        print(
            f"    {cat}:  few_shot={v['n_few_shot']:2d}  decisoes={v['n_decisoes']:3d}  cv={v['n_deteccoes_cv']:3d}"
        )
    print(f"  partes internas: {len(parts)} labels, {sum(len(v) for v in parts.values())} bboxes")
    print(f"  vereditos: {len(verdicts)} análises")
    print(f"  exemplos VLM: {len(vlm_examples)}")
    print(f"  referências: {len(refs)} PDFs")
    print(f"\n  INDEX salvo em: {out_path.relative_to(ROOT)}")
    print(f"  total de amostras indexadas: {n_total}")


if __name__ == "__main__":
    main()
