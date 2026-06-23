"""Renderiza o Laudo v2.0 (8 blocos) — HTML via Jinja2, PDF via WeasyPrint.

Separado de ``src/reporting/pdf.py`` de propósito: aquele importa WeasyPrint no
topo do módulo (quebra em ambientes sem a lib). Aqui o HTML é puro Jinja2 (sempre
disponível, testável sem WeasyPrint) e o PDF importa WeasyPrint de forma
preguiçosa — ausente → devolve ``None`` sem estourar (o HTML continua sendo o
artefato válido para fallback do endpoint).
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "laudo_v2.html"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_html(context: dict) -> str:
    """Renderiza o contexto de 8 blocos no HTML do laudo (sem WeasyPrint)."""
    return _env.get_template(TEMPLATE_NAME).render(**context)


def render_pdf(context: dict, out_pdf: str | Path) -> Path | None:
    """Renderiza o laudo em PDF (e grava o .html ao lado). WeasyPrint ausente → None."""
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(context)
    out_pdf.with_suffix(".html").write_text(html, encoding="utf-8")
    try:
        from weasyprint import HTML  # import preguiçoso
    except Exception:
        return None
    HTML(string=html, base_url=str(TEMPLATES_DIR)).write_pdf(str(out_pdf))
    return out_pdf
