"""Segurança: API keys (integradores) e sessão assinada (portais).

Mantém o esquema já em produção: API key ``vbk_live_<hex>`` com hash SHA-256 na
tabela ``api_keys`` (migration 002) e cookie de sessão HMAC-SHA256. Funções
puras e testáveis; o acoplamento com FastAPI fica nos routers (``backend.api``).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

from backend.core import db
from backend.core.config import settings


def validate_api_key(raw_key: str, required_scope: str) -> dict | None:
    """Valida a key e o escopo contra ``api_keys``. Atualiza ``last_used_at``."""
    if not raw_key:
        return None
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    row = db.fetch_one(
        "SELECT id::text AS id, name, scopes FROM api_keys WHERE key_hash = %s AND revoked_at IS NULL",
        (key_hash,),
    )
    if not row:
        return None
    if required_scope not in (row.get("scopes") or []):
        return None
    db.execute("UPDATE api_keys SET last_used_at = NOW() WHERE id = %s", (row["id"],))
    return {"id": row["id"], "name": row["name"], "scopes": row["scopes"]}


# ---------------------------------------------------------------------------
# Sessão assinada (HMAC) — para os portais Auditor/Supervisor
# ---------------------------------------------------------------------------


def _secret() -> bytes:
    return (settings.session_secret or "dev-insecure-secret").encode()


def sign_session(email: str, role: str, ttl_seconds: int = 90 * 86400) -> str:
    payload = {"email": email, "role": role, "exp": int(time.time()) + ttl_seconds}
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(_secret(), body, hashlib.sha256).hexdigest()
    import base64

    return base64.urlsafe_b64encode(body).decode() + "." + sig


def verify_session(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    import base64

    b64, sig = token.rsplit(".", 1)
    try:
        body = base64.urlsafe_b64decode(b64.encode())
    except Exception:
        return None
    expected = hmac.new(_secret(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        payload = json.loads(body)
    except Exception:
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload


def role_for(email: str) -> str:
    """Heurística de papel a partir do e-mail (piloto — pool aberto)."""
    e = (email or "").lower()
    if "supervisor" in e:
        return "supervisor"
    if "auditor" in e or "revisor" in e:
        return "auditor"
    if "admin" in e:
        return "admin"
    return "auditor"
