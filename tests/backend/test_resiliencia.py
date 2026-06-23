"""Testes da resiliência de ingestão (spec §5.6) — sem rede/DB."""

from __future__ import annotations

import os

os.environ.setdefault("VALBOT_DB_DISABLED", "1")

import pytest

from backend.ingestion import resiliencia


def test_retry_sucede_apos_falhas():
    estado = {"n": 0}

    def fn():
        estado["n"] += 1
        if estado["n"] < 3:
            raise RuntimeError("falha transitória")
        return "ok"

    assert resiliencia.com_retry(fn, max_retries=3, base_delay=0) == "ok"
    assert estado["n"] == 3


def test_retry_relanca_apos_esgotar():
    def fn():
        raise RuntimeError("sempre falha")

    with pytest.raises(RuntimeError):
        resiliencia.com_retry(fn, max_retries=2, base_delay=0)


def test_alertar_sem_webhook_nao_levanta():
    # Sem VALBOT_ALERTA_WEBHOOK configurado → vai para log, não levanta.
    resiliencia.alertar("teste", {"x": 1})


def test_dlq_sem_db_nao_persiste_mas_alerta():
    # DB desabilitado → não persiste (False), mas o alerta é emitido sem levantar.
    ok = resiliencia.enviar_para_dlq(
        hash_="abc", payload={"url": "x"}, erro="vídeo inacessível", tipo_falha="erro_acesso"
    )
    assert ok is False
