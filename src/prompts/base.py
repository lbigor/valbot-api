"""
Sistema base de prompts VALBOT — um prompt por infração.

Filosofia:
  - Um prompt = uma infração
  - Envia APENAS a imagem da câmera relevante (640×360)
  - Saída JSON estrita com 4 campos
  - Eventos temporais enviam sequência de 3-5 frames
"""

from dataclasses import dataclass
from enum import StrEnum


class CameraQuad(StrEnum):
    FRONTAL = "TL"
    LATERAL_DIREITA = "TR"
    INTERNA = "BL"
    TRASEIRA_ESQ = "BR"


@dataclass
class PromptInfracao:
    infracao_id: str
    nome: str
    assertividade_esperada: float
    camera: CameraQuad
    frames_needed: int
    frames_spacing_s: float
    system_prompt: str
    user_prompt_template: str
    expected_json_schema: dict


BASE_SCHEMA = {
    "type": "object",
    "required": ["detected", "confidence", "evidence"],
    "properties": {
        "detected": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence": {"type": "string", "maxLength": 500},
        "timestamp_relative_s": {"type": ["number", "null"]},
    },
}
