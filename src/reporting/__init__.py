"""Relatórios/laudos do pipeline (HTML + PDF).

O laudo v1 (`build_context`/`render_pdf`) depende de WeasyPrint, dep dura em
produção (``requirements.txt``) mas que pode faltar em dev. Importamos de forma
tolerante para que o laudo v2 (``render_laudo_v2``, HTML puro + PDF preguiçoso)
seja utilizável mesmo sem WeasyPrint instalado.
"""

from src.reporting.adapter import build_context

try:  # WeasyPrint ausente (dev) → render_pdf vira None, sem quebrar o import.
    from src.reporting.pdf import render_pdf
except Exception:  # pragma: no cover
    render_pdf = None  # type: ignore[assignment]

__all__ = ["build_context", "render_pdf"]
