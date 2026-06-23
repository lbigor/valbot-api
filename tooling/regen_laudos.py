"""Re-renderiza laudo.pdf a partir do result.json/upload.json já salvos
(sem reprocessar vídeo). Usa o _render_pdf do pipeline pra montar o contexto
idêntico ao da geração original; só o template muda.

Uso:
    python /tmp/regen_laudos.py <out_base_dir> <hash> [<hash> ...]

- Lê result.json + upload.json de  $ANALYSES_DIR/<hash>/
- Escreve laudo.pdf + laudo.html em  <out_base_dir>/<hash>/
  (passe o próprio ANALYSES_DIR p/ sobrescrever in-place, ou /tmp/regen p/ prova)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ANALYSES_DIR = Path(os.environ.get("VALBOT_ANALYSES_DIR", "/opt/valbot/storage/analyses"))


def main() -> None:
    out_base = Path(sys.argv[1])
    hashes = sys.argv[2:]
    if not hashes:
        raise SystemExit("informe ao menos 1 hash")

    from tooling.process_pending_s3 import _render_pdf

    for h in hashes:
        src = ANALYSES_DIR / h
        result = json.loads((src / "result.json").read_text())
        upload_meta = json.loads((src / "upload.json").read_text())
        out_dir = out_base / h
        out_dir.mkdir(parents=True, exist_ok=True)
        _render_pdf(out_dir, result, upload_meta)
        pdf = out_dir / "laudo.pdf"
        print(f"OK {h} -> {pdf} ({pdf.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
