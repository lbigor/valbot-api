"""Cobre o endpoint `POST /api/exams/init-upload` em ambos os shapes:

- Objeto único (compat com frontend SPA + integradores antigos).
- Array de itens (lote, novo schema com `id`/`renach`/`processo`).

Mocka GCS (`_gcs_client`) e o stream HTTP (`_stream_url_to_gcs`) — testes não
tocam rede nem GCS real. Roda com `VALBOT_DB_DISABLED=1` (sem Postgres).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# precisa setar ANTES de importar o server pra que `db._DISABLED=True`
os.environ.setdefault("VALBOT_DB_DISABLED", "1")
os.environ.setdefault("VALBOT_ADMIN_TOKEN", "test-admin")


def _stub_validate_url_video(url: str):
    """Aceita qualquer http(s) válida, rejeita 'invalid'. Retorna (ct, size)."""
    from fastapi import HTTPException

    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "url deve começar com http:// ou https://")
    if "invalid" in url or "nao-existe" in url:
        raise HTTPException(422, f"URL inacessível: simulado p/ {url}")
    return "video/mp4", 1024


def _stub_stream_url_to_gcs(url: str, blob) -> int:
    """Mock do download — devolve 'tamanho' falso, não toca rede."""
    return 1024


def _stub_validate_api_key(raw_key: str, scope: str):
    """Aceita qualquer key não vazia (auth bypassed nos testes)."""
    if not raw_key:
        return None
    return {"id": "test-key", "name": "test", "scopes": [scope]}


@pytest.fixture
def client(monkeypatch):
    """TestClient com GCS, HEAD e DB mockados. Não envia background tasks reais."""
    from tooling.api_stub import db as db_module
    from tooling.api_stub import server as srv

    monkeypatch.setattr(srv, "_validate_url_video", _stub_validate_url_video)
    monkeypatch.setattr(srv, "_stream_url_to_gcs", _stub_stream_url_to_gcs)
    monkeypatch.setattr(srv, "_gcs_client", lambda: MagicMock())
    monkeypatch.setattr(db_module, "validate_api_key", _stub_validate_api_key)
    # Não dispara worker de análise nos testes (background tasks rodam só com
    # `with TestClient(...)`, mas o `_run_analysis` faria import pesado).
    monkeypatch.setattr(srv, "_run_analysis", lambda *a, **kw: None)

    return TestClient(srv.app)


HDR = {"X-API-Key": "vbk_live_test_dummy", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# 1. Shape objeto único (compat com frontend antigo)
# ---------------------------------------------------------------------------


def test_single_object_returns_object(client):
    r = client.post(
        "/api/exams/init-upload",
        json={"url": "https://example.com/video.mp4", "renach": "SP-12345"},
        headers=HDR,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict), "Shape objeto-único deve devolver objeto, não lista"
    assert body["status"] == "uploading"
    assert body["analysis_id"]
    assert body["gs_path"].startswith("gs://")


def test_single_object_invalid_url_returns_422(client):
    r = client.post(
        "/api/exams/init-upload",
        json={"url": "https://invalid.example/v.mp4", "renach": "SP-X"},
        headers=HDR,
    )
    assert r.status_code == 422
    assert "URL inacess" in r.json()["detail"] or "inacess" in r.text.lower()


# ---------------------------------------------------------------------------
# 2. Shape em array (lote — schema novo)
# ---------------------------------------------------------------------------


def test_batch_two_valid_items_returns_array_same_order(client):
    payload = [
        {"url": "https://example.com/a.mp4", "id": 100, "renach": "SP-A", "processo": 111},
        {"url": "https://example.com/b.mp4", "id": 200, "renach": "SP-B", "processo": 222},
    ]
    r = client.post("/api/exams/init-upload", json=payload, headers=HDR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list), "Shape array deve devolver array"
    assert len(body) == 2
    # Ordem preservada
    assert body[0]["external_id"] == 100
    assert body[1]["external_id"] == 200
    assert body[0]["renach"] == "SP-A"
    assert body[1]["renach"] == "SP-B"
    # Cada item tem analysis_id único, status uploading
    assert all(it["status"] == "uploading" for it in body)
    assert body[0]["analysis_id"] != body[1]["analysis_id"]


def test_batch_partial_success_invalid_url_does_not_drop_others(client):
    payload = [
        {"url": "https://example.com/ok.mp4", "id": 1, "renach": "SP-OK"},
        {"url": "https://nao-existe.invalid/x.mp4", "id": 2, "renach": "SP-FAIL"},
        {"url": "https://example.com/ok2.mp4", "id": 3, "renach": "SP-OK2"},
    ]
    r = client.post("/api/exams/init-upload", json=payload, headers=HDR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 3
    assert body[0]["status"] == "uploading"
    assert body[0]["analysis_id"]
    assert body[1]["status"] == "error"
    assert body[1]["analysis_id"] is None
    assert "URL inacess" in body[1]["error"]
    assert body[2]["status"] == "uploading"
    assert body[2]["external_id"] == 3


def test_batch_external_id_persisted_in_response(client):
    payload = [
        {
            "url": "https://example.com/v.mp4",
            "id": 784562,
            "renach": "SP1234567890",
            "processo": 1234567890,
        }
    ]
    r = client.post("/api/exams/init-upload", json=payload, headers=HDR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body[0]["external_id"] == 784562


def test_batch_without_id_returns_external_id_null(client):
    payload = [{"url": "https://example.com/v.mp4", "renach": "SP-X"}]
    r = client.post("/api/exams/init-upload", json=payload, headers=HDR)
    assert r.status_code == 200
    assert r.json()[0]["external_id"] is None


# ---------------------------------------------------------------------------
# 3. Limites e validações
# ---------------------------------------------------------------------------


def test_batch_over_limit_returns_422(client):
    payload = [{"url": "https://example.com/v.mp4", "renach": f"SP-{i}"} for i in range(51)]
    r = client.post("/api/exams/init-upload", json=payload, headers=HDR)
    assert r.status_code == 422
    assert "50" in r.text


def test_empty_batch_returns_422(client):
    r = client.post("/api/exams/init-upload", json=[], headers=HDR)
    assert r.status_code == 422


def test_missing_api_key_returns_401(client):
    r = client.post(
        "/api/exams/init-upload",
        json={"url": "https://example.com/v.mp4", "renach": "X"},
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 401
