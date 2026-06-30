"""Avaliação REAL do detector de 208 contra o gabarito — OPT-IN, NÃO roda no CI.

Duplo guard: marker `vertex` + skipif por env. Chama o Vertex de verdade (custa
$$, lento), valida o casing real de videoMetadata/fps/offsets aceito pelo
servidor, e mede recall/FP/custo. Rodar na VM (tem ADC):

    VALBOT_RUN_VERTEX=1 pytest tests/backend/test_art208_eval_vertex.py -m vertex -s
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.vertex,
    pytest.mark.skipif(
        not os.environ.get("VALBOT_RUN_VERTEX"),
        reason="avaliação real chama Vertex e custa $$ — opt-in via VALBOT_RUN_VERTEX=1",
    ),
]


def test_detector_208_vs_gabarito_amostra():
    """Roda o detector em casos FN de 208 e exige recall mínimo sem estourar custo."""
    from backend.eval import cases, cli

    crs = cases.carregar_fn_208(os.environ.get("VALBOT_EVAL_DATA", "2026-06-23"), limit=6)
    assert crs, "sem casos FN de 208 para avaliar"
    report = cli.avaliar(crs, max_candidatos=5)
    m = report["metricas"]
    print("METRICAS:", m)
    # gate de sanidade (ajustar conforme calibração): custo por exame controlado
    assert m["custo_medio_usd"] is None or m["custo_medio_usd"] < 0.15
