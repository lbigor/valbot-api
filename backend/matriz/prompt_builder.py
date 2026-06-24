"""Gera o bloco de regras do prompt a PARTIR da Matriz vigente (spec §4.1).

A Matriz versionada passa a ser a fonte única que alimenta os próximos prompts
enviados ao Gemini (Motor de Detecção e Comitê). Assim, atualizar a Matriz muda
o comportamento da IA sem retreinar nada — e cada análise registra a
``matriz_versao`` usada (rastreabilidade §4.4).

Carrega as regras vigentes do banco (``exam_rules``) quando disponível; senão,
do seed canônico do MBEDV (``seed_mbedv.regras_canonicas``).
"""

from __future__ import annotations

from backend.core import db
from backend.core.config import settings
from backend.matriz import seed_mbedv


def _regras_vigentes() -> tuple[list[dict], str]:
    """Devolve (regras, matriz_versao). Banco tem prioridade sobre o seed."""
    if db.db_enabled():
        rows = db.fetch_all(
            "SELECT codigo_val, artigo_ctb, natureza, peso, categorias_aplicaveis, "
            "conduta_observavel, descricao, quando_pontuar, quando_nao_pontuar, "
            "comentario_juridico "
            "FROM exam_rules WHERE vigencia_fim IS NULL ORDER BY artigo_ctb"
        )
        ver = db.fetch_one("SELECT versao FROM matriz_versoes WHERE vigente = TRUE LIMIT 1")
        if rows:
            return rows, (ver["versao"] if ver else settings.matriz_versao)
    return seed_mbedv.regras_canonicas(), settings.matriz_versao


def _aplica_categoria(regra: dict, categoria: str | None) -> bool:
    if not categoria:
        return True
    cats = regra.get("categorias_aplicaveis") or []
    return not cats or categoria.upper() in cats


def construir_bloco(categoria: str | None = None) -> tuple[str, str]:
    """Monta o bloco textual das regras a avaliar (filtrado por categoria CNH).

    Devolve (texto_do_bloco, matriz_versao). Cada regra vira um item com artigo,
    natureza/peso, condutas que pontuam e — crítico — condutas que NÃO pontuam.
    """
    regras, versao = _regras_vigentes()
    aplicaveis = [r for r in regras if _aplica_categoria(r, categoria)]

    linhas = [
        f"MATRIZ NACIONAL DE REGRAS — versão {versao} (fonte: MBEDV/CTB).",
        "Avalie CADA artigo abaixo. Para cada um, decida se a conduta ocorreu, "
        "respeitando as exceções (condutas que NÃO pontuam).",
        "",
    ]
    for r in aplicaveis:
        peso = r.get("peso")
        peso_txt = f"{peso} pts" if peso is not None else "peso por inciso (revisão humana)"
        linhas.append(
            f"### {r.get('artigo_ctb')} — {r.get('conduta_observavel')} "
            f"[{r.get('natureza')}, {peso_txt}]"
        )
        # Descrição oficial da ficha MBEDV — contextualiza o que caracteriza a falta.
        if r.get("descricao"):
            linhas.append(f"Descrição: {str(r['descricao']).strip()}")
        if r.get("quando_pontuar"):
            linhas.append("Condutas que pontuam:")
            for c in str(r["quando_pontuar"]).split("\n"):
                if c.strip():
                    linhas.append(f"  - {c.strip()}")
        if r.get("quando_nao_pontuar"):
            linhas.append("Condutas que NÃO pontuam (descartar mesmo se parecer):")
            for c in str(r["quando_nao_pontuar"]).split("\n"):
                if c.strip():
                    linhas.append(f"  - {c.strip()}")
        # Definições e procedimentos da ficha MBEDV — COMO avaliar (ponto de
        # referência da conduta, ex.: "parada antes da faixa de retenção; veículo
        # totalmente imóvel"). Crítico p/ não gerar falso positivo de parada rolante.
        if r.get("comentario_juridico"):
            linhas.append(
                f"Como avaliar (definições e procedimentos): "
                f"{str(r['comentario_juridico']).strip()}"
            )
        linhas.append("")
    return "\n".join(linhas), versao
