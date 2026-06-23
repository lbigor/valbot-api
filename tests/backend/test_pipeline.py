"""Teste end-to-end do pipeline sem rede/DB (VALBOT_DB_DISABLED=1).

Usa um ``result`` simulado (como o que o analyzer Gemini devolveria) e exercita
a cadeia Detecção → Normativo → Pontuação → Comparação → Laudo, validando os
dois pontos que o produto exigiu:
  • carro que morre não pontua;
  • dados oficiais ausentes viram divergência (não "sem divergência").
"""

from __future__ import annotations

import os

os.environ.setdefault("VALBOT_DB_DISABLED", "1")

from backend import pipeline
from backend.models import PayloadExame, ResultadoExame, TipoDivergencia


def _payload(**kw) -> PayloadExame:
    base = {
        "url_video": "gs://x/v.mp4",
        "candidato": {"renach": "123", "categoria_pretendida": "B"},
    }
    base.update(kw)
    return PayloadExame.model_validate(base)


def test_pipeline_carro_morto_nao_pontua_e_sem_oficial_vira_divergencia():
    # Motor calou (flag motor_morreu) sobre Art. 169 → exceção §3.5, não pontua.
    result = {
        "infracoes_detectadas": [
            {
                "id": "VAL-CTB-169",
                "descricao": "motor calou",
                "timestamp_s": 50,
                "confidence": 0.9,
                "motor_morreu": True,
            },
        ],
        "engine": {"backend": "vertex_gemini", "model": "gemini-3.1-pro-preview"},
        "video": {},
    }
    out = pipeline.processar(_payload(), hash_exame="hashA", result=result, persistir=False)

    assert out.pontuacao.pontuacao_calculada == 0
    assert out.pontuacao.resultado_calculado == ResultadoExame.APROVADO
    # sem resultado oficial → divergência por evidência insuficiente
    assert out.comparacao.tipo_divergencia == TipoDivergencia.EVIDENCIA_INSUFICIENTE
    assert out.comparacao.encaminhamento.value == "comite_de_ia"
    assert out.laudo["integridade"]["hash_relatorio"].startswith("sha256:")
    assert "veiculo_morreu_nao_pontua" in str(out.laudo["cobertura"]["excecoes_aplicadas"])


def test_pipeline_contramao_pontua_via_matriz_canonica():
    # Art. 186, I (contramão duplo sentido) = grave/4 — enquadra na Matriz MBEDV.
    result = {
        "infracoes_detectadas": [
            {
                "id": "VAL-CTB-186-I",
                "descricao": "contramão",
                "timestamp_s": 30,
                "confidence": 0.95,
            },
        ],
        "engine": {"backend": "vertex_gemini", "model": "gemini-3.1-pro-preview"},
        "video": {},
    }
    payload = _payload(
        resultado_oficial={
            "decisao": "aprovado",
            "pontuacao": 4,
            "infracoes": [{"artigo_ctb": "Art. 186, I", "natureza": "grave", "peso": 4}],
        }
    )
    out = pipeline.processar(payload, hash_exame="hashB", result=result, persistir=False)
    assert out.pontuacao.pontuacao_calculada == 4
    assert out.normativo.enquadramentos[0].artigo_ctb.startswith("Art. 186")
