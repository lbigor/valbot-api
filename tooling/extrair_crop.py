"""
extrair_crop — recorta a região de um evento `approved` do avaliador IA
simbólico no quadrante FRONTAL correto (varia por layout do gravador) e
salva como JPEG ampliado pra revisor humano (Claude no chat) abrir via
Read multimodal.

Uso:
    .venv/bin/python -m tooling.extrair_crop --hash <h>            # 1 hash
    .venv/bin/python -m tooling.extrair_crop --pendentes           # todos approveds não revisados
    .venv/bin/python -m tooling.extrair_crop --hash <h> --evento_id <eid>  # 1 evento

Saída: /tmp/valbot_review/<hash8>_<evento_id>.png
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2

from src.ingestion.grid_slicer import GridSlicer

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "storage"
ANALYSES = STORAGE / "analyses"
EXAMPLES = STORAGE / "training" / "examples.jsonl"
OUTPUT_DIR = Path("/tmp/valbot_review")


def listar_approveds_pendentes() -> list[dict]:
    """
    Lê examples.jsonl e devolve approveds R1020-G-a que ainda NÃO foram
    revisados manualmente. "Revisado" = existe voto manual posterior
    (refuted/approved com 'manual:' no evidencia OU saved_at posterior).
    """
    if not EXAMPLES.exists():
        return []
    votos = [json.loads(l) for l in EXAMPLES.read_text().splitlines() if l.strip()]
    approveds = [
        v
        for v in votos
        if v.get("infracao_id") == "R1020-G-a"
        and v.get("decisao") == "approved"
        and v.get("vote") == "S"
    ]
    # Para cada approved, ver se há voto manual posterior cobrindo o mesmo
    # ts (±2s) no mesmo hash. Se sim, foi revisado — pular.
    pendentes = []
    for a in approveds:
        h = a["hash"]
        ts = float(a.get("ts") or 0)
        saved_at = a.get("saved_at", "")
        review_posterior = any(
            v.get("hash") == h
            and v.get("infracao_id") == "R1020-G-a"
            and abs(float(v.get("ts") or 0) - ts) <= 2.0
            and (v.get("saved_at") or "") > saved_at
            and "manual:" in (v.get("evidencia") or "").lower()
            for v in votos
        )
        if not review_posterior:
            pendentes.append(a)
    return pendentes


def _evento_do_avaliador(hash_: str, evento_id: str) -> dict | None:
    """Reconstrói o evento (com bbox agregada) a partir do result.json."""
    from tooling.avaliador_simbolico import agrupar_em_eventos, coletar_candidatos

    cands = coletar_candidatos(hash_)
    evs = agrupar_em_eventos(cands, hash_)
    for ev in evs:
        if ev.evento_id == evento_id:
            return {
                "evento_id": ev.evento_id,
                "ts_inicio": ev.ts_inicio,
                "ts_fim": ev.ts_fim,
                "n_frames": ev.n_frames,
                "fontes": ev.fontes,
                "bbox_resumo": ev.bbox_resumo,
                "narrativa": ev.narrativa,
                "candidatos": ev.candidatos,
            }
    return None


def _video_path(hash_: str) -> Path | None:
    rp = ANALYSES / hash_ / "result.json"
    if not rp.exists():
        return None
    return Path(json.loads(rp.read_text()).get("video", {}).get("path", ""))


def extrair_crop(
    hash_: str,
    evento_id: str | None = None,
    ts: float | None = None,
    bbox_local: tuple[int, int, int, int] | None = None,
    upscale: int = 2,
) -> Path | None:
    """Salva 2 imagens: (a) frame frontal inteiro com bbox marcada;
       (b) crop da bbox ampliado. Diretório de saída: OUTPUT_DIR.

    Modos de uso:
      - extrair_crop(h, evento_id=...)   → reconstrói tudo do result.json
      - extrair_crop(h, ts=..., bbox_local=...)  → modo direto (avaliador)
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    vp = _video_path(hash_)
    if vp is None or not vp.exists():
        print(f"[extrair_crop] vídeo não encontrado para hash {hash_[:12]}")
        return None

    # resolver evento (bbox + ts) se evento_id foi fornecido
    if evento_id is not None:
        ev = _evento_do_avaliador(hash_, evento_id)
        if ev is None:
            print(f"[extrair_crop] evento {evento_id} não encontrado")
            return None
        # Usa ts_inicio — onde o detector viu o sinal pela primeira vez,
        # antes do veículo chegar/passar. Frame médio costuma já estar pós.
        ts = ev["ts_inicio"]
        # bbox do PRIMEIRO candidato (não a média) — mostra o que disparou
        first_cand = ev["candidatos"][0]
        bb = first_cand.get("bbox") or [0, 0, 0, 0]
        if len(bb) == 4:
            # bbox formato [x, y, w, h] — convertendo pra [x1, y1, x2, y2]
            x, y, w, h = bb
            bbox_local = (int(x), int(y), int(x + w), int(y + h))
        else:
            cx = ev["bbox_resumo"].get("centro_x_medio", 320)
            cy = ev["bbox_resumo"].get("centro_y_medio", 180)
            bbox_local = (cx - 80, cy - 50, cx + 80, cy + 50)
    elif ts is None or bbox_local is None:
        print("[extrair_crop] precisa de evento_id OU (ts + bbox_local)")
        return None

    # extrai frame e quadrante frontal correto
    slicer = GridSlicer(vp, sample_fps=0.0)
    cap = cv2.VideoCapture(str(vp))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(ts * fps))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        print(f"[extrair_crop] falha ao ler frame em ts={ts}s")
        return None
    frontal = slicer.extract_camera(frame, "frontal").copy()

    # marca bbox no frame inteiro
    x1, y1, x2, y2 = bbox_local
    H, W = frontal.shape[:2]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(W, x2), min(H, y2)
    annotated = frontal.copy()
    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # crop com padding 30px e upscale
    pad = 30
    cx0, cy0 = max(0, x1 - pad), max(0, y1 - pad)
    cx1, cy1 = min(W, x2 + pad), min(H, y2 + pad)
    crop = frontal[cy0:cy1, cx0:cx1]
    if crop.size > 0 and upscale > 1:
        crop = cv2.resize(crop, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)

    tag = evento_id if evento_id else f"ts{int(ts)}"
    out_full = OUTPUT_DIR / f"{hash_[:8]}_{tag}_full.png"
    out_crop = OUTPUT_DIR / f"{hash_[:8]}_{tag}_crop.png"
    cv2.imwrite(str(out_full), annotated)
    cv2.imwrite(str(out_crop), crop)
    print(f"[ok] {out_full.name} + {out_crop.name}  (ts={ts:.1f}s, bbox={bbox_local})")
    return out_full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hash", help="hash sha256 do vídeo")
    ap.add_argument("--evento_id", help="ex.: 7514b7f4_e06")
    ap.add_argument("--ts", type=float, help="timestamp em segundos")
    ap.add_argument("--bbox", help="x1,y1,x2,y2 em coords do quadrante frontal")
    ap.add_argument(
        "--pendentes",
        action="store_true",
        help="processa todos approveds R1020-G-a ainda não revisados",
    )
    ap.add_argument("--limpar", action="store_true", help="apaga /tmp/valbot_review/ antes")
    args = ap.parse_args()

    if args.limpar and OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    if args.pendentes:
        pendentes = listar_approveds_pendentes()
        print(f"[pendentes] {len(pendentes)} approveds R1020-G-a aguardando revisão visual")
        for v in pendentes:
            ev = (v.get("evidencia") or "").strip()
            evento_id = ""
            if ev.startswith("[") and "]" in ev:
                evento_id = ev[1 : ev.index("]")]
            if evento_id:
                extrair_crop(v["hash"], evento_id=evento_id)
            else:
                ts = float(v.get("ts") or 0)
                # fallback: ts aproximado, bbox central padrão
                extrair_crop(v["hash"], ts=ts, bbox_local=(160, 80, 480, 280))
        return

    if not args.hash:
        ap.error(
            "forneça --hash <h> [--evento_id <eid> | --ts X --bbox x1,y1,x2,y2] ou --pendentes"
        )
    if args.evento_id:
        extrair_crop(args.hash, evento_id=args.evento_id)
    elif args.ts is not None and args.bbox:
        x1, y1, x2, y2 = map(int, args.bbox.split(","))
        extrair_crop(args.hash, ts=args.ts, bbox_local=(x1, y1, x2, y2))
    else:
        ap.error("forneça --evento_id ou --ts + --bbox")


if __name__ == "__main__":
    main()
