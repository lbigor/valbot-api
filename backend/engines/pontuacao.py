"""Motor de Pontuação (spec §8).

Recebe os enquadramentos do Motor Normativo, soma os pesos das infrações
efetivamente enquadradas, aplica o limite de aprovação (≤10) e trata o exame
interrompido como categoria especial (spec §3.4).

Algoritmo (spec §8.2):

    pontuacao_total = Σ peso(E) para cada E enquadrado
    se houve_interrupcao:        resultado = INTERROMPIDO, pontuacao = None
    senão se total <= 10:        resultado = APROVADO
    senão:                       resultado = REPROVADO

Eventos que não pontuam (exceção do MBEDV, veículo que morre, baliza isolada)
já chegam com ``enquadrado=False`` do Motor Normativo e portanto não somam.
"""

from __future__ import annotations

from backend.models import (
    LIMITE_APROVACAO,
    InfracaoCalculada,
    ResultadoExame,
    ResultadoPontuacao,
    SaidaNormativo,
)


def calcular(
    normativo: SaidaNormativo,
    *,
    houve_interrupcao: bool = False,
    motivo_interrupcao: str | None = None,
    modelo_deteccao_versao: str = "",
) -> ResultadoPontuacao:
    infracoes: list[InfracaoCalculada] = []
    total = 0
    for enq in normativo.enquadramentos:
        if not enq.enquadrado:
            continue
        peso = enq.peso or 0
        total += peso
        infracoes.append(
            InfracaoCalculada(
                artigo_ctb=enq.artigo_ctb or (enq.regra_aplicada or "?"),
                regra_aplicada=enq.regra_aplicada,
                natureza=enq.natureza,  # type: ignore[arg-type]
                peso=peso,
                timestamp_s=enq.timestamp_s,
            )
        )

    if houve_interrupcao:
        resultado = ResultadoExame.INTERROMPIDO
        pontuacao: int | None = None
    elif total <= LIMITE_APROVACAO:
        resultado = ResultadoExame.APROVADO
        pontuacao = total
    else:
        resultado = ResultadoExame.REPROVADO
        pontuacao = total

    return ResultadoPontuacao(
        exame_id=normativo.exame_id,
        resultado_calculado=resultado,
        pontuacao_calculada=pontuacao,
        limite_reprovacao=LIMITE_APROVACAO,
        houve_interrupcao=houve_interrupcao,
        motivo_interrupcao=motivo_interrupcao,
        infracoes_calculadas=infracoes,
        matriz_versao=normativo.matriz_versao,
        modelo_deteccao_versao=modelo_deteccao_versao,
    )
