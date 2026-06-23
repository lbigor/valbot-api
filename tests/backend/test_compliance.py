"""Camada de Compliance (sinais não-pontuáveis) — sem DB/rede.

Valida que condutas sem ficha MBEDV (cinto) e comentários do examinador viram
comentários de compliance via pipeline, SEM somar pontos.
"""

from __future__ import annotations

import os

os.environ.setdefault("VALBOT_DB_DISABLED", "1")

from backend import pipeline
from backend.models import PayloadExame, TipoCompliance


def _payload(**kw) -> PayloadExame:
    base = {"url_video": "gs://x/v.mp4", "candidato": {"renach": "1", "categoria_pretendida": "B"}}
    base.update(kw)
    return PayloadExame.model_validate(base)


def test_cinto_vira_compliance_sem_pontuar():
    result = {
        "infracoes_detectadas": [
            {
                "id": "R1020-GR-f",
                "descricao": "candidato sem cinto",
                "timestamp_s": 20,
                "confidence": 0.95,
            },
        ],
        "engine": {"backend": "vertex_gemini", "model": "gemini-3.1-pro-preview"},
        "video": {},
    }
    out = pipeline.processar(_payload(), hash_exame="hC1", result=result, persistir=False)
    # não pontua
    assert out.pontuacao.pontuacao_calculada == 0
    # virou comentário de compliance tipo conduta_sem_ficha
    tipos = [c.tipo for c in out.compliance]
    assert TipoCompliance.CONDUTA_SEM_FICHA in tipos
    cinto = next(c for c in out.compliance if c.tipo == TipoCompliance.CONDUTA_SEM_FICHA)
    assert cinto.origem_codigo == "R1020-GR-f"
    # e aparece no laudo, separado das infrações
    assert any(c["origem_codigo"] == "R1020-GR-f" for c in out.laudo["comentarios_compliance"])


def test_observacao_conduta_candidato_vira_compliance():
    result = {
        "infracoes_detectadas": [],
        "observacoes_conduta": [
            {
                "descricao": "candidato desacatou o examinador",
                "classificacao": "desacato",
                "ts_seconds": 90,
            },
        ],
        "engine": {"backend": "vertex_gemini", "model": "gemini-3.1-pro-preview"},
        "video": {},
    }
    out = pipeline.processar(_payload(), hash_exame="hC2", result=result, persistir=False)
    assert any(c.tipo == TipoCompliance.CONDUTA_CANDIDATO for c in out.compliance)
    assert out.pontuacao.pontuacao_calculada == 0
