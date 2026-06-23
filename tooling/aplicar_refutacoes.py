"""
Aplica refutações do `examples.jsonl` ao `yolo_custom_detections.json`
de cada vídeo, removendo entradas que o revisor já marcou como ilusão da IA.

Uso após o usuário negativar itens no painel:
    .venv/bin/python tooling/aplicar_refutacoes.py
    .venv/bin/python tooling/aplicar_refutacoes.py --gap-s 5  # raio mais largo
    .venv/bin/python tooling/aplicar_refutacoes.py --dry-run

Backend lê `yolo_custom_detections.json` direto, então restart do uvicorn
basta pra refletir no painel.

Heurística:
- Voto refuted casa com entrada YOLOC se MESMA classe + MESMA câmera + ts
  dentro de ±gap_s.
- Voto refuted em SINAL-* (entrada da biblioteca) também é honrado: removemos
  qualquer YOLOC daquela mesma classe/câmera próximo ts, e marcamos a entrada
  da biblioteca como suprimida (campo `suppressed_by_refute`) — bridge respeita.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSES_DIR = PROJECT_ROOT / "storage" / "analyses"
EXAMPLES_PATH = PROJECT_ROOT / "storage" / "training" / "examples.jsonl"


# infracao_id no examples.jsonl tem padrões:
#   YOLOC-PARE_CHAO-frontal      → classe=pare_chao, cam=frontal
#   SINAL-HORIZONTAL-PARE-CHAO-frontal → classe=pare_chao (legado)
#   R1020-G-a                    → infração tier_a (não relacionada com placa)
def _parse_infracao_id(inf_id: str) -> tuple[str, str] | None:
    """Devolve (classe_normalizada, camera) ou None se não for placa/sinalização."""
    if inf_id.startswith("YOLOC-"):
        rest = inf_id[len("YOLOC-") :]
        # YOLOC-<CLASSE>-<CAM> — split a partir do fim
        for cam in ("frontal", "lateral_direita", "interna", "traseira_esq"):
            suf = f"-{cam}"
            if rest.endswith(suf):
                return rest[: -len(suf)].lower(), cam
        return None
    if inf_id.startswith("SINAL-"):
        rest = inf_id[len("SINAL-") :]
        for cam in ("frontal", "lateral_direita", "interna", "traseira_esq"):
            suf = f"-{cam}"
            if rest.endswith(suf):
                cls_raw = rest[: -len(suf)]
                # Normaliza HORIZONTAL-PARE-CHAO → pare_chao, VERTICAL-PARE-R1 → pare_r1
                parts = cls_raw.split("-")
                if len(parts) >= 2 and parts[0] in ("HORIZONTAL", "VERTICAL"):
                    parts = parts[1:]
                return "_".join(p.lower() for p in parts), cam
        return None
    return None


def _carrega_refutacoes() -> dict[str, list[dict]]:
    """{hash: [{classe, cam, ts}]}."""
    out: dict[str, list[dict]] = {}
    if not EXAMPLES_PATH.exists():
        return out
    for line in EXAMPLES_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("decisao") != "refuted":
            continue
        hash_ = rec.get("hash")
        if not hash_:
            continue
        parsed = _parse_infracao_id(rec.get("infracao_id", ""))
        if parsed is None:
            continue
        cls, cam = parsed
        out.setdefault(hash_, []).append(
            {
                "classe": cls,
                "cam": cam,
                "ts": float(rec.get("ts") or 0),
            }
        )
    return out


def _aplicar_em_arquivo(yc_path: Path, refutas: list[dict], gap_s: float, dry: bool) -> dict:
    if not yc_path.exists():
        return {"hash": yc_path.parent.name, "skipped": "sem yolo_custom_detections.json"}
    data = json.loads(yc_path.read_text())
    entries = data.get("entries", [])
    n_before = len(entries)

    def deve_remover(e: dict) -> bool:
        cls = (e.get("class_name") or "").lower()
        cam = e.get("camera") or ""
        ts = float(e.get("ts") or 0)
        for r in refutas:
            if r["classe"] == cls and r["cam"] == cam and abs(ts - r["ts"]) <= gap_s:
                return True
        return False

    keep, drop = [], []
    for e in entries:
        (drop if deve_remover(e) else keep).append(e)
    if dry:
        return {
            "hash": yc_path.parent.name,
            "before": n_before,
            "drop": len(drop),
            "keep": len(keep),
            "dry_run": True,
        }
    data["entries"] = keep
    data["filtered_at"] = datetime.now().isoformat(timespec="seconds")
    data["refutas_aplicadas"] = len(refutas)
    data["n_dropped_by_refute"] = len(drop)
    yc_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return {"hash": yc_path.parent.name, "before": n_before, "after": len(keep), "drop": len(drop)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gap-s", type=float, default=3.0, help="raio temporal pra match (s)")
    ap.add_argument("--dry-run", action="store_true", help="só relata, não escreve")
    args = ap.parse_args()

    refutas_por_hash = _carrega_refutacoes()
    print(
        f"refutações em examples.jsonl: "
        f"{sum(len(v) for v in refutas_por_hash.values())} (em {len(refutas_por_hash)} hashes)"
    )

    if not refutas_por_hash:
        print("nada a aplicar.")
        return 0

    total_drop = 0
    for hash_, refutas in sorted(refutas_por_hash.items()):
        yc_path = ANALYSES_DIR / hash_ / "yolo_custom_detections.json"
        result = _aplicar_em_arquivo(yc_path, refutas, args.gap_s, args.dry_run)
        if "skipped" in result:
            print(f"  {hash_[:12]}  SKIP {result['skipped']}")
            continue
        if args.dry_run:
            print(
                f"  {hash_[:12]}  before={result['before']} drop={result['drop']} keep={result['keep']} (dry)"
            )
        else:
            print(
                f"  {hash_[:12]}  before={result['before']} after={result['after']} dropped={result['drop']}"
            )
        total_drop += result.get("drop", 0)

    print(f"\nTOTAL dropped: {total_drop}")
    if not args.dry_run and total_drop > 0:
        print("\nReinicie o backend pra refletir no painel:")
        print("  pkill -9 -f tooling.dev_backend_stub && \\")
        print(
            "    nohup .venv/bin/python -m tooling.dev_backend_stub > /tmp/valbot_backend.log 2>&1 &"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
