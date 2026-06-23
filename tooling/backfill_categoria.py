"""One-shot: popula exams.categoria quando vazio, a partir do source_url.

Integração batch DETRAN não envia categoria no init_upload — só a URL do S3
oficial techpratico, que tem o padrão:
    https://techpratico-stream-se-cache.s3.amazonaws.com/YYYYMMDD/HHMM/<CAT>/<RENACH>_*.mp4

Esse script:
  1. Lista exames com categoria NULL ou vazia
  2. Lê upload.json de cada um (em /opt/valbot/storage/analyses/<hash>/)
  3. Extrai categoria do path do source_url via regex
  4. UPDATE exams SET categoria = ? WHERE hash = ?

Idempotente: rodar de novo só atualiza quem ainda está vazio.

Uso (na VM valbot-prod, dentro do container api):
    docker exec valbot-api python -m tooling.backfill_categoria
Ou da máquina local:
    gcloud compute ssh valbot-prod --zone=us-central1-a \\
      --command="docker exec valbot-api python -m tooling.backfill_categoria"
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ANALYSES_DIR = Path(os.environ.get("ANALYSES_DIR", "/opt/valbot/storage/analyses"))

# Categorias compostas ANTES das simples — regex avalia esquerda→direita.
_CAT_RE = re.compile(r"/(ACC|AB|AC|AD|AE|A|B|C|D|E)/[A-Z0-9]+_")


def _extract_categoria(source_url: str) -> str:
    """Retorna categoria CNH detectada no path da URL, ou string vazia."""
    if not source_url:
        return ""
    m = _CAT_RE.search(source_url)
    return m.group(1) if m else ""


def main() -> int:
    try:
        from tooling.api_stub import db as _db
    except ImportError as e:
        log.error("não consigo importar tooling.api_stub.db: %s", e)
        return 2

    # Bypass do flag _DISABLED — esse script roda como administrador da DB.
    if _db._DISABLED:  # noqa: SLF001
        log.error("DB disabled (DATABASE_URL ausente?). Abortando.")
        return 2

    with _db._conn() as c:  # noqa: SLF001
        if c is None:
            log.error("sem conexão com Postgres.")
            return 2
        # Padrão db.py: c.execute(...).fetchall(). `c` é um Cursor-like wrapper
        # (psycopg3 ConnectionWrapper) que expõe execute encadeável.
        rows = c.execute(
            "SELECT hash FROM exams WHERE categoria IS NULL OR categoria = '' "
            "ORDER BY created_at DESC"
        ).fetchall()
        hashes = [row[0] for row in rows]

    log.info("encontrados %d exames sem categoria", len(hashes))
    if not hashes:
        return 0

    if not ANALYSES_DIR.exists():
        log.error("ANALYSES_DIR não existe: %s", ANALYSES_DIR)
        return 2

    updated, skipped_no_upload, skipped_no_url, skipped_no_match = 0, 0, 0, 0
    for h in hashes:
        upload_path = ANALYSES_DIR / h / "upload.json"
        if not upload_path.exists():
            skipped_no_upload += 1
            log.debug("[%s] upload.json ausente — pula", h[:12])
            continue
        try:
            upload_meta = json.loads(upload_path.read_text())
        except Exception as e:
            log.warning("[%s] upload.json corrompido (%s) — pula", h[:12], e)
            skipped_no_upload += 1
            continue

        source_url = (upload_meta.get("video") or {}).get("source_url") or ""
        if not source_url:
            skipped_no_url += 1
            log.debug("[%s] sem source_url — pula", h[:12])
            continue

        cat = _extract_categoria(source_url)
        if not cat:
            skipped_no_match += 1
            log.info("[%s] source_url não bate em /<CAT>/<RENACH>_: %s", h[:12], source_url[:80])
            continue

        # Persiste — reusa o caminho seguro com COALESCE/NULLIF preservando
        # valor existente. Mas como já filtramos NULL/'', podemos UPDATE direto.
        try:
            with _db._conn() as c:  # noqa: SLF001
                if c is None:
                    continue
                c.execute("UPDATE exams SET categoria = %s WHERE hash = %s", (cat, h))
            updated += 1
            log.info("[%s] categoria=%s ✓", h[:12], cat)
        except Exception as e:
            log.exception("[%s] UPDATE falhou: %s", h[:12], e)

    log.info(
        "backfill_categoria FIM: updated=%d skipped_no_upload=%d skipped_no_url=%d skipped_no_match=%d",
        updated,
        skipped_no_upload,
        skipped_no_url,
        skipped_no_match,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
