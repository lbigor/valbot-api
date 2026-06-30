"""Prompts VERSIONADOS do detector de Art. 208 (2 estágios).

REGRA (igual a DIRETRIZES_VAL): alterar o texto/critério = bump SemVer em
DETECTOR_208_VERSION e entrada em docs/PROMPT_CHANGELOG.md.
  MINOR = muda julgamento; PATCH = redação; MAJOR = remove/inverte critério.
A versão é carimbada no resultado de cada análise (rastreabilidade).
"""

from __future__ import annotations

DETECTOR_208_VERSION = "1.0.0"

# Estágio 1 — LOCALIZA (vídeo inteiro, fps baixo): só acha candidatos, não julga.
PROMPT_ESTAGIO1_LOCALIZAR = (
    "Voce audita um exame de direcao CAT B. Liste TODOS os momentos em que o "
    "veiculo se APROXIMA de um SEMAFORO ou de uma placa PARE (R-1). Para cada um, "
    "de o timestamp aproximado em mm:ss. NAO julgue infracao, apenas LOCALIZE. "
    'JSON: {"candidatos":[{"ts":"mm:ss","tipo":"semaforo|placa_pare","motivo":"..."}]}'
)

# Estágio 2 — DECIDE (janela recortada, fps alto): critério rigoroso, só visual.
PROMPT_ESTAGIO2_DECIDIR = (
    "Neste TRECHO o veiculo enfrenta um semaforo ou placa PARE. Houve Art. 208 "
    "(avancar sinal VERMELHO, ou nao fazer PARADA TOTAL na placa PARE)? Criterio "
    "RIGOROSO, SO evidencia VISUAL: (semaforo) a luz VERMELHA visivel E o veiculo "
    "cruza a faixa de retencao sem parar; (placa PARE) placa visivel E o veiculo "
    "cruza SEM imobilizar. Se houver QUALQUER frame com o veiculo imovel antes da "
    "linha, a parada e VALIDA -> NAO e infracao. NUNCA use audio nem suposicao. "
    'JSON: {"houve_208":true,"estado_visto":"vermelho/verde/placa/...",'
    '"evidencia_visual":"o que se ve","confianca":0.0}'
)

RESPONSE_SCHEMA_E1 = {
    "type": "object",
    "properties": {
        "candidatos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ts": {"type": "string"},
                    "tipo": {"type": "string"},
                    "motivo": {"type": "string"},
                },
            },
        }
    },
}

RESPONSE_SCHEMA_E2 = {
    "type": "object",
    "properties": {
        "houve_208": {"type": "boolean"},
        "estado_visto": {"type": "string"},
        "evidencia_visual": {"type": "string"},
        "confianca": {"type": "number"},
    },
}
