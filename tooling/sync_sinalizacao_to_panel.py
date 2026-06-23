"""
Reprocessa todas as anotações em `sinalizacao/<categoria>/<slug>.json` e
persiste como detecção do painel "Detecções da IA" — mas só se o timestamp
bater com o vídeo (template matching do crop salvo contra o frame real).

Regra crítica (definida pelo usuário): nada sobe pro painel sem timestamp
validado. Anotação que falhar é registrada com motivo e fica fora.

Pipeline:
  1. Mapeia `vid1..vid5 ↔ hash do storage/analyses` via filename do result.json
  2. Pra cada entry da biblioteca:
       - extrai frame no `timestamp_seconds` (cv2 VideoCapture)
       - olha o quadrante da câmera (frontal=TL, lateral=TR, interna=BL, traseira=BR)
       - cv2.matchTemplate (TM_CCOEFF_NORMED) entre crop_png e a região do frame
       - score >= MATCH_THRESHOLD → valida; senão rejeita
  3. Escreve `storage/analyses/<hash>/sinalizacao_panel.json` com as entradas validadas
  4. O bridge `_laudo_from_result_json` (Fonte 4) consome esse JSON e emite no painel

Uso:
    python tooling/sync_sinalizacao_to_panel.py
    python tooling/sync_sinalizacao_to_panel.py --threshold 0.35  # mais permissivo
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
SINALIZACAO_DIR = PROJECT_ROOT / "sinalizacao"
ANALYSES_DIR = PROJECT_ROOT / "storage" / "analyses"
VIDEOS_DIR = PROJECT_ROOT / "storage" / "videos"

# Layout de quadrantes do mosaic 1280×720 (camera_resolution 640×360 cada).
# Lido nos JSONs originais (TL=frontal, TR=lateral_direita, BL=interna, BR=traseira_esq).
QUADRANTE = {
    "frontal": ("TL", (0, 0, 640, 360)),
    "lateral_direita": ("TR", (640, 0, 1280, 360)),
    "lateral": ("TR", (640, 0, 1280, 360)),
    "interna": ("BL", (0, 360, 640, 720)),
    "traseira_esq": ("BR", (640, 360, 1280, 720)),
    "traseira": ("BR", (640, 360, 1280, 720)),
}


def _hash_to_video_filename() -> dict[str, str]:
    """Mapa hash → filename do vídeo, lendo result.json de cada análise."""
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


def _video_slug_to_hash(slug: str, hash_to_fn: dict[str, str]) -> str | None:
    """`vid4` → hash cujo filename é `4.mp4`."""
    if not slug.startswith("vid"):
        return None
    n = slug[3:]
    target = f"{n}.mp4"
    for h, fn in hash_to_fn.items():
        if fn == target:
            return h
    return None


def _extract_frame(video_path: Path, ts: float) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def _validate_entry(entry_json: dict, threshold: float) -> dict:
    slug = entry_json.get("slug", "")
    cam = entry_json.get("camera", "frontal")
    quad_letter, (qx0, qy0, qx1, qy1) = QUADRANTE.get(cam, QUADRANTE["frontal"])

    video_rel = entry_json.get("video", "")
    video_path = PROJECT_ROOT / video_rel
    if not video_path.exists():
        return {"slug": slug, "valid": False, "reason": f"vídeo não encontrado: {video_rel}"}

    ts = float(entry_json.get("timestamp_seconds", 0))
    frame = _extract_frame(video_path, ts)
    if frame is None:
        return {"slug": slug, "valid": False, "reason": f"falha ao ler frame em ts={ts}"}

    # Recorta o quadrante da câmera (no mosaic 1280×720)
    cam_region = frame[qy0:qy1, qx0:qx1]

    # Crop salvo (já com padding 8px e upscale 4x — descer pra resolução crua)
    crop_path = PROJECT_ROOT / entry_json.get("crop_png", "")
    if not crop_path.exists():
        return {
            "slug": slug,
            "valid": False,
            "reason": f"crop_png não encontrado: {entry_json.get('crop_png')}",
        }
    crop_saved = cv2.imread(str(crop_path))
    upscale = entry_json.get("crop_upscale", 1) or 1
    if upscale > 1:
        h, w = crop_saved.shape[:2]
        crop_saved = cv2.resize(
            crop_saved, (w // upscale, h // upscale), interpolation=cv2.INTER_AREA
        )

    # Sanity: template não pode ser maior que a imagem
    th, tw = crop_saved.shape[:2]
    rh, rw = cam_region.shape[:2]
    if th >= rh or tw >= rw or th < 4 or tw < 4:
        return {
            "slug": slug,
            "valid": False,
            "reason": f"template ({tw}×{th}) incompatível com região ({rw}×{rh})",
        }

    # Template matching (NCC) — robusto a brilho/contraste leves
    res = cv2.matchTemplate(cam_region, crop_saved, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    score = float(max_val)

    # Esperamos que o match aconteça PERTO da bbox anotada (640×360 coords).
    bbox = entry_json.get("bbox_xyxy", [0, 0, 0, 0])
    expected_x = bbox[0]
    expected_y = bbox[1]
    found_x, found_y = max_loc
    delta = ((found_x - expected_x) ** 2 + (found_y - expected_y) ** 2) ** 0.5

    valid = score >= threshold and delta <= 60  # 60 px de folga (~10% da câmera 640px)
    return {
        "slug": slug,
        "valid": valid,
        "match_score": round(score, 3),
        "match_loc_xy": [int(found_x), int(found_y)],
        "expected_xy": [expected_x, expected_y],
        "delta_px": round(delta, 1),
        "category": entry_json.get("category", ""),
        "tipo_contran": entry_json.get("tipo_contran", ""),
        "label_text": entry_json.get("label_text", ""),
        "ts": ts,
        "camera": cam,
        "bbox_xyxy_camera": bbox,
        "reason": (
            "ok"
            if valid
            else f"score {score:.2f} < {threshold}"
            if score < threshold
            else f"deslocamento {delta:.0f}px > 60"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--threshold", type=float, default=0.4, help="match_score mínimo do template matching"
    )
    args = ap.parse_args()

    h2f = _hash_to_video_filename()
    print(f"hashes mapeados: {len(h2f)}")

    library = sorted(SINALIZACAO_DIR.rglob("*.json"))
    library = [p for p in library if not p.name.startswith("scan_results")]
    print(f"anotações na biblioteca: {len(library)}")

    by_hash: dict[str, list[dict]] = {}
    rejeitados: list[dict] = []
    for js in library:
        try:
            entry = json.loads(js.read_text())
        except Exception:
            continue
        if "slug" not in entry or "video" not in entry:
            continue
        # Determina o hash via filename (storage/videos/4.mp4 → 4.mp4 → hash)
        vid_fn = Path(entry["video"]).name
        hash_ = next((h for h, fn in h2f.items() if fn == vid_fn), None)
        if hash_ is None:
            rejeitados.append(
                {
                    "slug": entry.get("slug"),
                    "valid": False,
                    "reason": f"hash não encontrado pra {vid_fn}",
                }
            )
            continue
        result = _validate_entry(entry, args.threshold)
        result["hash"] = hash_
        if result["valid"]:
            by_hash.setdefault(hash_, []).append(result)
        else:
            rejeitados.append(result)

    # Persiste por hash
    for hash_, entries in by_hash.items():
        out = ANALYSES_DIR / hash_ / "sinalizacao_panel.json"
        out.write_text(
            json.dumps(
                {
                    "synced_at": datetime.now().isoformat(timespec="seconds"),
                    "threshold": args.threshold,
                    "entries": entries,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        print(f"  ✅ {hash_[:12]}: {len(entries)} validadas → {out.relative_to(PROJECT_ROOT)}")

    # Hashes que não receberam nada também precisam de arquivo vazio (limpa stale).
    for h in h2f.keys():
        out = ANALYSES_DIR / h / "sinalizacao_panel.json"
        if h not in by_hash and out.exists():
            out.unlink()

    print(f"\n{'=' * 60}")
    print(
        f"resumo: {sum(len(v) for v in by_hash.values())}/{len(library)} validadas · {len(rejeitados)} rejeitadas"
    )
    if rejeitados:
        print("\nrejeitadas:")
        for r in rejeitados:
            print(f"  ❌ {r.get('slug', '?'):<48s} {r.get('reason', '?')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
