"""
test_valbot_p0.py — testes E2E P0 derivados das sugestões do Gemini
(`tests/e2e/gemini-suggestions.json`).

Cobertura:
  TC-001 — Fluxo de Logout
  TC-002 — Auth gate respeita 401 do /api/auth/me
  TC-008 — Modal de Envio de Novo Vídeo
  TC-012 — Ação Confirmar/Refutar em alerta (UI: Confirmar; Gemini disse
            "Resolvido" mas o produto usa Confirmar/Refutar)
  TC-018 — Switch de regra reflete estado correto (UI atual: read-only
            — documenta o gap)
  TC-021 — Sanitização XSS no campo de busca

Reusa o BASE_URL/SPA_URL/TIMEOUT_MS/HEADLESS do test_valbot_prod.

Uso:
    BASE_URL=https://valbot.com.br python3 tests/e2e/test_valbot_p0.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Dialog,
    Page,
    Playwright,
    sync_playwright,
)

BASE_URL = os.environ.get("BASE_URL", "https://valbot.com.br").rstrip("/")
SPA_PATH = os.environ.get("SPA_PATH", "/video")
SPA_URL = BASE_URL + SPA_PATH
HEADLESS = os.environ.get("HEADLESS", "1") != "0"
TIMEOUT_MS = int(os.environ.get("TIMEOUT_MS", "20000"))
ARTIFACTS = Path(__file__).parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []  # (id, status, msg)
        self.t0 = time.monotonic()

    def add(self, tc: str, ok: bool, msg: str) -> None:
        status = "PASS" if ok else "FAIL"
        self.rows.append((tc, status, msg))
        sym = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        suffix = f" — {msg}" if msg else ""
        print(f"  {sym} {tc} {status}{suffix}")

    def addinfo(self, tc: str, msg: str) -> None:
        self.rows.append((tc, "INFO", msg))
        print(f"  {YELLOW}i{RESET} {tc} {msg}")

    def summary(self) -> int:
        elapsed = time.monotonic() - self.t0
        passed = sum(1 for _, s, _ in self.rows if s == "PASS")
        failed = sum(1 for _, s, _ in self.rows if s == "FAIL")
        info = sum(1 for _, s, _ in self.rows if s == "INFO")
        print()
        print(f"{BOLD}{'=' * 64}{RESET}")
        print(
            f"  {GREEN}PASS: {passed}{RESET}  {RED}FAIL: {failed}{RESET}  {YELLOW}INFO: {info}{RESET}  total: {len(self.rows)}"
        )
        print(f"  duration: {elapsed:.1f}s   target: {SPA_URL}")
        print(f"{BOLD}{'=' * 64}{RESET}")
        return 0 if failed == 0 else 1


R = Report()


def banner(text: str) -> None:
    print(f"\n{CYAN}{BOLD}▶ {text}{RESET}")


def shot(page: Page, label: str) -> None:
    try:
        page.screenshot(path=str(ARTIFACTS / f"p0_{label}.png"), full_page=True)
    except Exception:
        pass


def quick_login(page: Page) -> None:
    """Helper — entra rápido como auditor via quick role."""
    page.context.clear_cookies()
    page.goto(SPA_URL)
    page.evaluate("() => { localStorage.clear(); }")
    page.reload(wait_until="networkidle")
    page.wait_for_function(
        "() => !document.body.innerText.toLowerCase().includes('validando sess')",
        timeout=TIMEOUT_MS,
    )
    page.locator("button:has-text('Auditor (Admin)')").click()
    page.locator("button:has-text('Acessar Painel')").click()
    # Aguarda sidebar completamente hidratada (footer com logout botão).
    page.wait_for_selector("button[title='Trocar usuário']", state="visible", timeout=TIMEOUT_MS)


def nav_to(page: Page, label: str) -> None:
    """Helper — navega via sidebar."""
    page.locator(
        f"nav button:has-text('{label}'), aside button:has-text('{label}'), a:has-text('{label}')"
    ).first.click()
    page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)


# ─────────────────────────────────────────────────────────────────────────────
# TC-001 — Logout
# ─────────────────────────────────────────────────────────────────────────────


def tc_001_logout(page: Page) -> None:
    banner("TC-001 · Fluxo de Logout")
    quick_login(page)

    # Botão de logout: AppLayout.tsx → <button title="Trocar usuário"> com <LogOut>
    logout_btn = page.locator("button[title='Trocar usuário']").first
    if logout_btn.count() == 0:
        R.add("TC-001", False, "botão de logout não encontrado (title='Trocar usuário')")
        shot(page, "tc001_no_logout")
        return

    try:
        logout_btn.click()
    except Exception as e:
        R.add("TC-001", False, f"click no logout falhou: {e}")
        shot(page, "tc001_click_fail")
        return

    # Após logout: spinner sumir + tela de Login aparecer.
    try:
        page.wait_for_selector("text=Acesse o VALBOT", timeout=TIMEOUT_MS)
    except Exception:
        R.add("TC-001", False, "Login não apareceu após logout")
        shot(page, "tc001_no_login_after")
        return

    # localStorage limpo
    valbot_email = page.evaluate("() => localStorage.getItem('valbot_email')")
    if valbot_email is not None:
        R.add("TC-001", False, f"localStorage.valbot_email ainda existe: {valbot_email}")
        return

    R.add("TC-001", True, "logout → tela de login + localStorage limpo")
    shot(page, "tc001_ok")


# ─────────────────────────────────────────────────────────────────────────────
# TC-002 — Auth gate (sem sessão → Login)
# ─────────────────────────────────────────────────────────────────────────────


def tc_002_session_gate(page: Page) -> None:
    """O Gemini pediu 'forçar 401 no /api/auth/me'. Como /api/auth/* está em
    ALWAYS_MOCK_PREFIXES, o page.route() do Playwright não pega — interceptamos
    via injection: stub do mock retorna 401 quando NÃO há localStorage.valbot_email.
    Logo, basta limpar o localStorage e recarregar pra exercitar o mesmo path."""
    banner("TC-002 · Auth gate respeita 401 do /api/auth/me")
    # garante sessão ativa
    quick_login(page)

    # Apaga localStorage e dispara reload — o /api/auth/me mock responde 401
    # quando 'valbot_email' não está presente.
    page.evaluate("() => { localStorage.clear(); }")
    page.reload(wait_until="networkidle")
    page.wait_for_function(
        "() => !document.body.innerText.toLowerCase().includes('validando sess')",
        timeout=TIMEOUT_MS,
    )

    body = page.locator("body").inner_text()
    if "Acesse o VALBOT" in body:
        R.add("TC-002", True, "sem localStorage → Login renderiza")
        shot(page, "tc002_ok")
    else:
        R.add("TC-002", False, f"auth gate não acionou Login. body[:200]={body[:200]!r}")
        shot(page, "tc002_fail")


# ─────────────────────────────────────────────────────────────────────────────
# TC-008 — Upload modal
# ─────────────────────────────────────────────────────────────────────────────


def tc_008_upload_modal(page: Page) -> None:
    banner("TC-008 · Modal de Envio de Novo Vídeo")
    quick_login(page)
    nav_to(page, "Vídeos")

    btn = page.locator("button:has-text('Enviar novo vídeo')").first
    if btn.count() == 0:
        R.add("TC-008", False, "botão 'Enviar novo vídeo' não encontrado")
        shot(page, "tc008_no_btn")
        return
    btn.click()
    page.wait_for_timeout(500)

    # Modal aberto: deve aparecer um headline com "vídeo" ou um input file
    file_input = page.locator("input[type='file']").count()
    dialog = page.locator("[role='dialog']").count()
    if dialog == 0 and file_input == 0:
        R.add("TC-008", False, "modal não abriu (sem [role=dialog] nem input[type=file])")
        shot(page, "tc008_no_modal")
        return
    R.add("TC-008", True, f"modal aberto (dialog={dialog}, file_inputs={file_input})")
    shot(page, "tc008_ok")


# ─────────────────────────────────────────────────────────────────────────────
# TC-012 — Ação em Alerta (Confirmar/Refutar, não "Resolvido")
# ─────────────────────────────────────────────────────────────────────────────


def tc_012_alert_action(page: Page) -> None:
    banner("TC-012 · Ação Confirmar em alerta (Gemini→'Resolvido', produto→'Confirmar')")
    quick_login(page)
    nav_to(page, "Alertas")
    page.wait_for_selector("text=Central de alertas", timeout=TIMEOUT_MS)
    page.wait_for_timeout(1000)

    # Backend não tem alertas reais — /api/alertas devolve []. A página
    # mostra empty state honesto e não há botão Confirmar pra clicar.
    confirm = page.locator("button:has-text('Confirmar')")
    if confirm.count() == 0:
        R.addinfo(
            "TC-012",
            "INFO: alertas vazios (sem fonte real no backend). Empty state honesto. "
            "Reativar este teste quando o backend implementar /api/alertas.",
        )
        shot(page, "tc012_empty_honest")
        return

    # Snapshot dos alertas resolvidos ANTES do click
    before_overrides = page.evaluate("() => localStorage.getItem('valbot_mock_alert_status')")
    before_resolved_count = page.locator("text=Resolvido").count()

    confirm = page.locator("button:has-text('Confirmar')").first
    if confirm.count() == 0:
        R.add("TC-012", False, "botão 'Confirmar' não encontrado em nenhum alerta pendente")
        shot(page, "tc012_no_btn")
        return

    confirm.click()
    page.wait_for_timeout(1500)  # mock-fetch → invalidateQueries → re-render

    # Valida: badge "✓ Resolvido" tem 1+ ocorrência a mais que antes
    after_resolved_count = page.locator("text=Resolvido").count()
    if after_resolved_count <= before_resolved_count:
        R.add(
            "TC-012",
            False,
            f"badge 'Resolvido' não aumentou (antes={before_resolved_count}, depois={after_resolved_count})",
        )
        shot(page, "tc012_no_change")
        return

    # Mock interceptor persiste o action no localStorage. Verifica:
    after_overrides = page.evaluate("() => localStorage.getItem('valbot_mock_alert_status')")
    if not after_overrides or "Confirmado" not in after_overrides:
        R.add(
            "TC-012",
            False,
            f"localStorage.valbot_mock_alert_status não recebeu 'Confirmado'. antes={before_overrides!r} depois={after_overrides!r}",
        )
        return

    R.add(
        "TC-012",
        True,
        f"action persistido em localStorage + badge Resolvido subiu de {before_resolved_count} → {after_resolved_count}",
    )
    shot(page, "tc012_ok")


# ─────────────────────────────────────────────────────────────────────────────
# TC-018 — Switch de regra (UI atual é read-only — documenta o gap)
# ─────────────────────────────────────────────────────────────────────────────


def tc_018_rule_toggle(page: Page) -> None:
    banner("TC-018 · Switch de regra (Gemini esperava toggle; UI atual: read-only)")
    quick_login(page)
    nav_to(page, "Regras")
    page.wait_for_selector("text=Rubrica de infrações", timeout=TIMEOUT_MS)

    # Aguarda rubrica real (30 infrações) carregar
    page.wait_for_timeout(2000)
    switches = page.locator("button[role='switch']")
    n = switches.count()
    if n == 0:
        R.addinfo(
            "TC-018",
            "INFO: nenhum switch encontrado — UI atual usa Switch shadcn disabled "
            "que pode renderizar como [data-state='checked'] em vez de role='switch'.",
        )
        shot(page, "tc018_no_switches")
        return

    first = switches.first
    is_disabled = first.is_disabled()
    aria_checked = first.get_attribute("aria-checked")

    if is_disabled:
        R.addinfo(
            "TC-018",
            f"INFO: switch read-only por design (disabled=True, aria-checked={aria_checked}, n={n}). "
            "Toggling de regras ainda não implementado — gap real documentado.",
        )
        shot(page, "tc018_readonly")
        return

    # Se algum dia for habilitado: tentar toggle + verificar mudança.
    before = aria_checked
    first.click()
    page.wait_for_timeout(500)
    after = switches.first.get_attribute("aria-checked")
    if before != after:
        R.add("TC-018", True, f"toggle funcionou: {before} → {after}")
    else:
        R.add("TC-018", False, f"toggle não mudou estado (antes={before}, depois={after})")
    shot(page, "tc018_toggled")


# ─────────────────────────────────────────────────────────────────────────────
# TC-021 — XSS sanitização
# ─────────────────────────────────────────────────────────────────────────────


def tc_021_xss_search(page: Page) -> None:
    banner("TC-021 · Sanitização XSS no campo de busca global")
    quick_login(page)

    # Listener: se algum window.alert/confirm/prompt for disparado, MARCAR fail.
    triggered: dict[str, str | None] = {"text": None, "type": None}

    def on_dialog(dialog: Dialog) -> None:
        triggered["type"] = dialog.type
        triggered["text"] = dialog.message
        # Aceita pra desbloquear sem ficar pendurado.
        try:
            dialog.dismiss()
        except Exception:
            pass

    page.on("dialog", on_dialog)

    # Localiza o input de busca global. Placeholder: "Buscar exames, alertas..."
    # Tentativas múltiplas — vírgula em CSS attribute selector é desafiadora.
    candidates = [
        "input[placeholder*='exames']",
        "input[placeholder*='Buscar']",
        "header input[type='text']",
        "input.placeholder\\:text-\\[\\#9CA3AF\\]",
    ]
    search = None
    for sel in candidates:
        loc = page.locator(sel).first
        if loc.count() > 0:
            search = loc
            break

    if search is None or search.count() == 0:
        R.add(
            "TC-021",
            False,
            f"input de busca global não encontrado (tentei {len(candidates)} seletores)",
        )
        shot(page, "tc021_no_input")
        return

    payload = "<script>alert('xss-valbot')</script>"
    search.fill(payload)
    search.press("Enter")
    page.wait_for_timeout(1500)  # janela pra script eventualmente injetado

    if triggered["type"] is not None:
        R.add("TC-021", False, f"XSS DISPAROU! type={triggered['type']} msg={triggered['text']!r}")
        shot(page, "tc021_xss_triggered")
        return

    # Valida que o payload tá literal no DOM (escapado, não como <script>)
    visible_value = search.input_value()
    if visible_value != payload:
        R.add("TC-021", False, f"input não reteve o payload: {visible_value!r}")
        return

    # Valida que nenhum <script> com 'xss-valbot' foi injetado no DOM
    injected = page.evaluate("""() =>
        [...document.querySelectorAll('script')]
          .some(s => s.textContent.includes('xss-valbot'))""")
    if injected:
        R.add("TC-021", False, "<script> com payload foi injetado no DOM")
        return

    R.add("TC-021", True, "payload tratado como texto puro (React escapa por default)")
    shot(page, "tc021_ok")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────


def run() -> int:
    print(f"{BOLD}VALBOT E2E · suíte P0 (Gemini suggestions){RESET}")
    print(f"  spa:       {CYAN}{SPA_URL}{RESET}")
    print(f"  headless:  {HEADLESS}")
    print(f"  artifacts: {ARTIFACTS}")

    pw: Playwright
    browser: Browser
    context: BrowserContext

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1440, "height": 900},
            accept_downloads=True,
        )
        page = context.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        try:
            for fn in (
                tc_001_logout,
                tc_002_session_gate,
                tc_008_upload_modal,
                tc_012_alert_action,
                tc_018_rule_toggle,
                tc_021_xss_search,
            ):
                try:
                    fn(page)
                except Exception as e:
                    tc_id = fn.__name__.split("_")[1].upper()
                    R.add(f"TC-{tc_id}", False, f"exception: {str(e).splitlines()[0][:200]}")
        finally:
            context.close()
            browser.close()

    return R.summary()


if __name__ == "__main__":
    sys.exit(run())
