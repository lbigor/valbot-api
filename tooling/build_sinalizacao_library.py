"""
build_sinalizacao_library — gera biblioteca de modelos visuais de sinalização
em sinalizacao/ pra alimentar VLM como referência few-shot e servir de
dicionário visual humano.

Pipeline em 2 fases:
  fase 1 (extract): lê tabela GROUND_TRUTH abaixo, extrai frame em ts exato,
                    cropa apenas a câmera onde a sinalização aparece, salva
                    PNG _raw (sem bbox) + JSON parcial.
  fase 2 (annotate): aplica bbox+label num _raw já existente. bbox vem do
                     revisor (Claude no chat lendo o PNG via Read multimodal,
                     ou usuário humano).

Uso:
    .venv/bin/python -m tooling.build_sinalizacao_library --extract
    .venv/bin/python -m tooling.build_sinalizacao_library --annotate \
        --slug 01_vid4_t01-19_frontal --category vertical/pare-r1 \
        --bbox 380,40,520,180 --label "R-1 PARE"
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import cv2

from src.ingestion.grid_slicer import GridSlicer

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "sinalizacao"
VIDEOS = ROOT / "storage" / "videos"


@dataclass
class FrameSpec:
    slug: str
    video: str
    ts_label: str
    camera: str
    category: str
    tipo_contran: str
    descricao: str
    espelhada: bool = False

    @property
    def ts_seconds(self) -> float:
        mm, ss = self.ts_label.split(":")
        return int(mm) * 60 + int(ss)

    @property
    def out_dir(self) -> Path:
        return LIBRARY / self.category

    @property
    def png_path(self) -> Path:
        return self.out_dir / f"{self.slug}.png"

    @property
    def raw_path(self) -> Path:
        return self.out_dir / f"{self.slug}_raw.png"

    @property
    def json_path(self) -> Path:
        return self.out_dir / f"{self.slug}.json"

    @property
    def crop_path(self) -> Path:
        return self.out_dir / f"{self.slug}_crop.png"


GROUND_TRUTH: list[FrameSpec] = [
    FrameSpec(
        "01_vid1_t00-54_frontal",
        "1.mp4",
        "00:54",
        "frontal",
        "horizontal/faixa-pedestre",
        "LFO - Faixa de travessia de pedestres",
        "faixa zebrada branca transversal à pista, vista aproximando",
    ),
    FrameSpec(
        "02_vid1_t01-06_lateral",
        "1.mp4",
        "01:06",
        "lateral_direita",
        "horizontal/faixa-pedestre",
        "LFO - Faixa de travessia de pedestres",
        "faixa zebrada vista de cima/lateral confirmando que o veículo passou",
    ),
    FrameSpec(
        "03_vid1_t01-06_traseira",
        "1.mp4",
        "01:06",
        "traseira_esq",
        "horizontal/faixa-pedestre",
        "LFO - Faixa de travessia de pedestres",
        "faixa zebrada vista pela traseira após o veículo cruzar (espelhada)",
        espelhada=True,
    ),
    FrameSpec(
        "04_vid2_t01-41_frontal",
        "2.mp4",
        "01:41",
        "frontal",
        "horizontal/seta-esquerda",
        "LMS - Seta de regulamentação de movimento (esquerda)",
        "seta branca apontando para esquerda no centro da faixa",
    ),
    FrameSpec(
        "05_vid2_t01-45_traseira",
        "2.mp4",
        "01:45",
        "traseira_esq",
        "horizontal/seta-esquerda",
        "LMS - Seta de regulamentação de movimento (esquerda) — espelhada",
        "vista pela traseira: seta aparece invertida horizontalmente",
        espelhada=True,
    ),
    FrameSpec(
        "06_vid2_t02-03_frontal",
        "2.mp4",
        "02:03",
        "frontal",
        "horizontal/seta-esquerda",
        "LMS - Seta de regulamentação de movimento (esquerda)",
        "seta para esquerda visível à frente",
    ),
    FrameSpec(
        "07_vid2_t02-05_frontal",
        "2.mp4",
        "02:05",
        "frontal",
        "horizontal/pare-chao",
        "LMS - Inscrição PARE no pavimento",
        "palavra PARE em letras brancas grandes maiúsculas no asfalto",
    ),
    FrameSpec(
        "08_vid2_t02-08_traseira",
        "2.mp4",
        "02:08",
        "traseira_esq",
        "horizontal/seta-esquerda",
        "LMS - Seta para esquerda — espelhada",
        "seta vista pela traseira após cruzar",
        espelhada=True,
    ),
    FrameSpec(
        "09_vid2_t02-45_frontal",
        "2.mp4",
        "02:45",
        "frontal",
        "horizontal/seta-reta",
        "LMS - Seta de regulamentação (frente/continuar reto)",
        "seta branca apontando para frente",
    ),
    FrameSpec(
        "10_vid2_t02-48_frontal",
        "2.mp4",
        "02:48",
        "frontal",
        "horizontal/pare-chao",
        "LMS - Inscrição PARE no pavimento",
        "palavra PARE bem visível, letras grandes, fase ótima de leitura",
    ),
    FrameSpec(
        "11_vid2_t03-05_traseira",
        "2.mp4",
        "03:05",
        "traseira_esq",
        "horizontal/seta-reta",
        "LMS - Seta de continuar reto — vista pela traseira",
        "seta para frente vista pela câmera traseira (após cruzar)",
        espelhada=True,
    ),
    FrameSpec(
        "12_vid4_t01-19_frontal",
        "4.mp4",
        "01:19",
        "frontal",
        "vertical/pare-r1",
        "R-1 - Parada obrigatória",
        "placa octogonal vermelha com palavra PARE branca, à direita do motorista",
    ),
    FrameSpec(
        "13_vid4_t04-29_frontal",
        "4.mp4",
        "04:29",
        "frontal",
        "vertical/pare-r1",
        "R-1 - Parada obrigatória",
        "placa octogonal vermelha PARE, segunda ocorrência no circuito",
    ),
]


def extract_one(spec: FrameSpec, *, force: bool = False) -> dict:
    """Extrai frame em ts exato, cropa câmera, salva _raw.png + JSON parcial."""
    video_path = VIDEOS / spec.video
    if not video_path.exists():
        return {"slug": spec.slug, "status": "video_missing", "path": str(video_path)}

    spec.out_dir.mkdir(parents=True, exist_ok=True)

    if spec.raw_path.exists() and not force:
        return {"slug": spec.slug, "status": "skipped_exists", "raw": str(spec.raw_path)}

    slicer = GridSlicer(video_path, sample_fps=0.0)
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(spec.ts_seconds * fps))
    ok, grid_frame = cap.read()
    cap.release()

    if not ok or grid_frame is None:
        return {"slug": spec.slug, "status": "read_failed", "ts": spec.ts_seconds}

    camera_img = slicer.extract_camera(grid_frame, spec.camera)
    cv2.imwrite(str(spec.raw_path), camera_img)

    h, w = camera_img.shape[:2]
    metadata = {
        "slug": spec.slug,
        "video": f"storage/videos/{spec.video}",
        "timestamp_seconds": spec.ts_seconds,
        "timestamp_label": spec.ts_label,
        "camera": spec.camera,
        "camera_resolution": [w, h],
        "layout_grid": slicer.layout_name,
        "category": spec.category,
        "tipo_contran": spec.tipo_contran,
        "descricao": spec.descricao,
        "espelhada": spec.espelhada,
        "bbox_xyxy": None,
        "bbox_source": None,
        "label_text": None,
        "annotated_png": None,
        "raw_png": str(spec.raw_path.relative_to(ROOT)),
    }
    spec.json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))

    return {
        "slug": spec.slug,
        "status": "extracted",
        "raw": str(spec.raw_path.relative_to(ROOT)),
        "resolution": [w, h],
    }


def annotate_one(
    slug: str,
    category: str,
    bbox: tuple[int, int, int, int],
    label: str,
    *,
    source: str = "claude-chat-vlm",
) -> dict:
    """Aplica bbox+label num _raw existente, salva PNG anotado e atualiza JSON."""
    out_dir = LIBRARY / category
    raw_path = out_dir / f"{slug}_raw.png"
    out_path = out_dir / f"{slug}.png"
    json_path = out_dir / f"{slug}.json"

    if not raw_path.exists():
        return {"slug": slug, "status": "raw_missing", "expected": str(raw_path)}

    img = cv2.imread(str(raw_path))
    if img is None:
        return {"slug": slug, "status": "imread_failed"}

    h, w = img.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    annotated = img.copy()
    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 3)

    # label com fundo branco em cima da bbox
    font = cv2.FONT_HERSHEY_DUPLEX
    scale, thick = 0.7, 2
    (tw, th), _ = cv2.getTextSize(label, font, scale, thick)
    pad = 6
    bg_y2 = max(y1 - pad, th + pad)
    bg_y1 = bg_y2 - th - 2 * pad
    bg_x1 = x1
    bg_x2 = x1 + tw + 2 * pad
    cv2.rectangle(annotated, (bg_x1, bg_y1), (bg_x2, bg_y2), (255, 255, 255), -1)
    cv2.rectangle(annotated, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), 1)
    cv2.putText(
        annotated, label, (bg_x1 + pad, bg_y2 - pad), font, scale, (0, 0, 0), thick, cv2.LINE_AA
    )

    cv2.imwrite(str(out_path), annotated)

    # atualiza JSON
    if json_path.exists():
        meta = json.loads(json_path.read_text())
    else:
        meta = {"slug": slug, "category": category}
    meta["bbox_xyxy"] = [x1, y1, x2, y2]
    meta["bbox_source"] = source
    meta["label_text"] = label
    meta["annotated_png"] = str(out_path.relative_to(ROOT))
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    return {"slug": slug, "status": "annotated", "out": str(out_path.relative_to(ROOT))}


def crop_one(slug: str, category: str, *, padding: int = 8, upscale: int = 4) -> dict:
    """Lê bbox do JSON, recorta com padding, amplia 4x, salva _crop.png.
    O crop é o MODELO few-shot que vai pra LLM (apenas a sinalização)."""
    out_dir = LIBRARY / category
    raw_path = out_dir / f"{slug}_raw.png"
    json_path = out_dir / f"{slug}.json"
    crop_path = out_dir / f"{slug}_crop.png"

    if not raw_path.exists():
        return {"slug": slug, "status": "raw_missing"}
    if not json_path.exists():
        return {"slug": slug, "status": "json_missing"}

    meta = json.loads(json_path.read_text())
    bbox = meta.get("bbox_xyxy")
    if not bbox:
        return {"slug": slug, "status": "no_bbox"}

    img = cv2.imread(str(raw_path))
    if img is None:
        return {"slug": slug, "status": "imread_failed"}
    H, W = img.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(W, x2 + padding)
    y2 = min(H, y2 + padding)
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return {"slug": slug, "status": "empty_crop"}

    if upscale > 1:
        crop = cv2.resize(crop, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(str(crop_path), crop)

    meta["crop_png"] = str(crop_path.relative_to(ROOT))
    meta["crop_padding"] = padding
    meta["crop_upscale"] = upscale
    meta["crop_resolution"] = [crop.shape[1], crop.shape[0]]
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    return {
        "slug": slug,
        "status": "cropped",
        "out": str(crop_path.relative_to(ROOT)),
        "resolution": [crop.shape[1], crop.shape[0]],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--extract",
        action="store_true",
        help="Fase 1: extrai todos os frames da tabela GROUND_TRUTH",
    )
    ap.add_argument("--force", action="store_true", help="Sobrescreve _raw.png existentes")
    ap.add_argument(
        "--annotate", action="store_true", help="Fase 2: aplica bbox+label num slug específico"
    )
    ap.add_argument("--slug")
    ap.add_argument("--category")
    ap.add_argument("--bbox", help="x1,y1,x2,y2")
    ap.add_argument("--label")
    ap.add_argument(
        "--crop-all",
        action="store_true",
        help="Fase 3: recorta _crop.png pra todos os slugs com bbox no JSON",
    )
    ap.add_argument(
        "--padding", type=int, default=8, help="Padding em pixels ao redor da bbox no crop"
    )
    ap.add_argument("--upscale", type=int, default=4, help="Fator de ampliação do crop")
    ap.add_argument(
        "--list",
        action="store_true",
        help="Lista frames pendentes de anotação (raw existe, png não)",
    )
    args = ap.parse_args()

    if args.list:
        for spec in GROUND_TRUTH:
            done = spec.png_path.exists()
            raw = spec.raw_path.exists()
            status = "DONE" if done else ("RAW" if raw else "MISS")
            print(f"  [{status}] {spec.slug}  ({spec.category})")
        return

    if args.extract:
        results = [extract_one(s, force=args.force) for s in GROUND_TRUTH]
        for r in results:
            print(f"  {r['status']:18} {r['slug']}", end="")
            if "resolution" in r:
                print(f"  {r['resolution'][0]}x{r['resolution'][1]}")
            else:
                print()
        return

    if args.crop_all:
        for spec in GROUND_TRUTH:
            r = crop_one(spec.slug, spec.category, padding=args.padding, upscale=args.upscale)
            print(f"  {r['status']:18} {spec.slug}", end="")
            if "resolution" in r:
                print(f"  {r['resolution'][0]}x{r['resolution'][1]}")
            else:
                print()
        return

    if args.annotate:
        if not (args.slug and args.category and args.bbox and args.label):
            ap.error("--annotate requer --slug --category --bbox --label")
        bbox = tuple(int(v) for v in args.bbox.split(","))
        if len(bbox) != 4:
            ap.error("--bbox formato x1,y1,x2,y2")
        r = annotate_one(args.slug, args.category, bbox, args.label)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    ap.print_help()


if __name__ == "__main__":
    main()
