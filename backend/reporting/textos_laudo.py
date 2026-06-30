"""Textos determinísticos do Laudo v2.0 — frases-template + slots de dados.

Num laudo OFICIAL do DETRAN os textos não podem ser prosa gerada livremente pela
IA (variaria entre execuções e seria indefensável em recurso). Aqui cada texto é
uma frase-MODELO fixa, escolhida pelo tipo de divergência e preenchida com dados
estruturados já calculados pelos motores. A mesma entrada produz o mesmo texto,
sempre — é o que torna o documento auditável (constitution §III/§VII).

Versão do catálogo de frases (carimbada no rodapé/integridade do laudo).
"""

from __future__ import annotations

CATALOGO_TEXTOS_VERSAO = "textos-laudo-v1.0"


def _fmt_pts(valor: int | float | None) -> str:
    if valor is None:
        return "não informada"
    n = int(valor)
    return f"{n} ponto" if n == 1 else f"{n} pontos"


def _join_artigos(artigos: list[str] | None) -> str:
    arts = [a for a in (artigos or []) if a]
    if not arts:
        return "—"
    if len(arts) == 1:
        return arts[0]
    return ", ".join(arts[:-1]) + " e " + arts[-1]


def veredito_agregado(
    *,
    tipo_divergencia: str | None,
    concorda_resultado: bool,
    resultado_oficial: str | None,
    resultado_calculado: str | None,
    artigos_oficiais: list[str] | None = None,
    artigos_calculados: list[str] | None = None,
) -> str:
    """Parágrafo do Sumário Executivo (Bloco 2). Frase fixa por tipo."""
    oficial = (resultado_oficial or "—").upper()
    calc = (resultado_calculado or "—").upper()
    if not tipo_divergencia or tipo_divergencia == "sem_divergencia":
        return (
            f"Comissão e Val Auditor concordam: {oficial}. A análise automatizada "
            f"corrobora o resultado oficial sem divergência de fundamentação."
        )
    if tipo_divergencia.startswith("1") or "resultado" in (tipo_divergencia or ""):
        return (
            f"Divergência de RESULTADO: a Comissão registrou {oficial} e o Val Auditor "
            f"calculou {calc}. Caso encaminhado para revisão humana com prioridade."
        )
    if tipo_divergencia.startswith("5") or "evidencia" in (tipo_divergencia or ""):
        return (
            "Evidência insuficiente para conclusão automatizada segura. O Val Auditor "
            "não confirma nem refuta o resultado oficial; recomenda-se revisão humana "
            "do material de exame."
        )
    # Tipos 2/3/4 — concordam no resultado, divergem na fundamentação.
    return (
        f"Comissão e Val Auditor concordam no resultado ({oficial}), mas divergem na "
        f"fundamentação: a Comissão apontou {_join_artigos(artigos_oficiais)} e o Val "
        f"Auditor identificou {_join_artigos(artigos_calculados)}. A divergência é de "
        f"enquadramento/pontuação e não altera o desfecho do exame."
    )


def justificativa_divergencia(
    *,
    tipo_divergencia: str | None,
    artigos_oficiais: list[str] | None = None,
    artigos_calculados: list[str] | None = None,
    pontuacao_oficial: int | float | None = None,
    pontuacao_calculada: int | float | None = None,
    limite: int = 10,
    tem_conduta_inadequada: bool = False,
) -> dict[str, str]:
    """Bloco 6 — justificativa técnica em 3 slots determinísticos."""
    principal = (
        f"O conjunto de infrações difere entre as fontes: Comissão "
        f"{_join_artigos(artigos_oficiais)}; Val Auditor {_join_artigos(artigos_calculados)}. "
        f"A pontuação calculada ({_fmt_pts(pontuacao_calculada)}) é confrontada com o "
        f"limite normativo de {limite} pontos (Resolução CONTRAN 1.020/2025, Art. 45)."
    )
    secundaria = (
        "A fundamentação registrada pela Comissão pode estar incompleta frente às "
        "evidências de áudio e vídeo analisadas pela plataforma."
        if not tem_conduta_inadequada
        else (
            "Há indício de conduta inadequada da examinadora no áudio do exame, o que "
            "pode ter influenciado o registro oficial. Sinal encaminhado para apuração "
            "específica, sem impacto na pontuação do candidato (constitution §V)."
        )
    )
    recomendacao = (
        "O resultado é materialmente consistente, mas a fundamentação oficial deve ser "
        "reforçada com base na ficha MBEDV correspondente, garantindo defensabilidade "
        "em eventual recurso. Decisão final permanece com a Comissão/Auditor humano."
    )
    return {
        "hipotese_principal": principal,
        "hipotese_secundaria": secundaria,
        "recomendacao": recomendacao,
    }


def observacao_tecnica_registro_oficial(
    *,
    pontuacao_tpa: int | float | None,
    limite: int = 10,
    houve_interrupcao_registrada: bool = False,
    exame_prosseguiu: bool = False,
) -> str:
    """Bloco 4 — observação técnica sobre o registro oficial."""
    partes: list[str] = []
    if houve_interrupcao_registrada and exame_prosseguiu:
        partes.append(
            "A examinadora registrou tipificação de interrupção, mas o exame prosseguiu "
            "sem registro de interrupção formal."
        )
    if pontuacao_tpa is not None:
        partes.append(
            f"A soma das anotações do TPA ({_fmt_pts(pontuacao_tpa)}) está abaixo do "
            f"limite de reprovação ({limite} pontos)."
        )
    partes.append(
        "Recomenda-se conferência da fundamentação do registro oficial frente às fichas "
        "MBEDV aplicáveis."
    )
    return " ".join(partes)


def recomendacao_encaminhamento(
    *,
    tipo_divergencia: str | None,
    tem_conduta_inadequada: bool = False,
) -> dict[str, str]:
    """Bloco 2 — razão, prioridade e SLA do encaminhamento (fluxo 4 níveis)."""
    if not tipo_divergencia or tipo_divergencia == "sem_divergencia":
        return {
            "fluxo": "ARQUIVAMENTO (sem divergência)",
            "razao": "Concordância entre Comissão e Val Auditor — arquivamento direto.",
            "prioridade": "baixa",
            "sla": "Sem ação humana requerida.",
        }
    razao = "Divergência de enquadramento/pontuação identificada pelo Val Auditor."
    prioridade = "média"
    if tem_conduta_inadequada:
        razao = (
            "Divergência de enquadramento com possível conduta inadequada da examinadora "
            "identificada no áudio."
        )
        prioridade = "alta"
    if (tipo_divergencia or "").startswith("1") or "resultado" in (tipo_divergencia or ""):
        prioridade = "alta"
    return {
        "fluxo": "COMITÊ VAL → AUDITOR → SUPERVISOR (fluxo de 4 níveis)",
        "razao": razao,
        "prioridade": prioridade,
        "sla": "Parecer do Auditor em 48h, decisão final do Supervisor em mais 24h.",
    }


def frase_excecao(*, ficha: str | None, excecao_texto: str | None, resultado: str | None) -> str:
    """Bloco 7 — frase determinística sobre a exceção analisada da ficha MBEDV.

    `resultado` ∈ {aplicada, descartada, nao_aplicavel}.
    """
    ficha_ref = ficha or "a ficha MBEDV"
    excecao = excecao_texto or "exceção prevista na ficha"
    r = (resultado or "nao_aplicavel").lower()
    if r == "aplicada":
        return (
            f"{ficha_ref} prevê {excecao}. Esta exceção foi analisada e APLICADA — a "
            f"conduta não pontua."
        )
    if r == "descartada":
        return (
            f"{ficha_ref} prevê {excecao}. Esta exceção foi analisada e DESCARTADA com "
            f"base na evidência do exame."
        )
    return f"{ficha_ref}: nenhuma exceção aplicável foi identificada para esta conduta."


def conclusao_processo(
    *,
    codigo_laudo: str,
    resultado_oficial: str | None,
    resultado_calculado: str | None,
    artigos_oficiais: list[str] | None = None,
    artigos_calculados: list[str] | None = None,
    tipo_divergencia: str | None = None,
    concorda_resultado: bool = True,
    tem_conduta_inadequada: bool = False,
    parecer_auditor: str | None = None,
    decisao_supervisor: str | None = None,
) -> list[str]:
    """Conclusão textual (narrativa) do processo — o "laudo final" conclusivo.

    Texto-MODELO determinístico, ramificado pelo tipo de divergência e pelo estado
    das etapas humanas (Auditor/Supervisor pendentes ou concluídos). Mesma entrada →
    mesmo texto (constitution §III/§VII): nenhuma prosa gerada por IA. Retorna a lista
    de parágrafos.
    """
    oficial = (resultado_oficial or "—").upper()
    calc = (resultado_calculado or "—").upper()
    art_of = _join_artigos(artigos_oficiais)
    art_va = _join_artigos(artigos_calculados)
    sem_div = (not tipo_divergencia) or tipo_divergencia == "sem_divergencia"
    div_resultado = (tipo_divergencia or "").startswith("1") or "resultado" in (tipo_divergencia or "")

    paras: list[str] = []

    # 1 — recebimento + apontamento da Comissão + análise do Val Auditor
    p1 = f"Exame {codigo_laudo} recebido para auditoria técnica. "
    p1 += f"A Comissão Examinadora registrou o resultado {oficial}"
    p1 += f", com enquadramento em {art_of}. " if art_of != "—" else ". "
    p1 += f"Em análise automatizada, o Val Auditor apurou {calc}"
    p1 += f", identificando {art_va}." if art_va != "—" else "."
    paras.append(p1.strip())

    # 2 — atuação do Comitê Val + divergência/concordância
    if sem_div:
        p2 = (
            f"O Comitê Val corroborou a apuração: a Comissão Examinadora e o Val Auditor "
            f"convergem no resultado ({oficial}), sem divergência de fundamentação."
        )
    elif div_resultado:
        p2 = (
            f"O Comitê Val identificou divergência de RESULTADO entre a Comissão ({oficial}) "
            f"e o Val Auditor ({calc}), reforçou os apontamentos do Val Auditor e manteve o "
            f"resultado apurado, gerando discordância com o apontamento do examinador."
        )
    else:
        p2 = (
            f"A Comissão Examinadora e o Val Auditor convergem no resultado ({oficial}), "
            f"divergindo na fundamentação ({art_of} × {art_va}). O Comitê Val classificou a "
            f"ocorrência como divergência de enquadramento/pontuação, reforçou os apontamentos "
            f"do Val Auditor e manteve o resultado apurado."
        )
    if tem_conduta_inadequada:
        p2 += (
            " Foi sinalizada conduta inadequada da examinadora no áudio do exame, encaminhada "
            "para apuração específica, sem impacto na pontuação do candidato."
        )
    paras.append(p2)

    # 3 — etapas humanas (Auditor → Supervisor)
    if parecer_auditor:
        p3 = f"O Auditor, após revisão dos fatos, {parecer_auditor.rstrip('. ')}. "
    else:
        p3 = "O caso segue encaminhado ao Auditor para parecer técnico (aguardando revisão humana). "
    if decisao_supervisor:
        p3 += f"{decisao_supervisor.rstrip('. ')}, com homologação da Supervisão."
    else:
        p3 += "A decisão final do Supervisor permanece pendente de homologação."
    paras.append(p3.strip())

    # 4 — conclusão baseada nas evidências
    if parecer_auditor and decisao_supervisor:
        paras.append(
            f"Baseado nas evidências técnicas reunidas e confirmado pelo Supervisor, o "
            f"candidato deve ser considerado {calc}."
        )
    else:
        paras.append(
            f"Baseado nas evidências técnicas reunidas, o Val Auditor mantém o resultado "
            f"{calc}; a decisão formal sobre o candidato fica condicionada ao parecer do "
            f"Auditor e à homologação do Supervisor, nos termos do Art. 43, §1º da Resolução "
            f"CONTRAN nº 1.020/2025."
        )
    return paras
