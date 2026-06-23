#!/usr/bin/env python3
"""
Gera PDF profissional do Plano Estratégico Valma.
Estilo: Megawork-inspired (verde/navy, sans-serif, KPI cards, footer paginado).
"""

import re
from datetime import date
from pathlib import Path

import markdown
from weasyprint import CSS, HTML

PLAN_PATH = Path("/Users/igorlima/.claude/plans/preciso-montar-um-plano-lucky-kite.md")
OUT_PDF = Path("/Users/igorlima/Documents/Valbot/plano-valma-5anos.pdf")

# ----- HTML template -----
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Plano Estratégico Valma</title>
</head>
<body>

<!-- COVER PAGE -->
<section class="cover">
  <div class="cover-brand">VALMA</div>
  <div class="cover-divider"></div>
  <h1 class="cover-title">Plano Estratégico de<br>Infraestrutura GPU</h1>
  <h2 class="cover-subtitle">5 cenários de volume — do MVP a 50% do Brasil</h2>
  <div class="cover-meta">
    <table>
      <tr><td>Documento elaborado por</td><td><strong>Igor Bernardes Lima</strong> — CTO Valma</td></tr>
      <tr><td>Audiência</td><td>Conselho de sócios + parceiros estratégicos</td></tr>
      <tr><td>Versão</td><td>2.1</td></tr>
      <tr><td>Data</td><td>{date_str}</td></tr>
      <tr><td>Cadência de revisão</td><td>Trimestral, modelo SAP Activate</td></tr>
      <tr><td>Classificação</td><td><span class="confidential">CONFIDENCIAL — uso interno</span></td></tr>
    </table>
  </div>
  <div class="cover-recipients">
    <strong>Destinatários:</strong> Chrysler · Victor · Rodrigo · Igor · Techpark · Ayko
  </div>
</section>

<!-- KPI HERO PAGE -->
<section class="kpi-hero">
  <h1>Visão executiva — números-chave</h1>
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-value">60k</div>
      <div class="kpi-label">vídeos/mês baseline Techpark</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value">180k</div>
      <div class="kpi-label">vídeos/mês meta 50% Brasil (5 anos)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value">23</div>
      <div class="kpi-label">H100 necessárias no Cenário D (50% BR)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value">R$ 11M</div>
      <div class="kpi-label">TCO 5 anos NET (BUY + depreciação)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value">R$ 13M</div>
      <div class="kpi-label">receita anual estimada @ R$ 6/vídeo</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value">14</div>
      <div class="kpi-label">UFs alvo (50% do Brasil)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value">R$ 42k</div>
      <div class="kpi-label">custo do MVP — 30 dias 1.000 vídeos/dia</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value">R$ 1,17</div>
      <div class="kpi-label">custo unitário/vídeo em regime escala</div>
    </div>
  </div>
  <div class="kpi-footnote">
    Premissas: 340 vídeos/dia por H100 (pipeline Tier A+B mix, utilização 70%, 24/7), preço de venda alvo R$ 5-8/vídeo, infraestrutura própria colocada em Ayko Vitória ou Scala Tamboré.
  </div>
</section>

<!-- TOC -->
<section class="toc">
  <h1>Sumário</h1>
  {toc}
</section>

<!-- MAIN CONTENT -->
<section class="content">
{content}
</section>

</body>
</html>
"""

# ----- CSS -----
CSS_STYLE = """
@page {
    size: A4;
    margin: 22mm 18mm 22mm 18mm;

    @top-left {
        content: "Plano Estratégico Valma";
        font-family: "Inter", "Helvetica Neue", sans-serif;
        font-size: 8.5pt;
        color: #1A2B4C;
        font-weight: 600;
    }
    @top-right {
        content: "VALMA · CONFIDENCIAL";
        font-family: "Inter", "Helvetica Neue", sans-serif;
        font-size: 8.5pt;
        color: #00A651;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    @bottom-left {
        content: "v2.1 · mai/2026";
        font-family: "Inter", "Helvetica Neue", sans-serif;
        font-size: 8pt;
        color: #6B7280;
    }
    @bottom-right {
        content: "Página " counter(page) " de " counter(pages);
        font-family: "Inter", "Helvetica Neue", sans-serif;
        font-size: 8pt;
        color: #6B7280;
    }
}

@page cover {
    margin: 0;
    @top-left { content: ""; }
    @top-right { content: ""; }
    @bottom-left { content: ""; }
    @bottom-right { content: ""; }
}

* { box-sizing: border-box; }

body {
    font-family: "Inter", "Helvetica Neue", -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 9.5pt;
    line-height: 1.55;
    color: #1F2937;
    margin: 0;
    padding: 0;
}

/* ============== COVER ============== */
.cover {
    page: cover;
    page-break-after: always;
    padding: 60mm 24mm 24mm 24mm;
    height: 297mm;
    background: linear-gradient(180deg, #1A2B4C 0%, #1A2B4C 65%, #00A651 65%, #00A651 100%);
    color: white;
    position: relative;
}

.cover-brand {
    font-size: 36pt;
    font-weight: 800;
    letter-spacing: 0.15em;
    color: #00A651;
}

.cover-divider {
    width: 80mm;
    height: 4px;
    background: #00A651;
    margin: 12mm 0;
}

.cover-title {
    font-size: 32pt;
    font-weight: 700;
    line-height: 1.15;
    margin: 0 0 8mm 0;
    color: white;
}

.cover-subtitle {
    font-size: 14pt;
    font-weight: 400;
    color: #cbd5e1;
    margin: 0 0 30mm 0;
}

.cover-meta table {
    width: 100%;
    color: white;
    font-size: 10pt;
    border-collapse: collapse;
    background: transparent !important;
}
.cover-meta td,
.cover-meta tr:nth-child(even) td,
.cover-meta tr:nth-child(odd) td {
    padding: 3mm 0;
    border: none !important;
    border-bottom: 1px solid rgba(255,255,255,0.15) !important;
    background: transparent !important;
    color: white;
}
.cover-meta td:first-child {
    color: #94a3b8;
    width: 40%;
}
.cover-meta td strong { color: white; }

.confidential {
    background: #DC2626;
    color: white;
    padding: 1mm 3mm;
    border-radius: 3px;
    font-weight: 700;
    font-size: 9pt;
}

.cover-recipients {
    position: absolute;
    bottom: 14mm;
    left: 24mm;
    right: 24mm;
    color: white;
    font-size: 9.5pt;
    text-align: center;
    border-top: 1px solid rgba(255,255,255,0.3);
    padding-top: 4mm;
}

/* ============== KPI HERO ============== */
.kpi-hero {
    page-break-after: always;
    padding-top: 5mm;
}
.kpi-hero h1 {
    font-size: 22pt;
    color: #1A2B4C;
    border-bottom: 4px solid #00A651;
    padding-bottom: 4mm;
    margin-bottom: 10mm;
}
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 5mm;
    margin-bottom: 10mm;
}
.kpi-card {
    border: 1px solid #E5E7EB;
    border-left: 4px solid #00A651;
    padding: 6mm 7mm;
    background: #F9FAFB;
    border-radius: 2px;
}
.kpi-value {
    font-size: 28pt;
    font-weight: 800;
    color: #1A2B4C;
    line-height: 1;
    margin-bottom: 2mm;
}
.kpi-label {
    font-size: 9pt;
    color: #4B5563;
    line-height: 1.3;
}
.kpi-footnote {
    font-size: 8pt;
    color: #6B7280;
    font-style: italic;
    border-top: 1px solid #E5E7EB;
    padding-top: 4mm;
    margin-top: 8mm;
}

/* ============== TOC ============== */
.toc {
    page-break-after: always;
    padding-top: 5mm;
}
.toc h1 {
    font-size: 22pt;
    color: #1A2B4C;
    border-bottom: 4px solid #00A651;
    padding-bottom: 4mm;
    margin-bottom: 8mm;
}
.toc ul {
    list-style: none;
    padding: 0;
}
.toc > ul > li {
    margin: 2.5mm 0;
    font-size: 11pt;
    font-weight: 600;
    color: #1A2B4C;
}
.toc > ul > li > ul > li {
    margin: 1mm 0 1mm 6mm;
    font-size: 9.5pt;
    font-weight: 400;
    color: #4B5563;
}

/* ============== CONTENT ============== */
.content { padding-top: 4mm; }

h1 {
    font-size: 18pt;
    color: #1A2B4C;
    border-bottom: 3px solid #00A651;
    padding-bottom: 3mm;
    margin: 12mm 0 5mm 0;
    page-break-after: avoid;
    page-break-inside: avoid;
    /* Force at least 4 lines of content after h1 to avoid orphan title */
    orphans: 4;
    widows: 2;
}
h2 {
    font-size: 14pt;
    color: #1A2B4C;
    margin: 8mm 0 3mm 0;
    page-break-after: avoid;
    page-break-inside: avoid;
    orphans: 3;
    widows: 2;
}
h3 {
    font-size: 11.5pt;
    color: #00A651;
    margin: 6mm 0 2mm 0;
    page-break-after: avoid;
    page-break-inside: avoid;
}
h4 {
    font-size: 10.5pt;
    color: #1A2B4C;
    margin: 4mm 0 2mm 0;
    page-break-after: avoid;
    page-break-inside: avoid;
}

p { margin: 0 0 3mm 0; }

strong { color: #1A2B4C; font-weight: 700; }

/* Blockquotes */
blockquote {
    border-left: 4px solid #00A651;
    background: #F0FDF4;
    padding: 4mm 6mm;
    margin: 4mm 0;
    color: #1F2937;
    font-size: 9pt;
    page-break-inside: avoid;
}
blockquote p:last-child { margin-bottom: 0; }

/* Tables — allow long tables to break, but keep rows intact and repeat headers */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 4mm 0;
    font-size: 8.5pt;
    page-break-inside: auto;
}
thead { display: table-header-group; }
tbody { display: table-row-group; }
tr { page-break-inside: avoid; page-break-after: auto; }

th {
    background: #1A2B4C;
    color: white;
    padding: 2.5mm 3mm;
    text-align: left;
    font-weight: 600;
    font-size: 8.5pt;
    border: 1px solid #1A2B4C;
}
td {
    padding: 2mm 3mm;
    border: 1px solid #E5E7EB;
    vertical-align: top;
}
tbody tr:nth-child(even) td { background: #F9FAFB; }

/* Task list (pymdownx.tasklist with custom_checkbox) */
.task-list { list-style: none; padding-left: 4mm; }
.task-list-item { list-style: none; margin: 1.2mm 0; padding-left: 0; }
.task-list-item input[type="checkbox"],
.task-list-item-checkbox {
    appearance: none;
    -webkit-appearance: none;
    display: inline-block;
    width: 3mm;
    height: 3mm;
    margin-right: 2.5mm;
    border: 1.2pt solid #1A2B4C;
    background: white;
    vertical-align: -0.5mm;
    border-radius: 1px;
}
.task-list-item input[type="checkbox"]:checked,
.task-list-item-checkbox.checked {
    background: #00A651;
    border-color: #00A651;
}

/* Code */
code {
    background: #F3F4F6;
    padding: 0.5mm 1.5mm;
    border-radius: 2px;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 8pt;
    color: #DC2626;
}
pre {
    background: #F3F4F6;
    border-left: 3px solid #1A2B4C;
    padding: 3mm 4mm;
    overflow-x: auto;
    page-break-inside: avoid;
    font-size: 8pt;
    line-height: 1.4;
}
pre code { background: transparent; color: #1F2937; padding: 0; font-size: 8pt; }

/* Lists */
ul, ol { margin: 2mm 0 3mm 0; padding-left: 6mm; }
li { margin: 1mm 0; }

/* Links */
a { color: #00A651; text-decoration: none; }
a:hover { text-decoration: underline; }

/* hr */
hr {
    border: none;
    border-top: 1px solid #E5E7EB;
    margin: 8mm 0;
}

/* Emoji + heading visual fix */
h1, h2, h3, h4 { font-feature-settings: "liga", "calt"; }

/* Section breaks for major chapters */
h1 { page-break-before: auto; }
"""


def build_toc(html: str) -> str:
    """Extract h1/h2 from rendered HTML to build a TOC."""
    headings = re.findall(r"<h([12])[^>]*>(.*?)</h[12]>", html)
    if not headings:
        return "<p><em>(sumário será gerado quando o conteúdo for renderizado)</em></p>"
    out = ["<ul>"]
    in_h2 = False
    for level, txt in headings:
        clean = re.sub(r"<[^>]+>", "", txt).strip()
        if level == "1":
            if in_h2:
                out.append("</ul>")
                in_h2 = False
            out.append(f"<li>{clean}")
        else:  # h2
            if not in_h2:
                out.append("<ul>")
                in_h2 = True
            out.append(f"<li>{clean}</li>")
    if in_h2:
        out.append("</ul>")
    out.append("</li></ul>")
    return "\n".join(out)


def main():
    md_text = PLAN_PATH.read_text(encoding="utf-8")

    # Convert markdown to HTML with tables, fenced code, attr_list
    md = markdown.Markdown(
        extensions=[
            "tables",
            "fenced_code",
            "attr_list",
            "pymdownx.tilde",  # ~~strikethrough~~
            "pymdownx.tasklist",  # checkboxes
            "sane_lists",
        ],
        extension_configs={
            "pymdownx.tasklist": {"custom_checkbox": True},
        },
    )
    body_html = md.convert(md_text)

    # Build TOC from generated HTML
    toc = build_toc(body_html)

    # Compose final HTML
    full_html = HTML_TEMPLATE.format(
        date_str=date.today().strftime("%d/%m/%Y"),
        toc=toc,
        content=body_html,
    )

    # Render PDF
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=full_html).write_pdf(
        target=str(OUT_PDF),
        stylesheets=[CSS(string=CSS_STYLE)],
    )
    print(f"PDF gerado: {OUT_PDF}")
    print(f"Tamanho: {OUT_PDF.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
