"""Runner OPT-IN da avaliação do detector de 208 contra o gabarito.

Herdeiro versionado dos scripts efêmeros de /opt/valbot/storage/ab_harness/*.py.
NÃO roda no CI (chama Vertex, custa $$). Rodar na VM (tem ADC):

    VALBOT_RUN_VERTEX=1 python -m backend.eval.cli --ids id1,id2 [--max-candidatos 5]
    VALBOT_RUN_VERTEX=1 python -m backend.eval.cli --fn-208 2026-06-23 --limit 12
"""

from __future__ import annotations

import argparse
import json

from backend.detectors.art208 import detectar_208
from backend.eval import cases as _cases
from backend.eval import gabarito as _gab
from backend.eval import metrics as _metrics


def avaliar(case_records, **det_kwargs) -> dict:
    """Roda o detector em cada caso e compara com o gabarito. Devolve report."""
    resultados = []
    for cr in case_records:
        gab_208 = _gab.tem_208(cr.training_annotations)
        item = {"exam_id": cr.exam_id, "gab": gab_208}
        try:
            res = detectar_208(cr.gs_uri, **det_kwargs)
            item["pred"] = res.houve_208
            item["custo_usd"] = res.custo_usd
            item["versao"] = res.versao
            # janelas brutas (houve_208/confianca/estado_visto/evidencia/ts_seg) —
            # insumo da calibração: permite varrer o limiar pós-hoc sem re-rodar Vertex.
            item["janelas"] = res.detalhe.get("janelas", [])
        except Exception as e:  # nunca derruba o lote
            item["erro"] = f"{type(e).__name__}: {e}"
        print("CASO " + json.dumps(item, ensure_ascii=False, default=str)[:600], flush=True)
        resultados.append(item)
    return {
        "resultados": resultados,
        "metricas": _metrics.agregar_metricas(resultados),
        "sweep_limiar": _metrics.sweep_limiar(resultados),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", help="lista de exam_id separada por virgula")
    ap.add_argument("--fn-208", dest="fn208", help="data YYYY-MM-DD: casos FN de 208 do dia")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--max-candidatos", type=int, default=5)
    args = ap.parse_args()

    if args.ids:
        crs = _cases.carregar_por_ids([s.strip() for s in args.ids.split(",") if s.strip()])
    elif args.fn208:
        crs = _cases.carregar_fn_208(args.fn208, args.limit)
    else:
        raise SystemExit("informe --ids ou --fn-208")

    report = avaliar(crs, max_candidatos=args.max_candidatos)
    print("METRICAS " + json.dumps(report["metricas"], ensure_ascii=False), flush=True)
    # curva de calibração: recall×precisão por limiar de confiança (pós-hoc, sem rede)
    for ponto in report["sweep_limiar"]:
        print("SWEEP " + json.dumps(ponto, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
