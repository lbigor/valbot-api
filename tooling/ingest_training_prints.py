"""
Ingere prints de treino que o usuário enviou no chat (timestamp + imagem +
infracao_id) e persiste como exemplo `approved`/`refuted`/`inconclusive` no
dataset, copiando a imagem pra `storage/analyses/<hash>/training_prints/`.

Quando a decisão é `approved` e a infração é pontuável, também faz append em
`result.json#infracoes_detectadas` pra o painel "Detecções da IA" mostrar
imediatamente, sem esperar re-run do tier_a.

Uso:
    python tooling/ingest_training_prints.py \\
        --hash 19d72ba460e2ddb300f796306fc8a5c4e1a41e4d3fa60cc96b0b5677151753a4 \\
        --ts 42.5 --infracao R1020-G-a --decisao approved \\
        --evidencia "PARE r-1 visível à direita" \\
        --image /Users/.../print.jpg

    # Via API (default — backend deve estar rodando):
    python tooling/ingest_training_prints.py --hash <h> --ts 12 --infracao R1020-G-a \\
        --decisao approved --evidencia "..." --image foo.jpg --api http://127.0.0.1:8000

    # Sem backend (escreve direto em examples.jsonl + result.json):
    python tooling/ingest_training_prints.py --hash <h> --ts 12 ... --offline
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSES_DIR = PROJECT_ROOT / "storage" / "analyses"
EXAMPLES_PATH = PROJECT_ROOT / "storage" / "training" / "examples.jsonl"

VALID_DECISOES = {"approved", "refuted", "inconclusive"}


def _fps_from_result(result: dict) -> float:
    return float((result.get("video") or {}).get("fps") or 30.0)


def _append_examples_jsonl(record: dict) -> int:
    EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXAMPLES_PATH.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return sum(1 for _ in EXAMPLES_PATH.open())


def _post_to_backend(api_base: str, hash_: str, payload: dict) -> dict:
    import urllib.request

    url = f"{api_base.rstrip('/')}/api/analyses/{hash_}/training-example"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _append_infracao_detectada(
    result_path: Path,
    infracao_id: str,
    ts: float,
    evidencia: str,
    evidencia_path: str,
    severidade: str,
    pontos: int,
    descricao: str,
) -> None:
    result = json.loads(result_path.read_text())
    detectadas = result.get("infracoes_detectadas") or []
    detectadas.append(
        {
            "id": infracao_id,
            "ts": ts,
            "severidade": severidade,
            "pontos": pontos,
            "descricao": descricao,
            "evidencia": evidencia,
            "evidencia_path": evidencia_path,
            "origem": "training_print",
            "ingested_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    result["infracoes_detectadas"] = detectadas
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))


def _lookup_infracao_meta(result: dict, infracao_id: str) -> tuple[str, int, str]:
    """Tenta achar severidade/pontos/descricao em infracoes_avaliadas."""
    for av in result.get("infracoes_avaliadas") or []:
        if av.get("id") == infracao_id:
            return (
                (av.get("severidade") or "leve").lower(),
                int(av.get("pontos") or 0),
                av.get("descricao") or "",
            )
    return ("leve", 0, "")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hash", required=True, help="hash do vídeo (storage/analyses/<hash>)")
    p.add_argument("--ts", required=True, type=float, help="timestamp em segundos")
    p.add_argument("--infracao", required=True, help="id da infração (ex: R1020-G-a)")
    p.add_argument("--decisao", required=True, choices=sorted(VALID_DECISOES))
    p.add_argument("--evidencia", default="", help="texto curto descrevendo o que aparece")
    p.add_argument("--image", required=True, help="caminho do print que o usuário enviou")
    p.add_argument("--api", default="http://127.0.0.1:8000", help="base URL do backend")
    p.add_argument(
        "--offline",
        action="store_true",
        help="não chamar o backend; escrever direto em examples.jsonl",
    )
    args = p.parse_args()

    hash_ = args.hash
    base = ANALYSES_DIR / hash_
    if not base.exists():
        print(f"erro: hash {hash_!r} não existe em {ANALYSES_DIR}", file=sys.stderr)
        return 2

    src = Path(args.image).expanduser().resolve()
    if not src.exists():
        print(f"erro: imagem {src} não encontrada", file=sys.stderr)
        return 2

    result_path = base / "result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {}
    fps = _fps_from_result(result) if result else 30.0
    frame_idx = int(round(args.ts * fps))

    # 1. copia a imagem
    dst_dir = base / "training_prints"
    dst_dir.mkdir(parents=True, exist_ok=True)
    safe_inf = args.infracao.replace("/", "_")
    dst = dst_dir / f"{args.ts:09.2f}_{safe_inf}{src.suffix.lower()}"
    shutil.copy2(src, dst)
    rel_evidencia = str(dst.relative_to(PROJECT_ROOT))
    print(f"copiei {src.name} → {rel_evidencia}")

    # 2. registra em examples.jsonl (via backend ou direto)
    payload = {
        "infracao_id": args.infracao,
        "frame_idx": frame_idx,
        "ts": args.ts,
        "decisao": args.decisao,
        "evidencia": (args.evidencia or "")[:500],
        "vote": {"approved": "S", "refuted": "N"}.get(args.decisao, ""),
    }
    if args.offline:
        record = {
            "hash": hash_,
            **payload,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        }
        total = _append_examples_jsonl(record)
        print(f"examples.jsonl atualizado (offline). total: {total}")
    else:
        try:
            resp = _post_to_backend(args.api, hash_, payload)
            print(
                f"POST /api/analyses/{hash_[:12]}.../training-example → {resp.get('total_examples')} exemplos"
            )
        except Exception as e:
            print(f"warn: backend indisponível ({e}); fallback offline.")
            record = {
                "hash": hash_,
                **payload,
                "saved_at": datetime.now().isoformat(timespec="seconds"),
            }
            total = _append_examples_jsonl(record)
            print(f"examples.jsonl atualizado (offline). total: {total}")

    # 3. se approved + result.json existe → promove pra infracoes_detectadas
    if args.decisao == "approved" and result_path.exists():
        sev, pts, desc = _lookup_infracao_meta(result, args.infracao)
        _append_infracao_detectada(
            result_path,
            infracao_id=args.infracao,
            ts=args.ts,
            evidencia=args.evidencia or "ingestão de print do usuário",
            evidencia_path=rel_evidencia,
            severidade=sev,
            pontos=pts,
            descricao=desc,
        )
        print(f"result.json#infracoes_detectadas + {args.infracao} ({sev}/{pts} pts)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
