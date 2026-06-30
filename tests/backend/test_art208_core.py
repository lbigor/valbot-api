"""Testes unitários do detector de 208 — MOCKADOS (rodam no CI, sem Vertex)."""

from __future__ import annotations

import json

import pytest

from backend.detectors.art208 import core, detectar_208, prompts


def _resp(payload_text: str, pin: int = 1000, pout: int = 20) -> dict:
    return {
        "candidates": [{"content": {"parts": [{"text": payload_text}]}}],
        "usageMetadata": {"promptTokenCount": pin, "candidatesTokenCount": pout},
    }


# ---------------- funções puras ----------------
@pytest.mark.parametrize(
    "txt,esperado",
    [("1:23", 83), ("0:05", 5), ("1:02:03", 3723), (90, 90), ("12:00", 720), ("lixo", None)],
)
def test_parse_mmss(txt, esperado):
    assert core.parse_mmss(txt) == esperado


def test_fmt_e_janela_offsets():
    assert core.fmt_offset(12) == "12s"
    assert core.fmt_offset(-3) == "0s"
    assert core.janela_offsets(30, 5) == ("25s", "35s")
    assert core.janela_offsets(2, 5) == ("0s", "7s")  # clamp em 0
    assert core.janela_offsets(100, 5, dur_total=102) == ("95s", "102s")  # teto


def test_montar_payload_estrutura():
    p = core.montar_payload("gs://b/v.mp4", "PROMPT", fps=5, start_offset="25s", end_offset="35s")
    parte = p["contents"][0]["parts"][0]
    vm = parte["videoMetadata"]
    assert vm["fps"] == 5 and vm["startOffset"] == "25s" and vm["endOffset"] == "35s"
    assert parte["fileData"]["fileUri"] == "gs://b/v.mp4"
    assert p["generationConfig"]["temperature"] == 0


def test_parse_candidatos_e_veredito():
    r1 = _resp(json.dumps({"candidatos": [{"ts": "1:10", "tipo": "semaforo"}, {"ts": "x"}]}))
    cands = core.parse_candidatos(r1)
    assert len(cands) == 1 and cands[0]["ts_seg"] == 70  # 'x' descartado
    r2 = _resp(json.dumps({"houve_208": True, "confianca": 0.9, "evidencia_visual": "vermelho"}))
    v = core.parse_veredito_janela(r2)
    assert v["houve_208"] is True and v["confianca"] == 0.9


def test_agregar_janelas():
    pos = {"houve_208": True, "confianca": 0.9, "ts_seg": 10}
    neg = {"houve_208": False, "confianca": 0.0, "ts_seg": 20}
    houve, ev = core.agregar_janelas([neg, pos])
    assert houve is True and len(ev) == 1
    assert core.agregar_janelas([neg, neg])[0] is False
    # limiar de confiança filtra
    assert (
        core.agregar_janelas([{"houve_208": True, "confianca": 0.3}], limiar_confianca=0.5)[0]
        is False
    )


def test_custo_da_resposta():
    c = core.custo_da_resposta(_resp("{}", pin=1_000_000, pout=0), "gemini-2.5-pro")
    assert c["usd"] == pytest.approx(1.25)  # 1M tokens in * $1.25/1M


# ---------------- orquestração ponta-a-ponta (call_fn FAKE, sem rede) ----------------
def _fake_call_factory(houve_na_janela: bool):
    def fake(payload: dict) -> dict:
        texto_prompt = payload["contents"][0]["parts"][1]["text"]
        if "LOCALIZE" in texto_prompt or "candidatos" in texto_prompt:
            return _resp(json.dumps({"candidatos": [{"ts": "0:30", "tipo": "semaforo"}]}))
        return _resp(
            json.dumps({"houve_208": houve_na_janela, "confianca": 0.9, "evidencia_visual": "x"})
        )

    return fake


def test_detectar_208_positivo():
    r = detectar_208("gs://b/v.mp4", call_fn=_fake_call_factory(True))
    assert r.houve_208 is True
    assert r.n_candidatos == 1
    assert r.versao == prompts.DETECTOR_208_VERSION
    assert r.custo_usd > 0  # somou estágio1 + estágio2


def test_detectar_208_negativo():
    r = detectar_208("gs://b/v.mp4", call_fn=_fake_call_factory(False))
    assert r.houve_208 is False
