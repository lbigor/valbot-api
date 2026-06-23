"""Checklist Técnico do Anexo K (Bloco 10 / FR-LAU-10) — 12 itens binários.

Deriva, de forma determinística, os 12 itens do Termo de Referência do DETRAN-SE
a partir dos sinais técnicos já disponíveis no dossiê do exame (veredito do
validador, confiança do layout das câmeras, suficiência de evidência, conduta da
examinadora). Onde não há sinal automático confiável, o item fica
``requer_verificacao_humana`` — nunca se "inventa" um SIM.

Itens críticos (1, 2, 8, 9, 10): se qualquer um falha (NÃO), o laudo escala
automaticamente ao Auditor. Item 1 (biometria 1:1) depende de base DETRAN
[DIFERIDO] → sempre ``requer_verificacao_humana`` por ora.
"""

from __future__ import annotations

from backend.reporting.regras_laudo import item_critico

SIM = "sim"
NAO = "nao"
NA = "nao_aplicavel"
REQUER = "requer_verificacao_humana"

# (numero, pergunta) — ordem e texto fixos do Anexo K.
_PERGUNTAS = [
    (1, "Biometria 1:1 do candidato validada no início"),
    (2, "Gravação contínua, sem cortes, do início ao fim"),
    (3, "Candidato permaneceu no veículo até o encerramento"),
    (4, "Examinador identificado no registro do exame"),
    (5, "Faltas informadas ao candidato durante o exame"),
    (6, "Resultado (APTO/INAPTO) comunicado ao candidato"),
    (7, "Tom respeitoso e adequado da examinadora"),
    (8, "Câmeras reguladas e posicionadas corretamente"),
    (9, "Imagens nítidas e câmeras sincronizadas"),
    (10, "Áudio sem interrupção ou atraso relevante"),
    (11, "Sem queixa mecânica do veículo durante o exame"),
    (12, "Comportamento geral adequado no procedimento"),
]


def _veredito_item(numero: int, sinais: dict) -> tuple[str, str | None]:
    """Veredito + evidência opcional de um item, a partir dos sinais do dossiê."""
    conf_layout = sinais.get("layout_confianca")
    evidencia_suf = sinais.get("evidencia_suficiente")
    validator_ok = sinais.get("validator_veredito")
    conduta_inadequada = bool(sinais.get("conduta_inadequada"))
    duracao = sinais.get("duracao_s")

    if numero == 1:  # biometria 1:1 — base DETRAN [DIFERIDO]
        return REQUER, "Depende da base biométrica do DETRAN (verificação humana)."
    if numero == 2:  # gravação contínua
        if validator_ok in ("ok", "aprovado", True):
            return SIM, None
        if duracao:
            return SIM, None
        return REQUER, None
    if numero == 7:  # tom respeitoso
        return (
            (NAO, "Comentário inadequado detectado no áudio.")
            if conduta_inadequada
            else (SIM, None)
        )
    if numero in (8, 9):  # câmeras reguladas / nítidas e sincronizadas
        if isinstance(conf_layout, (int, float)):
            return (
                (SIM, None)
                if conf_layout >= 0.7
                else (NAO, f"Confiança de layout {conf_layout:.0%}.")
            )
        return REQUER, None
    if numero == 10:  # áudio sem interrupção
        if evidencia_suf is True:
            return SIM, None
        if evidencia_suf is False:
            return NAO, "Evidência de áudio insuficiente em parte do exame."
        return REQUER, None
    if numero == 12:  # comportamento geral
        return (NAO, "Conduta inadequada registrada.") if conduta_inadequada else (SIM, None)
    # Itens 3,4,5,6,11 — sem sinal automático confiável por ora.
    return REQUER, None


def montar_checklist(sinais: dict | None = None) -> dict:
    """Monta o bloco do checklist Anexo K (12 itens) a partir dos sinais.

    `sinais` aceita: ``layout_confianca`` (0..1), ``evidencia_suficiente`` (bool),
    ``validator_veredito`` (str/bool), ``conduta_inadequada`` (bool),
    ``duracao_s`` (float). Ausências viram ``requer_verificacao_humana``.
    """
    sinais = sinais or {}
    itens: list[dict] = []
    aprovados = 0
    escalou = False
    for numero, pergunta in _PERGUNTAS:
        veredito, evidencia = _veredito_item(numero, sinais)
        critico = item_critico(numero)
        if veredito == SIM:
            aprovados += 1
        if critico and veredito == NAO:
            escalou = True
        itens.append(
            {
                "numero": numero,
                "pergunta": pergunta,
                "veredito": veredito,
                "critico": critico,
                "evidencia": evidencia,
            }
        )
    return {
        "itens": itens,
        "aprovados": aprovados,
        "total": len(_PERGUNTAS),
        "escalou_auditor": escalou,
        "indicador": f"{aprovados} de {len(_PERGUNTAS)}",
    }
