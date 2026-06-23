#!/usr/bin/env bash
# =============================================================================
# tests/e2e/run_e2e.sh — wrapper de execução da suíte Playwright do VALBOT.
#
# Uso:
#     ./tests/e2e/run_e2e.sh                          # roda contra prod
#     BASE_URL=http://localhost:5173 ./run_e2e.sh     # contra dev local
#     HEADLESS=0 ./tests/e2e/run_e2e.sh               # com browser visível
#
# Variáveis:
#     BASE_URL    URL alvo (default https://valbot.com.br)
#     HEADLESS    0 mostra browser, 1 (default) headless
#     TIMEOUT_MS  Timeout por step em ms (default 20000)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_FILE="$SCRIPT_DIR/test_valbot_prod.py"
ARTIFACTS="$SCRIPT_DIR/artifacts"

BASE_URL="${BASE_URL:-https://valbot.com.br}"
SPA_PATH="${SPA_PATH:-/video}"
HEADLESS="${HEADLESS:-1}"
TIMEOUT_MS="${TIMEOUT_MS:-20000}"

cyan='\033[36m'; green='\033[32m'; red='\033[31m'; yellow='\033[33m'; bold='\033[1m'; reset='\033[0m'

log()  { printf "${cyan}▶${reset} %s\n" "$*"; }
ok()   { printf "${green}✓${reset} %s\n" "$*"; }
err()  { printf "${red}✗${reset} %s\n" "$*"; }
warn() { printf "${yellow}!${reset} %s\n" "$*"; }

# ----------------------------------------------------------------------------
# Pré-requisitos
# ----------------------------------------------------------------------------
log "Validando ambiente"

if ! command -v python3 >/dev/null; then
    err "python3 não encontrado"
    exit 1
fi
PY_VERSION=$(python3 --version 2>&1)
ok "$PY_VERSION"

if ! python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    err "Playwright não está instalado"
    warn "instale com: pip install playwright && python3 -m playwright install chromium"
    exit 1
fi
PW_VERSION=$(python3 -m playwright --version 2>&1 | head -1)
ok "Playwright $PW_VERSION"

# Chromium tá baixado?
if ! python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    try: p.chromium.executable_path
    except Exception as e: import sys; print(f'erro: {e}', file=sys.stderr); sys.exit(1)
" 2>/dev/null; then
    warn "Chromium não está baixado — baixando agora"
    python3 -m playwright install chromium
fi
ok "Chromium pronto"

# ----------------------------------------------------------------------------
# Smoke test do alvo (responde antes de subir browser)
# ----------------------------------------------------------------------------
log "Smoke check ${BASE_URL}${SPA_PATH}"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -L "${BASE_URL}${SPA_PATH}" --max-time 10 || echo "000")
if [[ "$HTTP" == "200" ]]; then
    ok "SPA responde HTTP 200"
else
    err "SPA respondeu HTTP $HTTP — abortando suíte"
    exit 2
fi

API_HTTP=$(curl -s -o /dev/null -w "%{http_code}" -L "$BASE_URL/api/health" --max-time 10 || echo "000")
if [[ "$API_HTTP" == "200" ]]; then
    ok "API /api/health HTTP 200"
else
    warn "API /api/health HTTP $API_HTTP — mock interceptor cobre, mas pode haver issue"
fi

# ----------------------------------------------------------------------------
# Cleanup artifacts antigos
# ----------------------------------------------------------------------------
mkdir -p "$ARTIFACTS"
rm -f "$ARTIFACTS"/*.png "$ARTIFACTS"/*.html 2>/dev/null || true

# ----------------------------------------------------------------------------
# Execução
# ----------------------------------------------------------------------------
log "Rodando suíte E2E (BASE_URL=$BASE_URL  SPA_PATH=$SPA_PATH  HEADLESS=$HEADLESS  TIMEOUT_MS=$TIMEOUT_MS)"
echo

cd "$ROOT_DIR"
EXPORTS=(BASE_URL="$BASE_URL" SPA_PATH="$SPA_PATH" HEADLESS="$HEADLESS" TIMEOUT_MS="$TIMEOUT_MS")
EXIT=0

# Suíte base (smoke + happy paths)
log "── Suíte base ──"
env "${EXPORTS[@]}" python3 "$TEST_FILE" || EXIT=$?

# Suíte P0 (Gemini-suggested, fluxos críticos)
echo
log "── Suíte P0 (Gemini suggestions) ──"
P0_FILE="$SCRIPT_DIR/test_valbot_p0.py"
if [[ -f "$P0_FILE" ]]; then
    env "${EXPORTS[@]}" python3 "$P0_FILE" || EXIT=$?
else
    warn "$P0_FILE não existe — pulando"
fi

echo
if [[ $EXIT -eq 0 ]]; then
    ok "Suíte completa — tudo verde"
else
    err "Suíte falhou (exit $EXIT)"
    warn "Screenshots em $ARTIFACTS"
    ls -1 "$ARTIFACTS" 2>/dev/null | head -20
fi

exit $EXIT
