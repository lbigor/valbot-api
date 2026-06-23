"""Motor de Comparação e Divergência (spec §9).

Compara o resultado CALCULADO pelo Val com o resultado OFICIAL registrado pela
Comissão e classifica o caso em 1 de 5 tipos de divergência (ou sem
divergência), seguindo a precedência da spec §9.3:

    1. evidência insuficiente  → 5_evidencia_insuficiente
    2. resultado difere        → 1_resultado
    3. pontuação difere        → 2_pontuacao
    4. nº de infrações difere  → 3_infracao
    5. mesma conduta, art. CTB diferente → 4_enquadramento
    6. caso contrário          → sem_divergencia

Divergências "silenciosas" (mesmo resultado final, mas pontuação/enquadramento
diferentes) também são capturadas como subtipos — geram valor regulatório
(spec §9 nota).

Quando o resultado oficial não traz pontuação/lista de infrações (limitação da
integração atual), a comparação se restringe ao que é possível e marca os
campos indisponíveis em ``detalhes`` em vez de inventar divergência.
"""

from __future__ import annotations

from backend.models import (
    Comparacao,
    Encaminhamento,
    ResultadoExame,
    ResultadoOficial,
    ResultadoPontuacao,
    TipoDivergencia,
)


def _conjunto_artigos(infracoes) -> set[str]:
    return {(i.artigo_ctb or "").strip() for i in infracoes if (i.artigo_ctb or "").strip()}


def _campos_oficiais_ausentes(oficial: ResultadoOficial | None) -> list[str]:
    """Lista os dados oficiais que NÃO vieram do integrador.

    Regra (pedido do produto): informações do exame/aluno que hoje não são
    enviadas não podem ser tratadas como "tudo certo" — são lacunas que viram
    divergência por evidência insuficiente, indo para revisão humana.

    A lista de infrações só é cobrada quando o resultado oficial pressupõe que
    deveria existir (reprovado, ou pontuação > 0) — um aprovado limpo com
    pontuação 0 e sem infrações é coerente, não uma lacuna.
    """
    ausentes: list[str] = []
    if oficial is None or oficial.decisao in (None, ResultadoExame.NAO_AVALIADO):
        return ["resultado_oficial", "pontuacao_oficial", "infracoes_oficiais"]
    if oficial.pontuacao is None:
        ausentes.append("pontuacao_oficial")
    espera_infracoes = (
        oficial.pontuacao is None
        or (oficial.pontuacao or 0) > 0
        or oficial.decisao == ResultadoExame.REPROVADO
    )
    if not oficial.infracoes and espera_infracoes:
        ausentes.append("infracoes_oficiais")
    return ausentes


def comparar(
    calc: ResultadoPontuacao,
    oficial: ResultadoOficial | None,
    *,
    evidencia_suficiente: bool = True,
) -> Comparacao:
    detalhes: dict = {}
    ausentes = _campos_oficiais_ausentes(oficial)
    if ausentes:
        detalhes["campos_oficiais_ausentes"] = ausentes

    # Sem base oficial nenhuma: não dá para auditar → divergência por evidência
    # insuficiente (NUNCA "sem divergência"). Vai para o humano.
    if oficial is None or oficial.decisao in (None, ResultadoExame.NAO_AVALIADO):
        detalhes["motivo"] = "dados_oficiais_ausentes"
        return Comparacao(
            exame_id=calc.exame_id,
            resultado_oficial=oficial.decisao if oficial else None,
            resultado_calculado=calc.resultado_calculado,
            pontuacao_calculada=calc.pontuacao_calculada,
            tipo_divergencia=TipoDivergencia.EVIDENCIA_INSUFICIENTE,
            evidencia_suficiente=False,
            detalhes=detalhes,
            encaminhamento=Encaminhamento.COMITE_DE_IA,
        )

    res_of = oficial.decisao
    res_calc = calc.resultado_calculado
    pont_of = oficial.pontuacao
    pont_calc = calc.pontuacao_calculada

    concorda_resultado = res_of == res_calc

    pontuacao_comparavel = pont_of is not None
    concorda_pontuacao = (pont_of == pont_calc) if pontuacao_comparavel else concorda_resultado

    artigos_of = _conjunto_artigos(oficial.infracoes)
    artigos_calc = _conjunto_artigos(calc.infracoes_calculadas)
    infracoes_comparaveis = bool(oficial.infracoes)
    if infracoes_comparaveis:
        concorda_infracoes = (
            len(oficial.infracoes) == len(calc.infracoes_calculadas) and artigos_of == artigos_calc
        )
        detalhes["artigos_oficiais"] = sorted(artigos_of)
        detalhes["artigos_calculados"] = sorted(artigos_calc)
    else:
        concorda_infracoes = concorda_resultado

    subtipos: list[TipoDivergencia] = []

    # Classificação com precedência (spec §9.3). A insuficiência de evidência da
    # própria IA (áudio inaudível, vídeo ruim) tem precedência máxima.
    if not evidencia_suficiente:
        tipo = TipoDivergencia.EVIDENCIA_INSUFICIENTE
    elif not concorda_resultado:
        tipo = TipoDivergencia.RESULTADO
        if pontuacao_comparavel and not concorda_pontuacao:
            subtipos.append(TipoDivergencia.PONTUACAO)
        if infracoes_comparaveis and not concorda_infracoes:
            subtipos.append(TipoDivergencia.INFRACAO)
    elif pontuacao_comparavel and not concorda_pontuacao:
        tipo = TipoDivergencia.PONTUACAO
        if infracoes_comparaveis and not concorda_infracoes:
            subtipos.append(TipoDivergencia.INFRACAO)
    elif infracoes_comparaveis and len(oficial.infracoes) != len(calc.infracoes_calculadas):
        tipo = TipoDivergencia.INFRACAO
    elif infracoes_comparaveis and artigos_of != artigos_calc:
        tipo = TipoDivergencia.ENQUADRAMENTO
        detalhes["artigos_so_oficial"] = sorted(artigos_of - artigos_calc)
        detalhes["artigos_so_calculado"] = sorted(artigos_calc - artigos_of)
    elif ausentes:
        # Tudo que veio concorda, MAS faltam dados oficiais → não dá para
        # afirmar "sem divergência". Vira evidência insuficiente p/ o humano.
        tipo = TipoDivergencia.EVIDENCIA_INSUFICIENTE
        detalhes["motivo"] = "comparacao_incompleta_por_dados_ausentes"
    else:
        tipo = TipoDivergencia.SEM_DIVERGENCIA

    # Lacunas de dado registradas como subtipo informativo quando há outra
    # divergência principal (visibilidade no laudo/dashboard).
    if ausentes and tipo not in (
        TipoDivergencia.EVIDENCIA_INSUFICIENTE,
        TipoDivergencia.SEM_DIVERGENCIA,
    ):
        subtipos.append(TipoDivergencia.EVIDENCIA_INSUFICIENTE)

    evidencia_final = evidencia_suficiente and not ausentes
    encaminhamento = (
        Encaminhamento.ENCERRAMENTO
        if tipo == TipoDivergencia.SEM_DIVERGENCIA
        else Encaminhamento.COMITE_DE_IA
    )

    return Comparacao(
        exame_id=calc.exame_id,
        resultado_oficial=res_of,
        resultado_calculado=res_calc,
        pontuacao_oficial=pont_of,
        pontuacao_calculada=pont_calc,
        tipo_divergencia=tipo,
        subtipos_associados=subtipos,
        concorda_resultado=concorda_resultado,
        concorda_pontuacao=concorda_pontuacao,
        concorda_infracoes=concorda_infracoes,
        evidencia_suficiente=evidencia_final,
        detalhes=detalhes,
        encaminhamento=encaminhamento,
    )
