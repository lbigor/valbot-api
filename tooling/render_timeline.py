"""
render_timeline — gera PNG por vídeo mostrando todos os eventos detectados
em barra temporal + thumbnails do frame da câmera no instante do evento.

Saída: storage/training/dataset_master/timelines/<hash>_timeline.png
       sinalizacao/timelines/<nome_video>_timeline.png  (link simbólico amigável)

Uso:
    .venv/bin/python -m tooling.render_timeline             # todos os vídeos
    .venv/bin/python -m tooling.render_timeline --hash X    # só um
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from src.ingestion.grid_slicer import GridSlicer

ROOT = Path(__file__).resolve().parents[1]
ANALYSES = ROOT / "storage" / "analyses"
OUT_DIR = ROOT / "storage" / "training" / "dataset_master" / "timelines"
LINK_DIR = ROOT / "sinalizacao" / "timelines"

# cores BGR por categoria
CAT_COLOR = {
    "vertical/pare-r1": (60, 60, 220),  # vermelho R-1
    "horizontal/pare-chao": (220, 220, 220),  # branco PARE chão
    "horizontal/faixa-pedestre": (180, 180, 180),  # cinza zebra
    "horizontal/seta-esquerda": (80, 220, 80),  # verde seta esq
    "horizontal/seta-reta": (80, 220, 80),  # verde seta reta
}
CAT_LABEL = {
    "vertical/pare-r1": "R-1 PARE",
    "horizontal/pare-chao": "PARE chao",
    "horizontal/faixa-pedestre": "Faixa Ped",
    "horizontal/seta-esquerda": "Seta Esq",
    "horizontal/seta-reta": "Seta Reta",
}


def render_one(scan_path: Path, video_path: Path, out_path: Path) -> Path:
    scan = json.loads(scan_path.read_text())
    duration = scan["duration_s"]
    eventos = scan.get("eventos", {})

    # canvas: 1920×900
    W, H = 1920, 900
    canvas = np.full((H, W, 3), 30, dtype=np.uint8)

    # cabeçalho
    title = Path(video_path).name
    cv2.putText(
        canvas, title, (20, 35), cv2.FONT_HERSHEY_DUPLEX, 0.75, (220, 220, 220), 1, cv2.LINE_AA
    )
    cv2.putText(
        canvas,
        f"duracao: {duration:.0f}s   eventos: "
        + "  ".join(f"{CAT_LABEL.get(c, c)}={len(v)}" for c, v in eventos.items()),
        (20, 65),
        cv2.FONT_HERSHEY_PLAIN,
        1.2,
        (180, 180, 180),
        1,
        cv2.LINE_AA,
    )

    # timeline: x=80..W-80, y=120..200 (5 trilhas, uma por categoria)
    tl_x0, tl_x1 = 80, W - 80
    tl_y0 = 110
    track_h = 30
    cats_used = list(eventos.keys())

    def ts_to_x(ts):
        return int(tl_x0 + (ts / max(duration, 1)) * (tl_x1 - tl_x0))

    # eixo de tempo
    axis_y = tl_y0 + len(cats_used) * track_h + 20
    cv2.line(canvas, (tl_x0, axis_y), (tl_x1, axis_y), (180, 180, 180), 1)
    for tick_s in range(0, int(duration) + 1, 30):
        x = ts_to_x(tick_s)
        cv2.line(canvas, (x, axis_y - 4), (x, axis_y + 4), (180, 180, 180), 1)
        if tick_s % 60 == 0:
            cv2.putText(
                canvas,
                f"{tick_s // 60:02d}:{tick_s % 60:02d}",
                (x - 18, axis_y + 22),
                cv2.FONT_HERSHEY_PLAIN,
                0.9,
                (180, 180, 180),
                1,
                cv2.LINE_AA,
            )

    # trilha por categoria
    for i, cat in enumerate(cats_used):
        y = tl_y0 + i * track_h
        color = CAT_COLOR.get(cat, (200, 200, 200))
        cv2.rectangle(canvas, (tl_x0, y + 4), (tl_x1, y + track_h - 4), (50, 50, 50), -1)
        cv2.putText(
            canvas,
            CAT_LABEL.get(cat, cat),
            (4, y + 22),
            cv2.FONT_HERSHEY_PLAIN,
            1.0,
            color,
            1,
            cv2.LINE_AA,
        )
        for ev in eventos[cat]:
            x_a = ts_to_x(ev["ts_start"])
            x_b = max(x_a + 2, ts_to_x(ev["ts_end"]))
            alpha = 0.4 + 0.6 * min(1.0, ev["max_confidence"])
            ev_color = tuple(int(c * alpha) for c in color)
            cv2.rectangle(canvas, (x_a, y + 6), (x_b, y + track_h - 6), ev_color, -1)

    # thumbnails: até 6 eventos top-confidence diferentes (1 por categoria
    # se possível, depois preenche com mais alta conf)
    thumbs_y = axis_y + 50
    thumb_w, thumb_h = 280, 158
    pad = 20
    cols = (W - 2 * pad) // (thumb_w + pad)
    selected = []
    seen_cats = set()
    # 1 melhor por categoria
    for cat in cats_used:
        if not eventos[cat]:
            continue
        best = max(eventos[cat], key=lambda e: e["max_confidence"])
        selected.append((cat, best))
        seen_cats.add(cat)
        if len(selected) >= cols:
            break
    # preenche restante com top-confidence cross-categoria
    if len(selected) < cols:
        all_evs = [(c, e) for c in cats_used for e in eventos[c]]
        all_evs.sort(key=lambda x: -x[1]["max_confidence"])
        for c, e in all_evs:
            if (c, e) in selected:
                continue
            selected.append((c, e))
            if len(selected) >= cols:
                break

    # extrai thumbnails do vídeo
    if selected and video_path.exists():
        slicer = GridSlicer(video_path, sample_fps=0.0)
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        for i, (cat, ev) in enumerate(selected[:cols]):
            ts = ev["ts_start"]
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(ts * fps))
            ok, frame = cap.read()
            if not ok:
                continue
            cam_img = slicer.extract_camera(frame, ev["camera"])
            # desenha bbox se disponível
            if ev.get("bbox_first"):
                x1, y1, x2, y2 = [int(v) for v in ev["bbox_first"]]
                cv2.rectangle(cam_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
            thumb = cv2.resize(cam_img, (thumb_w, thumb_h))
            tx = pad + i * (thumb_w + pad)
            ty = thumbs_y
            canvas[ty : ty + thumb_h, tx : tx + thumb_w] = thumb
            # legenda do thumbnail
            ts_s = int(ts)
            label = f"{ts_s // 60:02d}:{ts_s % 60:02d}  {CAT_LABEL.get(cat, cat)}  c={ev['max_confidence']:.2f}"
            cv2.putText(
                canvas,
                label,
                (tx, ty + thumb_h + 18),
                cv2.FONT_HERSHEY_PLAIN,
                1.1,
                CAT_COLOR.get(cat, (200, 200, 200)),
                1,
                cv2.LINE_AA,
            )
            # marcador no eixo apontando pro thumb
            x_axis = ts_to_x(ts)
            cv2.line(
                canvas,
                (x_axis, axis_y + 25),
                (tx + thumb_w // 2, ty - 5),
                CAT_COLOR.get(cat, (200, 200, 200)),
                1,
                cv2.LINE_AA,
            )
        cap.release()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), canvas)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hash", help="apenas um hash")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LINK_DIR.mkdir(parents=True, exist_ok=True)

    n = 0
    hashes = [args.hash] if args.hash else [d.name for d in ANALYSES.iterdir() if d.is_dir()]
    for h in hashes:
        scan_path = ANALYSES / h / "sinalizacao_scan.json"
        result_path = ANALYSES / h / "result.json"
        if not scan_path.exists():
            continue
        if not result_path.exists():
            continue
        result = json.loads(result_path.read_text())
        video_path = Path(result.get("video", {}).get("path", ""))
        if not video_path.exists():
            print(f"  vídeo não encontrado: {video_path}")
            continue

        out_path = OUT_DIR / f"{h[:8]}_{video_path.stem.replace(' ', '_')}_timeline.png"
        render_one(scan_path, video_path, out_path)

        # link simbólico amigável em sinalizacao/timelines/
        link = LINK_DIR / out_path.name
        if link.exists() or link.is_symlink():
            link.unlink()
        try:
            link.symlink_to(out_path.resolve())
        except Exception:
            # fallback: copiar
            import shutil

            shutil.copy2(out_path, link)

        print(f"  ok  {out_path.relative_to(ROOT)}")
        n += 1
    print(f"\n{n} timelines geradas em {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
