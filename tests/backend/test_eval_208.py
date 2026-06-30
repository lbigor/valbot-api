"""Testes unitários do harness de avaliação (gabarito, custo, métricas, prompts).
Tudo puro — roda no CI sem Vertex."""

from __future__ import annotations

from backend.detectors.art208 import prompts
from backend.eval import cost, gabarito, metrics


# ---------------- gabarito (training_annotations) ----------------
def test_extrair_artigos_e_208():
    anns = [
        {
            "anotacoes": "I-Faltas Gravissimas - Art. 208. Avancar o sinal vermelho do semaforo.",
            "timestamp": "1:00",
        },
        {"anotacoes": "IV- Faltas Leves - Art. 169. Dirigir sem atencao.", "timestamp": "2:00"},
    ]
    assert gabarito.extrair_artigos(anns) == frozenset({208, 169})
    assert gabarito.tem_208(anns) is True
    assert gabarito.tem_208([{"anotacoes": "Art. 196. Seta"}]) is False
    assert gabarito.extrair_artigos([]) == frozenset()
    assert gabarito.extrair_artigos(None) == frozenset()


def test_flags_conduta():
    anns = [{"anotacoes": "O Examinador podera interromper o exame por impericia recorrente."}]
    f = gabarito.flags_conduta(anns)
    assert f["tem_conduta"] is True and "interromper o exame" in f["termos"]
    assert gabarito.flags_conduta([{"anotacoes": "Art. 208"}])["tem_conduta"] is False


def test_from_annotations():
    g = gabarito.from_annotations([{"anotacoes": "Art. 208 ... instabilidade emocional"}])
    assert g.tem(208) is True and g.tem_conduta is True


# ---------------- custo ----------------
def test_compute_cost_usd():
    c = cost.compute_cost_usd("gemini-2.5-pro", 1_000_000, 100_000)
    assert c["usd"] == round(1.25 + 1.0, 6)  # 1M in*$1.25 + 100k out*$10/1M=$1
    assert c["preco_conhecido"] is True
    # modelo desconhecido cai no default (não quebra, não subestima)
    assert cost.compute_cost_usd("modelo-x", 1_000_000, 0)["usd"] == 1.25


# ---------------- métricas ----------------
def test_classificar():
    assert metrics.classificar(True, True) == "TP"
    assert metrics.classificar(False, True) == "FN"
    assert metrics.classificar(True, False) == "FP"
    assert metrics.classificar(False, False) == "TN"


def test_agregar_metricas():
    res = [
        {"pred": True, "gab": True, "custo_usd": 0.03},  # TP
        {"pred": False, "gab": True, "custo_usd": 0.03},  # FN
        {"pred": True, "gab": False, "custo_usd": 0.03},  # FP
        {"pred": False, "gab": False, "custo_usd": 0.03},  # TN
        {"erro": "x", "custo_usd": 0.01},  # falha
    ]
    m = metrics.agregar_metricas(res)
    assert m["TP"] == 1 and m["FN"] == 1 and m["FP"] == 1 and m["TN"] == 1
    assert m["falhas"] == 1 and m["validos"] == 4
    assert m["recall"] == 0.5  # TP/(TP+FN)=1/2
    assert m["precision"] == 0.5  # TP/(TP+FP)=1/2
    assert m["custo_total_usd"] == 0.13


# ---------------- calibração: sweep de limiar pós-hoc ----------------
def test_pred_no_limiar():
    janelas = [
        {"houve_208": True, "confianca": 0.6},
        {"houve_208": True, "confianca": 0.3},
        {"houve_208": False, "confianca": 0.9},
    ]
    assert metrics.pred_no_limiar(janelas, 0.0) is True  # qualquer positiva
    assert metrics.pred_no_limiar(janelas, 0.5) is True  # a de 0.6 sobrevive
    assert metrics.pred_no_limiar(janelas, 0.7) is False  # nenhuma positiva >=0.7
    assert metrics.pred_no_limiar([], 0.0) is False
    # confiança ausente -> 0.0 (não vaza positivo num limiar > 0)
    assert metrics.pred_no_limiar([{"houve_208": True}], 0.1) is False


def test_sweep_limiar_derruba_fp_sem_perder_tp():
    # FP com confiança baixa (0.4) deve cair antes do TP (confiança 0.8).
    resultados = [
        {"gab": True, "janelas": [{"houve_208": True, "confianca": 0.8}], "custo_usd": 0.02},
        {"gab": False, "janelas": [{"houve_208": True, "confianca": 0.4}], "custo_usd": 0.02},
        {"gab": False, "janelas": [{"houve_208": False, "confianca": 0.0}], "custo_usd": 0.01},
        {"erro": "x", "custo_usd": 0.01},  # ignorado no sweep (sem janelas)
    ]
    curva = metrics.sweep_limiar(resultados, [0.0, 0.5, 0.9])
    por_lim = {p["limiar"]: p for p in curva}
    assert por_lim[0.0]["TP"] == 1 and por_lim[0.0]["FP"] == 1  # baseline: 1 TP, 1 FP
    assert por_lim[0.5]["TP"] == 1 and por_lim[0.5]["FP"] == 0  # 0.5 mata o FP, mantém o TP
    assert por_lim[0.9]["TP"] == 0  # 0.9 alto demais: perde o TP também


# ---------------- prompts versionados ----------------
def test_prompts_versionados_presentes():
    assert prompts.DETECTOR_208_VERSION.count(".") == 2  # SemVer X.Y.Z
    assert "LOCALIZE" in prompts.PROMPT_ESTAGIO1_LOCALIZAR
    assert "RIGOROSO" in prompts.PROMPT_ESTAGIO2_DECIDIR
    assert "audio" in prompts.PROMPT_ESTAGIO2_DECIDIR.lower()  # proíbe áudio
