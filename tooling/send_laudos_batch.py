"""Envia o laudo PDF de um LOTE de exames pro callback Techpratico.

Para cada hash (lista em arquivo, 1 por linha):
  • lê o veredito VALBOT do DB (aprovado/gate) -> A/R/N
  • lê /opt/valbot/storage/analyses/<hash>/laudo.pdf -> base64
  • POST {id_analise, resultado, relatorio} com X-API-Key
  • grava laudo_envio_* no DB (auditoria)

Uso: python -m tooling.send_laudos_batch <arquivo_hashes> [--dry-run]
Env: VALBOT_TECHPRATICO_API_KEY (obrigatório p/ envio real)
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ANALYSES_DIR = Path(os.environ.get("VALBOT_ANALYSES_DIR", "/opt/valbot/storage/analyses"))
URL = os.environ.get(
    "VALBOT_TECHPRATICO_RETORNO_URL",
    "https://convert.se.techpratico.net/conversao/retorno-analise",
)
KEY = os.environ.get("VALBOT_TECHPRATICO_API_KEY", "")


def _verdicts(hashes: list[str]) -> dict[str, str]:
    """hash -> A/R/N pelo veredito VALBOT (mesma regra do mapear_resultado_valbot)."""
    from tooling.api_stub import db as _db

    out: dict[str, str] = {}
    with _db._conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT hash, aprovado, gate_rejected FROM exams WHERE hash = ANY(%s)",
            (hashes,),
        )
        for h, aprovado, gate in cur.fetchall():
            if gate:
                out[h] = "N"
            elif aprovado is True:
                out[h] = "A"
            elif aprovado is False:
                out[h] = "R"
            else:
                out[h] = "N"
    return out


def _record(h: str, status: str, resultado: str, resposta: str) -> None:
    try:
        from tooling.api_stub import db as _db

        if hasattr(_db, "update_laudo_envio"):
            _db.update_laudo_envio(
                h,
                status=status,
                resultado=resultado,
                resposta=resposta[:500],
                sucesso=(status == "success"),
            )
    except Exception as e:  # noqa: BLE001
        print(f"   (audit DB falhou p/ {h[:12]}: {e})", flush=True)


def main() -> int:
    path = sys.argv[1]
    dry = "--dry-run" in sys.argv[2:]
    hashes = [ln.strip() for ln in open(path) if ln.strip() and not ln.startswith("#")]
    verd = _verdicts(hashes)

    # validação: todos têm PDF + veredito
    faltando = []
    for h in hashes:
        pdf = ANALYSES_DIR / h / "laudo.pdf"
        if not pdf.exists() or pdf.stat().st_size == 0:
            faltando.append(h)
    dist: dict[str, int] = {}
    for h in hashes:
        dist[verd.get(h, "?")] = dist.get(verd.get(h, "?"), 0) + 1
    print(
        f"[send] {len(hashes)} exames | split={dist} | PDFs faltando={len(faltando)} | dry={dry}",
        flush=True,
    )
    if faltando:
        print("ABORT: sem PDF -> " + ", ".join(x[:12] for x in faltando[:10]), flush=True)
        return 2
    if dry:
        print("DRY-RUN: nenhum POST disparado.", flush=True)
        return 0
    if not KEY:
        print("ABORT: VALBOT_TECHPRATICO_API_KEY ausente.", flush=True)
        return 2

    ok = fail = 0
    for i, h in enumerate(hashes, 1):
        r = verd.get(h, "N")
        pdf_b64 = base64.b64encode((ANALYSES_DIR / h / "laudo.pdf").read_bytes()).decode("ascii")
        body = json.dumps({"id_analise": h, "resultado": r, "relatorio": pdf_b64}).encode()
        req = urllib.request.Request(
            URL,
            data=body,
            method="POST",
            headers={"X-API-Key": KEY, "Content-Type": "application/json"},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            txt = resp.read().decode("utf-8", "replace")
            success = resp.status == 200 and "SUCESSO" in txt.upper()
            print(
                f"[{i}/{len(hashes)}] {h[:12]} res={r} HTTP {resp.status} {'OK' if success else 'WARN'} {txt[:70]}",
                flush=True,
            )
            _record(h, "success" if success else "failed", r, txt)
            ok += 1 if success else 0
            fail += 0 if success else 1
            if not success:
                print("   >> resposta inesperada, parando", flush=True)
                break
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")
            print(
                f"[{i}/{len(hashes)}] {h[:12]} res={r} HTTP {e.code} FAIL {txt[:120]}", flush=True
            )
            _record(h, "failed", r, txt)
            fail += 1
            print("   >> parando", flush=True)
            break
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(hashes)}] {h[:12]} res={r} ERRO rede {e!r}", flush=True)
            _record(h, "failed", r, str(e))
            fail += 1
            print("   >> parando", flush=True)
            break
        time.sleep(0.4)

    print("=" * 50, flush=True)
    print(f"FIM envio: {ok} ok, {fail} fail de {len(hashes)}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
