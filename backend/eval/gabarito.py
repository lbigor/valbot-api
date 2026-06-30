"""Ground-truth (gabarito) a partir de ``exams.training_annotations``.

O TechPrático/examinador devolve a lista de faltas oficiais em
``training_annotations`` (JSONB: lista de ``{"anotacoes": "...Art. 208...", "timestamp": "..."}``).
Estas funções são PURAS — extraem os artigos CTB e flags de conduta a partir
dessa lista, servindo de verdade para a avaliação do detector. Ground-truth é
responsabilidade do HARNESS, não do detector.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_ART_RE = re.compile(r"art\.?\s*(\d+)", re.IGNORECASE)

# Termos que indicam reprovação por CONDUTA/eliminatória subjetiva (interrupção
# do exame) — que a IA de visão NÃO pontua por design (vão p/ revisão humana).
_CONDUTA_TERMOS = (
    "interromper o exame",
    "impericia recorrente",
    "impericia reiterada",
    "instabilidade emocional",
    "incapacidade tecnica",
    "comportamento incompat",
)


def _norm(texto: str) -> str:
    """minúsculas sem acento, p/ casar os termos de conduta de forma robusta."""
    nfkd = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn").lower()


def _textos(annotations) -> list[str]:
    if not annotations:
        return []
    out = []
    for a in annotations:
        t = (a.get("anotacoes") or a.get("anotacao") or "") if isinstance(a, dict) else str(a)
        if t:
            out.append(t)
    return out


def extrair_artigos(annotations) -> frozenset[int]:
    """Conjunto dos números de artigo CTB citados nas anotações oficiais."""
    arts: set[int] = set()
    for t in _textos(annotations):
        for m in _ART_RE.finditer(t):
            arts.add(int(m.group(1)))
    return frozenset(arts)


def tem_artigo(annotations, numero: int) -> bool:
    return numero in extrair_artigos(annotations)


def tem_208(annotations) -> bool:
    return tem_artigo(annotations, 208)


def flags_conduta(annotations) -> dict:
    """Quais sinais de conduta/eliminatória subjetiva aparecem (não-pontuáveis)."""
    blob = _norm(" || ".join(_textos(annotations)))
    achados = [t for t in _CONDUTA_TERMOS if t in blob]
    return {"tem_conduta": bool(achados), "termos": achados}


@dataclass(frozen=True)
class Gabarito:
    artigos: frozenset[int] = field(default_factory=frozenset)
    tem_conduta: bool = False

    def tem(self, numero: int) -> bool:
        return numero in self.artigos


def from_annotations(annotations) -> Gabarito:
    return Gabarito(
        artigos=extrair_artigos(annotations),
        tem_conduta=flags_conduta(annotations)["tem_conduta"],
    )
