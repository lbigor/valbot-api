"""Renderiza um laudo usando um template ARBITRÁRIO (de /tmp), lendo o
result.json/upload.json já salvos. NÃO altera a fonte de produção — só lê
dados e escreve PDF em <out_base>/<hash>/laudo.pdf.

Uso: python regen_laudo_tmpl.py <template_dir> <out_base> <hash> [<hash> ...]
  <template_dir> deve conter laudo.html
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime as _dt
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from src.reporting.adapter import build_context

ANALYSES_DIR = Path(os.environ.get("VALBOT_ANALYSES_DIR", "/opt/valbot/storage/analyses"))


def _ctx(result: dict, upload_meta: dict) -> dict:
    detectadas = []
    for d in result.get("infracoes_detectadas", []) or []:
        ts = d.get("timestamp_s")
        if ts is None:
            ts = d.get("ts_seconds") or 0
        detectadas.append(
            {
                "id": d.get("id") or f"i{len(detectadas)}",
                "timestamp_inicio": float(ts or 0),
                "duracao_s": float(d.get("duracao_s") or 1.0),
                "evidencia": d.get("evidence") or d.get("evidencia") or "",
                "descricao_longa": d.get("evidence") or "",
                "occurrences": 1,
            }
        )
    candidato = dict(upload_meta.get("candidato", {}))
    candidato["veiculo"] = upload_meta.get("exame", {}).get("veiculo", "—")
    hash_short = (result.get("video", {}).get("hash") or "")[:8].upper() or "UNKNOWN"
    metadata = {
        "laudo_id": f"LAU-{hash_short}",
        "rubrica": "1020_2025",
        "video_hash": result.get("video", {}).get("hash", ""),
        "modelo_versao": result.get("engine", {}).get("model", "gemini-3.1-pro-preview"),
        "duracao_seg": float(result.get("video", {}).get("duration_s") or 240.0),
        "limite_pontuacao": 10,
        "local": upload_meta.get("exame", {}).get("local", "—"),
        "examinador": upload_meta.get("exame", {}).get("examinador", "—"),
        "data_exame": _dt.now().strftime("%d/%m/%Y"),
        "result_hash": hashlib.sha1(
            json.dumps(result, sort_keys=True, default=str).encode()
        ).hexdigest()[:12],
        "analysis_version": "valbot-vertex-v25",
    }
    ctx = dict(build_context(detectadas, candidato, metadata))
    ctx["contagem"] = {"eliminatoria": 0, **ctx.get("contagem", {})}
    return ctx


def main() -> None:
    template_dir, out_base = sys.argv[1], Path(sys.argv[2])
    hashes = sys.argv[3:]
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template("laudo.html")
    for h in hashes:
        src = ANALYSES_DIR / h
        result = json.loads((src / "result.json").read_text())
        upload_meta = json.loads((src / "upload.json").read_text())
        html = tpl.render(**_ctx(result, upload_meta))
        out_dir = out_base / h
        out_dir.mkdir(parents=True, exist_ok=True)
        HTML(string=html, base_url=template_dir).write_pdf(str(out_dir / "laudo.pdf"))
        print(f"OK {h} -> {out_dir / 'laudo.pdf'} ({(out_dir / 'laudo.pdf').stat().st_size} bytes)")


if __name__ == "__main__":
    main()
