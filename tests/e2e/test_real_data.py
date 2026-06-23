"""
test_real_data.py — valida que as telas exibem DADOS REAIS de prod, não mocks.

Critérios de "real":
  Regras       → 30 infrações (mock tinha 7); slug "1020/2025" do backend
  Relatórios   → IDs são hashes hex de 32 chars (mock era "LAU-DEMO-XXXX")
  Dashboard    → KPI 'Exames processados' > 0 e ≠ "—"
  Auditoria    → amostras com IDs hex (não EX-2026-XXXX do mock)
  Vídeos       → backend reporta ≥1 vídeo com has_pdf=true
  PDF endpoint → /api/laudo/{hash}/pdf retorna application/pdf real
"""

from __future__ import annotations

import os
import re
import sys

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "https://valbot.com.br").rstrip("/")
SPA_URL = BASE_URL + os.environ.get("SPA_PATH", "/")
HEADLESS = os.environ.get("HEADLESS", "1") != "0"

G = "\033[32m"
R = "\033[31m"
Y = "\033[33m"
C = "\033[36m"
B = "\033[1m"
X = "\033[0m"
HASH_RE = re.compile(r"^[a-f0-9]{32}$", re.I)


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, msg: str) -> None:
        results.append((name, ok, msg))
        sym = f"{G}✓{X}" if ok else f"{R}✗{X}"
        print(f"  {sym} {name} — {msg}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(20000)

        # Login
        page.goto(SPA_URL)
        page.evaluate("localStorage.clear(); sessionStorage.clear()")
        page.reload(wait_until="networkidle")
        page.wait_for_function(
            "() => !document.body.innerText.toLowerCase().includes('validando sess')"
        )
        page.locator("button:has-text('Auditor (Admin)')").click()
        page.locator("button:has-text('Acessar Painel')").click()
        page.wait_for_selector("button[title='Trocar usuário']", timeout=20000)

        # ─── 1. Regras → backend real (30 infrações) ───
        print(f"\n{C}{B}▶ Regras — rubrica real do backend{X}")
        page.locator("a:has-text('Regras'), button:has-text('Regras')").first.click()
        page.wait_for_selector("text=Rubrica de infrações", timeout=20000)
        page.wait_for_timeout(1500)  # rubrica é 32KB, render levou tempo
        total_text = page.locator("text=/\\d+ infrações/").first.inner_text()
        m = re.search(r"(\d+)", total_text)
        n = int(m.group(1)) if m else 0
        add("Rubrica total >= 25", n >= 25, f"backend reporta {n} infrações (mock tinha 7)")

        # ─── 2. Relatórios → IDs são hashes hex (não LAU-DEMO) ───
        print(f"\n{C}{B}▶ Relatórios — IDs hex de hashes reais{X}")
        page.locator("a:has-text('Relatórios'), button:has-text('Relatórios')").first.click()
        page.wait_for_selector("text=Relatórios emitidos", timeout=20000)
        page.wait_for_timeout(1500)
        laudo_ids = page.evaluate("""() => {
            const rows = [...document.querySelectorAll('button')];
            return rows
                .map(r => {
                    const m = r.querySelector('span.font-mono');
                    return m ? m.textContent : null;
                })
                .filter(x => x && x.length >= 20);
        }""")
        hex_ids = [i for i in laudo_ids if HASH_RE.match(i or "")]
        demo_ids = [i for i in laudo_ids if i and "LAU-DEMO" in i]
        add(
            "Laudos com ID hex (não LAU-DEMO)",
            len(hex_ids) >= 5 and len(demo_ids) == 0,
            f"hex={len(hex_ids)} demo={len(demo_ids)} (esperava hex>=5, demo=0)",
        )

        # ─── 3. Relatórios → pdf_url aponta para /api/laudo/{hash}/pdf real ───
        # Pega o primeiro laudo, abre, valida que botão "Baixar PDF" tem hash real
        if hex_ids:
            print(f"\n{C}{B}▶ Relatórios → PDF binário do backend{X}")
            first_hash = hex_ids[0]
            # Selecionar o laudo
            page.locator(f"span.font-mono:has-text('{first_hash[:8]}')").first.click(timeout=5000)
            page.wait_for_timeout(500)
            # Validar PDF via fetch direto
            pdf_info = page.evaluate(
                """async (hash) => {
                    const url = `/api/laudo/${hash}/pdf`;
                    const r = await fetch(url, { credentials: 'include' });
                    const ab = await r.arrayBuffer();
                    return {
                        status: r.status,
                        contentType: r.headers.get('content-type') || '',
                        size: ab.byteLength,
                    };
                }""",
                first_hash,
            )
            add(
                "PDF real do laudo",
                pdf_info["status"] == 200
                and "pdf" in pdf_info["contentType"].lower()
                and pdf_info["size"] > 5000,
                f"HTTP {pdf_info['status']}, ct={pdf_info['contentType']}, {pdf_info['size']} bytes",
            )

        # ─── 4. Dashboard → KPIs derivados de /api/videos ───
        print(f"\n{C}{B}▶ Dashboard — KPIs derivados de /api/videos{X}")
        page.locator("a:has-text('Dashboard'), button:has-text('Dashboard')").first.click()
        page.wait_for_selector("text=Painel executivo", timeout=20000)
        page.wait_for_timeout(1200)
        processados_kpi = page.evaluate("""() => {
            const cards = [...document.querySelectorAll('p')];
            for (const c of cards) {
                if (c.textContent.toLowerCase().includes('exames processados')) {
                    const card = c.closest('.relative');
                    const h3 = card?.querySelector('h3');
                    return h3 ? h3.textContent.trim() : null;
                }
            }
            return null;
        }""")
        is_real = bool(processados_kpi and processados_kpi != "—" and processados_kpi != "187")
        add(
            "KPI 'Exames processados' tem valor real",
            is_real,
            f"valor={processados_kpi!r} (mock era 187, '—' = sem dados)",
        )

        # ─── 5. Auditoria → amostras com hashes reais ───
        print(f"\n{C}{B}▶ Auditoria — amostras com IDs reais{X}")
        page.locator("a:has-text('Auditoria'), button:has-text('Auditoria')").first.click()
        page.wait_for_selector("text=Auditoria & calibração", timeout=20000)
        page.wait_for_timeout(1200)
        sample_ids = page.evaluate("""() => {
            return [...document.querySelectorAll('td')]
                .filter(td => td.classList.contains('font-mono'))
                .map(td => td.textContent.trim())
                .filter(x => x.length > 10);
        }""")
        hex_samples = [i for i in sample_ids if HASH_RE.match(i.lower())]
        mock_samples = [i for i in sample_ids if i.startswith("EX-2026-")]
        add(
            "Amostras de auditoria são hashes reais",
            len(hex_samples) >= 1 and len(mock_samples) == 0,
            f"hex={len(hex_samples)} mock={len(mock_samples)}",
        )

        # ─── 6. Vídeos → cards reais com botão PDF ───
        print(f"\n{C}{B}▶ Vídeos — backend real reporta vídeos com PDF{X}")
        videos_info = page.evaluate("""async () => {
            const r = await fetch('/api/videos', { credentials: 'include' });
            const arr = await r.json();
            return {
                total: arr.length,
                with_pdf: arr.filter(v => v.has_pdf).length,
                with_result: arr.filter(v => v.has_result).length,
                sample_hash: arr[0]?.hash,
            };
        }""")
        add(
            "/api/videos retorna ≥10 com has_pdf",
            videos_info["with_pdf"] >= 10,
            f"total={videos_info['total']} pdf={videos_info['with_pdf']} result={videos_info['with_result']}",
        )

        ctx.close()
        browser.close()

    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print()
    print(f"{B}{'═' * 64}{X}")
    print(f"  {G}PASS: {passed}{X}   {R}FAIL: {failed}{X}   total: {len(results)}")
    print(f"{B}{'═' * 64}{X}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
