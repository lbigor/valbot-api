"""Ponte entre os IDs de detecção legados (R1020-*) e o escopo canônico do MBEDV.

O Motor de Detecção (Gemini) ainda emite IDs custom ``R1020-*``. Cada um é
classificado em três categorias, validadas contra as 84 fichas do MBEDV
(``configs/references/mbedv_fichas.json``) — ver ``docs/mapa_infracoes_r1020_mbedv.md``:

  • PONTUA   — tem ficha CTB inequívoca → mapeia para ``codigo_val`` (Art. CTB) e
               pontua via Matriz.
  • A VALIDAR — correspondência plausível mas ambígua (inciso/artigo) → INERTE até
               validação por especialista (não pontua, não some — fica documentado).
  • COMPLIANCE — sem ficha pontuável no MBEDV (cinto, baliza, técnicas de exame) →
               NÃO pontua; vira COMENTÁRIO DE COMPLIANCE (tela dedicada).

⚠️ Princípio: na dúvida, NÃO pontuar. Só os PONTUA de alta confiança são ativos.
"""

from __future__ import annotations

import re

# --- PONTUA: correspondência inequívoca com ficha do MBEDV (Art. CTB) ----------
R1020_PARA_CODIGO_VAL: dict[str, str] = {
    "R1020-G-a": "VAL-CTB-208",  # desobedecer semáforo / parada obrigatória (Art. 208)
    "R1020-G-d": "VAL-CTB-186-I",  # contramão em via de duplo sentido (Art. 186, I)
    "R1020-G-g": "VAL-CTB-218-I",  # exceder a velocidade máxima (Art. 218, I)
    "R1020-GR-c": "VAL-CTB-214-I",  # não dar preferência a pedestre (Art. 214, I)
    "R1020-GR-e": "VAL-CTB-196",  # não sinalizar a manobra com antecedência (Art. 196)
    "R1020-M-e": "VAL-CTB-227",  # usar buzina indevidamente (Art. 227)
}

# --- A VALIDAR: plausível, mas ambíguo — INERTE (não usado em runtime) ----------
A_VALIDAR: dict[str, str] = {
    "R1020-G-b": "Art. 193 (avançar meio-fio ~ transitar em calçada?)",
    "R1020-G-e": "Art. 215 (avançar via preferencial ~ deixar de dar preferência?)",
    "R1020-GR-a": "Art. 195 (desobedecer sinalização da via / agente?)",
    "R1020-M-b": "Art. 220 (velocidade inadequada ~ deixar de reduzir?)",
    "R1020-M-d": "Art. 206 (conversão incorreta ~ retorno/conversão?)",
    "R1020-GR-b": "Art. 199-203 (ultrapassagem/mudança de direção — família ambígua)",
}

# --- COMPLIANCE: sem ficha pontuável no MBEDV → vira comentário de compliance ---
COMPLIANCE_SEM_FICHA: set[str] = {
    "R1020-GR-f",  # cinto de segurança (Art. 167 — ausente do anexo de fichas)
    "R1020-G-c",  # baliza em 3 tentativas (integrada ao estacionamento; sem ficha autônoma)
    "R1020-GR-d",  # porta aberta durante o percurso (sem ficha)
    "R1020-G-f",  # provocar acidente (consequência; sem ficha pontuável direta)
    "R1020-GR-g",  # perder o controle da direção (sem ficha direta)
    # Técnicas de exame (não são infração CTB):
    "R1020-M-a",  # freio de mão não livre
    "R1020-M-c",  # interromper o motor (carro morreu — §3.5 não pontua)
    "R1020-M-f",  # desengrenar em declive
    "R1020-M-g",  # partida sem cautelas
    "R1020-M-h",  # embreagem antes do freio
    "R1020-M-i",  # ponto neutro em curva
    "R1020-M-j",  # marchas incorretas
    "R1020-L-a",
    "R1020-L-b",
    "R1020-L-c",
    "R1020-L-d",
    "R1020-L-e",
    "R1020-L-f",
}


def para_codigo_val(codigo_deteccao: str | None) -> str | None:
    """Traduz um ID de detecção para o código canônico da Matriz (ou None).

    Aceita código já canônico (VAL-CTB-* / Art. *) e os R1020 da categoria PONTUA.
    IDs de compliance ou a-validar retornam None (não pontuam).
    """
    if not codigo_deteccao:
        return None
    c = codigo_deteccao.strip()
    if c.startswith("VAL-CTB-"):
        return c
    if c.startswith("Art."):
        m = re.search(r"(\d+)", c)
        return f"VAL-CTB-{m.group(1)}" if m else None
    return R1020_PARA_CODIGO_VAL.get(c)


def eh_compliance(codigo_deteccao: str | None) -> bool:
    """True se a conduta detectada é não-pontuável e deve virar comentário de compliance."""
    return bool(codigo_deteccao) and codigo_deteccao.strip() in COMPLIANCE_SEM_FICHA
