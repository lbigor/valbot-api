#!/usr/bin/env python3
"""Gera PDF de 1-2 páginas com Meta e Budget para o Chrysler."""

from pathlib import Path

import markdown
from weasyprint import CSS, HTML

PLAN_PATH = Path("/Users/igorlima/.claude/plans/resumo-chrysler.md")
OUT_PDF = Path("/Users/igorlima/Documents/Valbot/resumo-chrysler.pdf")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><title>Valma — Meta e Budget</title></head>
<body>
<section class="cover-bar">
  <div class="brand">VALMA</div>
  <div class="tag">CONFIDENCIAL · CFO</div>
</section>
<section class="content">
{content}
</section>
</body></html>
"""

CSS_STYLE = """
@page {
    size: A4;
    margin: 12mm 14mm 10mm 14mm;
    @bottom-right { content: ""; }
    @bottom-left { content: ""; }
}
* { box-sizing: border-box; }
body { font-family: "Inter", "Helvetica Neue", -apple-system, sans-serif; font-size: 9pt; line-height: 1.35; color: #1F2937; margin: 0; padding: 0; }

.cover-bar {
    background: #1A2B4C;
    color: white;
    padding: 3mm 5mm;
    margin: -2mm -2mm 4mm -2mm;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 3px solid #00A651;
}
.cover-bar .brand { font-size: 16pt; font-weight: 800; letter-spacing: 0.15em; color: #00A651; }
.cover-bar .tag { font-size: 8pt; font-weight: 600; letter-spacing: 0.1em; color: white; }

h1 { font-size: 18pt; color: #1A2B4C; border-bottom: 2px solid #00A651; padding-bottom: 1.5mm; margin: 2mm 0 3mm 0; page-break-after: avoid; }
h2 { font-size: 12pt; color: #1A2B4C; margin: 4mm 0 1.5mm 0; page-break-after: avoid; }
h3 { font-size: 10pt; color: #00A651; margin: 2mm 0 1mm 0; page-break-after: avoid; }

p { margin: 0 0 1.5mm 0; }
strong { color: #1A2B4C; font-weight: 700; }

blockquote { border-left: 3px solid #00A651; background: #F0FDF4; padding: 2mm 4mm; margin: 2mm 0; font-size: 8.5pt; }
blockquote p:last-child { margin-bottom: 0; }

table { width: 100%; border-collapse: collapse; margin: 1.5mm 0 2.5mm 0; font-size: 8.5pt; }
th { background: #1A2B4C; color: white; padding: 1.5mm 2.5mm; text-align: left; font-weight: 600; border: 1px solid #1A2B4C; }
td { padding: 1.2mm 2.5mm; border: 1px solid #E5E7EB; }
tr:nth-child(even) td { background: #F9FAFB; }

ul, ol { margin: 0.5mm 0 1.5mm 0; padding-left: 5mm; }
li { margin: 0.3mm 0; }
hr { border: none; border-top: 1px solid #E5E7EB; margin: 3mm 0; }

a { color: #00A651; text-decoration: none; }
"""


def main():
    md_text = PLAN_PATH.read_text(encoding="utf-8")
    md = markdown.Markdown(extensions=["tables", "fenced_code", "attr_list", "sane_lists"])
    body_html = md.convert(md_text)
    full_html = HTML_TEMPLATE.format(content=body_html)
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=full_html).write_pdf(target=str(OUT_PDF), stylesheets=[CSS(string=CSS_STYLE)])
    print(f"PDF gerado: {OUT_PDF}")
    print(f"Tamanho: {OUT_PDF.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
