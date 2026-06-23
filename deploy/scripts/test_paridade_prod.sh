#!/bin/bash
# =============================================================================
# Teste de paridade repo × produção — roda ANTES de qualquer cutover.
#
# Prova que o código versionado no repositório é IGUAL ao que roda em produção
# (hoje montado via customizations na VM). Compara o backend arquivo-a-arquivo e
# builda o frontend conferindo o bundle byte-a-byte contra o build de prod.
#
# Uso:  deploy/scripts/test_paridade_prod.sh
# Requer: gcloud configurado para a VM de produção, pnpm.
# =============================================================================
set -u
VM="${VALBOT_VM:-valbot-prod}"
ZONE="${VALBOT_ZONE:-us-central1-a}"
CUST="/opt/valbot-deploy/customizations"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
fail=0

ssh() { gcloud compute ssh "$VM" --zone="$ZONE" --quiet --command "$1"; }

echo "== baixando código de produção da VM =="
ssh "cd $CUST && tar czf /tmp/parity_be.tgz --exclude='*.bak*' --exclude=__pycache__ --exclude='._*' --exclude='*.pyc' --exclude=frontend-dist --exclude=node_modules ." >/dev/null
gcloud compute scp "$VM:/tmp/parity_be.tgz" "$TMP/be.tgz" --zone="$ZONE" --quiet >/dev/null
mkdir -p "$TMP/be" && tar xzf "$TMP/be.tgz" -C "$TMP/be"

echo "== paridade BACKEND (repo × prod) =="
chk() { # $1 prod  $2 repo-rel
  if [ ! -f "$REPO/$2" ]; then echo "  ✗ FALTA no repo: $2"; fail=1; return; fi
  if diff -q "$TMP/be/$1" "$REPO/$2" >/dev/null 2>&1; then echo "  ✓ $2"; else echo "  ✗ DIVERGE: $2"; fail=1; fi
}
chk server.py            tooling/api_stub/server.py
chk db.py                tooling/api_stub/db.py
chk gemini_analyzer.py   src/analysis/gemini_analyzer.py
chk layout_discovery.py  src/analysis/layout_discovery.py
chk process_pending_s3.py tooling/process_pending_s3.py
diff -rq "$TMP/be/backend" "$REPO/backend" 2>/dev/null | grep -vE '\.bak|__pycache__|\._' && fail=1 || echo "  ✓ backend/"
diff -rq "$TMP/be/presets" "$REPO/tooling/bench_demo/presets" 2>/dev/null | grep -vE '\.bak|__pycache__|\._' && fail=1 || echo "  ✓ presets/"

echo "== paridade FRONTEND (build do repo × build de prod) =="
ssh "cd $CUST/frontend-dist/public && tar czf /tmp/parity_fe.tgz assets" >/dev/null
gcloud compute scp "$VM:/tmp/parity_fe.tgz" "$TMP/fe.tgz" --zone="$ZONE" --quiet >/dev/null
mkdir -p "$TMP/fe" && tar xzf "$TMP/fe.tgz" -C "$TMP/fe"
( cd "$REPO/frontend" && pnpm install --frozen-lockfile >/dev/null 2>&1 && pnpm --filter @workspace/valbot build >/dev/null 2>&1 )
REPOJS=$(ls "$REPO/frontend/artifacts/valbot/dist/public/assets/"index-*.js 2>/dev/null | head -1)
PRODJS=$(ls "$TMP/fe/assets/"index-*.js 2>/dev/null | head -1)
if [ -n "$REPOJS" ] && [ -n "$PRODJS" ] && diff -q "$REPOJS" "$PRODJS" >/dev/null 2>&1; then
  echo "  ✓ bundle idêntico ($(wc -c < "$REPOJS") bytes)"
else
  echo "  ✗ bundle DIVERGE — repo=$(wc -c < "$REPOJS" 2>/dev/null) prod=$(wc -c < "$PRODJS" 2>/dev/null)"; fail=1
fi

rm -rf "$TMP"
echo ""
[ "$fail" = "0" ] && echo "PARIDADE TOTAL: OK — repo == produção" || { echo "PARIDADE: HÁ DIVERGÊNCIAS"; exit 1; }
