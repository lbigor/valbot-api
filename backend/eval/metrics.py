"""Métricas puras de avaliação de um detector contra o gabarito.

Tudo opera sobre listas de dicts simples — testável sem rede.
"""

from __future__ import annotations


def classificar(houve_pred: bool, houve_gab: bool) -> str:
    """TP/FP/FN/TN da predição do detector vs o gabarito (verdade)."""
    if houve_gab and houve_pred:
        return "TP"
    if houve_gab and not houve_pred:
        return "FN"
    if not houve_gab and houve_pred:
        return "FP"
    return "TN"


def agregar_metricas(resultados: list[dict]) -> dict:
    """Recall, precisão, contagens e custo a partir de uma lista de resultados.

    Cada item esperado: {"pred": bool, "gab": bool, "custo_usd": float}.
    Itens com erro (sem "pred") são contados em "falhas" e ignorados nas taxas.
    """
    validos = [r for r in resultados if "pred" in r and "gab" in r]
    falhas = len(resultados) - len(validos)
    tp = fp = fn = tn = 0
    for r in validos:
        c = classificar(bool(r["pred"]), bool(r["gab"]))
        tp += c == "TP"
        fp += c == "FP"
        fn += c == "FN"
        tn += c == "TN"
    pos_reais = tp + fn  # casos onde o gabarito tem a infração
    preditos = tp + fp  # casos onde o detector marcou
    custo_total = round(sum(float(r.get("custo_usd") or 0) for r in resultados), 4)
    n = len(resultados)
    return {
        "n": n,
        "validos": len(validos),
        "falhas": falhas,
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "recall": round(tp / pos_reais, 4) if pos_reais else None,
        "precision": round(tp / preditos, 4) if preditos else None,
        "custo_total_usd": custo_total,
        "custo_medio_usd": round(custo_total / n, 4) if n else None,
    }
