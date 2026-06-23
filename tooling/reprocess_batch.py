"""Reprocessa uma LISTA de exames (cofre-safe) com throttle, timing e custo.

Diferente do --reprocess-all (que pega TODOS os exames com upload.json), este
roda só os hashes de um arquivo (1 por linha). Para cada um:
  1. reset_one_for_reprocess (preserva upload.json/video.mp4/cofre no DB)
  2. process_one (que já usa analyze_with_retry: backoff em 429/JSON truncado)
  3. throttle entre itens (VALBOT_THROTTLE_S, default 4s) — evita rajada de 429

Uso: python -m tooling.reprocess_batch <arquivo_hashes> [--dry-run]
Ao fim imprime tempo total e o custo real (somado do DB) do lote.
"""

from __future__ import annotations

import os
import sys
import time

from tooling.process_pending_s3 import process_one, reset_one_for_reprocess


def _custo_lote(hashes: list[str]) -> dict:
    try:
        from tooling.api_stub import db as _db

        with _db._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FILTER (WHERE status='processed'), "
                "count(*) FILTER (WHERE status='failed'), "
                "COALESCE(sum(cost_usd),0), COALESCE(avg(gemini_elapsed_s),0) "
                "FROM exams WHERE hash = ANY(%s)",
                (hashes,),
            )
            ok, fail, custo, seg = cur.fetchone()
            return {"ok": ok, "fail": fail, "custo_usd": float(custo), "seg_medio": float(seg)}
    except Exception as e:  # noqa: BLE001
        print(f"[custo_lote] falhou ({e}); calcule via psql", flush=True)
        return {}


def main() -> int:
    path = sys.argv[1]
    dry = "--dry-run" in sys.argv[2:]
    throttle = float(os.getenv("VALBOT_THROTTLE_S", "4"))
    hashes = [ln.strip() for ln in open(path) if ln.strip() and not ln.startswith("#")]
    print(f"[reprocess_batch] {len(hashes)} exames | throttle={throttle}s | dry={dry}", flush=True)

    t0 = time.time()
    ok = fail = 0
    for i, h in enumerate(hashes, 1):
        ti = time.time()
        try:
            if not dry:
                reset_one_for_reprocess(h)
            done = process_one(h, dry_run=dry)
        except Exception as e:  # noqa: BLE001
            done = False
            print(f"[{i}/{len(hashes)}] {h[:12]} EXCEPTION {str(e)[:120]}", flush=True)
        dt = time.time() - ti
        if done:
            ok += 1
        else:
            fail += 1
        print(
            f"[{i}/{len(hashes)}] {h[:12]} {'OK' if done else 'FAIL'} ({dt:.0f}s) "
            f"acum ok={ok} fail={fail}",
            flush=True,
        )
        if i < len(hashes) and not dry:
            time.sleep(throttle)

    total = time.time() - t0
    print("=" * 60, flush=True)
    print(f"FIM: {ok} ok, {fail} fail em {total / 60:.1f} min ({total:.0f}s)", flush=True)
    if not dry:
        c = _custo_lote(hashes)
        if c:
            print(
                f"DB do lote: processed={c['ok']} failed={c['fail']} "
                f"custo_real=${c['custo_usd']:.4f} seg_medio={c['seg_medio']:.1f}",
                flush=True,
            )
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
