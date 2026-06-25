"""Cobre o shape e a resiliência do endpoint `GET /api/dashboard/diario`.

O endpoint agrega a v_exams_overview por dia de recebimento. Aqui validamos:

- Sem sessão → 401 (proteção dupla: middleware `internal_lockdown` +
  `Depends(require_session)`, igual aos demais dashboards do SPA).
- Com sessão + DB off (`VALBOT_DB_DISABLED=1`) → caminho resiliente:
  devolve `{"items": [], "source": "mock"}` (200, nunca estoura).
- Shape do contrato acordado entre as duas frentes (chaves e tipos).

Roda sem Postgres — `db._conn()` devolve None e o endpoint cai no fallback.
A sessão é um cookie HMAC real, assinado com `_sign_session` (mesma chave que
o middleware valida) — assim exercita as DUAS camadas de proteção de verdade.
"""

from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

# precisa setar ANTES de importar o server pra que `db._DISABLED=True`
os.environ.setdefault("VALBOT_DB_DISABLED", "1")
os.environ.setdefault("VALBOT_ADMIN_TOKEN", "test-admin")


@pytest.fixture
def srv_mod():
    from tooling.api_stub import server as srv

    return srv


@pytest.fixture
def client_no_auth(srv_mod):
    """Cliente SEM cookie de sessão — exercita o 401 do middleware."""
    return TestClient(srv_mod.app)


@pytest.fixture
def client(srv_mod):
    """Cliente com um cookie de sessão HMAC válido (admin, +1h)."""
    cookie = srv_mod._sign_session("tester@valbot", "admin", int(time.time()) + 3600)
    c = TestClient(srv_mod.app)
    c.cookies.set(srv_mod.SESSION_COOKIE, cookie)
    return c


def test_requires_session(client_no_auth):
    r = client_no_auth.get("/api/dashboard/diario")
    assert r.status_code == 401, r.text


def test_db_off_returns_mock_shape(client):
    r = client.get("/api/dashboard/diario?dias=30")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict)
    assert body["source"] == "mock"  # DB off → fallback resiliente
    assert body["items"] == []


def test_top_level_keys(client):
    body = client.get("/api/dashboard/diario").json()
    assert set(body.keys()) == {"items", "source"}
    assert isinstance(body["items"], list)
    assert body["source"] in ("db", "mock")


def test_dias_param_accepted(client):
    # `dias` é clampado em [1, 365]; qualquer valor não pode estourar.
    for d in (1, 7, 90, 365, 9999):
        r = client.get(f"/api/dashboard/diario?dias={d}")
        assert r.status_code == 200, r.text
        assert "items" in r.json()
