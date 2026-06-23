"""Renderiza laudo HTML (Jinja2) e converte em PDF (WeasyPrint)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_pdf(context: dict, out_pdf: str | Path) -> Path:
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    tpl = _env.get_template("laudo.html")
    html = tpl.render(**context)
    HTML(string=html, base_url=str(TEMPLATES_DIR)).write_pdf(str(out_pdf))
    (out_pdf.with_suffix(".html")).write_text(html, encoding="utf-8")
    return out_pdf
