"""Motor Normativo (spec §7) sobre a Matriz Nacional (spec §4).

Transforma EVENTOS detectados em INFRAÇÕES enquadradas: para cada evento, busca
a regra aplicável na Matriz, filtra por categoria CNH, verifica exceções da §3.5
(``backend.engines.excecoes``) e atribui artigo CTB / ficha MBEDV / natureza /
peso.

A Matriz é carregada, em ordem de prioridade:
  1. Tabela ``exam_rules`` (DB) — versionada e editável sem retreinar a IA.
  2. Seed canônico do MBEDV (``backend.matriz.seed_mbedv``) — as 84 fichas reais
     do PDF oficial, usado quando o DB não está populado.

Cada exame registra a ``matriz_versao`` usada (rastreabilidade — spec §4.4).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.core import db
from backend.core.config import settings
from backend.engines import excecoes
from backend.matriz import correspondencia
from backend.models import (
    CategoriaCNH,
    Enquadramento,
    EventoDetectado,
    EventoNaoEnquadrado,
    Natureza,
    SaidaNormativo,
)

log = logging.getLogger("valbot.normativo")

_TODAS_CATEGORIAS = [c.value for c in CategoriaCNH]
_NATUREZAS_VALIDAS = {n.value for n in Natureza}


@dataclass(frozen=True)
class Regra:
    """Uma regra da Matriz Nacional (spec §4.2)."""

    codigo_val: str
    artigo_ctb: str
    ficha_mbedv: str
    natureza: str  # leve|media|grave|gravissima|variavel
    peso: int | None  # None quando a gravidade varia por inciso (Art. 181)
    categorias_aplicaveis: list[str]
    conduta_observavel: str
    quando_pontuar: str = ""
    quando_nao_pontuar: str = ""
    confiabilidade_deteccao: str = "media"
    requer_revisao_humana: bool = False
    versao_regra: str = "v1.0"

    @property
    def natureza_enum(self) -> Natureza | None:
        return Natureza(self.natureza) if self.natureza in _NATUREZAS_VALIDAS else None


def _regra_de_dict(r: dict) -> Regra:
    return Regra(
        codigo_val=r["codigo_val"],
        artigo_ctb=r.get("artigo_ctb") or "",
        ficha_mbedv=r.get("ficha_mbedv") or "",
        natureza=r.get("natureza") or "variavel",
        peso=r.get("peso"),
        categorias_aplicaveis=r.get("categorias_aplicaveis") or _TODAS_CATEGORIAS,
        conduta_observavel=r.get("conduta_observavel") or "",
        quando_pontuar=r.get("quando_pontuar") or "",
        quando_nao_pontuar=r.get("quando_nao_pontuar") or "",
        confiabilidade_deteccao=r.get("confiabilidade_deteccao") or "media",
        requer_revisao_humana=bool(r.get("requer_revisao_humana")),
        versao_regra=r.get("versao_regra") or "v1.0",
    )


def _da_tabela() -> list[Regra]:
    rows = db.fetch_all(
        """
        SELECT codigo_val, artigo_ctb, ficha_mbedv, natureza, peso,
               categorias_aplicaveis, conduta_observavel, quando_pontuar, quando_nao_pontuar,
               confiabilidade_deteccao, requer_revisao_humana, versao_regra
        FROM exam_rules WHERE vigencia_fim IS NULL
        """
    )
    regras: list[Regra] = []
    for r in rows:
        try:
            regras.append(_regra_de_dict(r))
        except Exception as e:
            log.warning("regra ignorada (%s): %s", r.get("codigo_val"), e)
    return regras


def _seed_canonico() -> list[Regra]:
    """As 84 fichas reais do MBEDV (fonte canônica embutida)."""
    from backend.matriz import seed_mbedv

    return [_regra_de_dict(r) for r in seed_mbedv.regras_canonicas()]


@dataclass
class MatrizNacional:
    versao: str
    regras: dict[str, Regra] = field(default_factory=dict)

    @classmethod
    def carregar(cls, versao: str | None = None) -> MatrizNacional:
        versao = versao or settings.matriz_versao
        regras_lista = _da_tabela()
        origem = "exam_rules"
        if not regras_lista:
            regras_lista = _seed_canonico()
            origem = "MBEDV (seed canônico)"
        log.info("Matriz carregada de %s: %d regras (versao=%s)", origem, len(regras_lista), versao)
        return cls(versao=versao, regras={r.codigo_val: r for r in regras_lista})

    def por_codigo(self, codigo: str) -> Regra | None:
        return self.regras.get(codigo)


# ---------------------------------------------------------------------------
# Enquadramento
# ---------------------------------------------------------------------------


def enquadrar(
    eventos: list[EventoDetectado],
    *,
    exame_id: str,
    categoria: str | None,
    comentarios_examinador: list[EventoDetectado] | None = None,
    matriz: MatrizNacional | None = None,
) -> SaidaNormativo:
    """Enquadra cada evento na Matriz (spec §7.2), aplicando as exceções da §3.5.

    Eventos do examinador não pontuam o candidato. Regras de peso variável
    (Art. 181) são enquadradas mas com peso 0 + revisão humana — não pontuam
    automaticamente.
    """
    matriz = matriz or MatrizNacional.carregar()
    cat = (categoria or "").upper() or None
    comentarios_examinador = comentarios_examinador or []

    enquadrados: list[Enquadramento] = []
    nao_enquadrados: list[EventoNaoEnquadrado] = []

    for ev in eventos:
        if ev.categoria == "evento_examinador" or ev.classificacao:
            nao_enquadrados.append(
                EventoNaoEnquadrado(
                    evento_id=ev.evento_id, motivo="comentario_examinador_nao_pontua_candidato"
                )
            )
            continue

        codigo_bruto = _codigo_do_evento(ev)
        # Conduta sem ficha pontuável no MBEDV (cinto, baliza, técnicas) → não pontua;
        # o pipeline a encaminha como COMENTÁRIO DE COMPLIANCE (tela dedicada).
        if correspondencia.eh_compliance(codigo_bruto):
            nao_enquadrados.append(
                EventoNaoEnquadrado(evento_id=ev.evento_id, motivo="compliance_sem_ficha")
            )
            continue

        codigo = correspondencia.para_codigo_val(codigo_bruto)
        regra = matriz.por_codigo(codigo) if codigo else None
        if regra is None:
            nao_enquadrados.append(
                EventoNaoEnquadrado(
                    evento_id=ev.evento_id, motivo="evento_observado_sem_enquadramento"
                )
            )
            continue

        if cat and regra.categorias_aplicaveis and cat not in regra.categorias_aplicaveis:
            nao_enquadrados.append(
                EventoNaoEnquadrado(
                    evento_id=ev.evento_id, motivo=f"regra_nao_aplica_categoria_{cat}"
                )
            )
            continue

        excecao = excecoes.avaliar(ev, comentarios_examinador)
        ts = ev.timestamp_video_seg or ev.timestamp_audio_seg
        if excecao:
            enquadrados.append(
                Enquadramento(
                    evento_id=ev.evento_id,
                    enquadrado=False,
                    regra_aplicada=regra.codigo_val,
                    artigo_ctb=regra.artigo_ctb,
                    ficha_mbedv=regra.ficha_mbedv,
                    natureza=regra.natureza_enum,
                    peso=0,
                    excecao_aplicada=excecao,
                    justificativa=f"Exceção do MBEDV aplicada: {excecao}",
                    confianca_enquadramento=ev.confianca,
                    requer_revisao_humana=regra.requer_revisao_humana,
                    timestamp_s=ts,
                )
            )
            continue

        # Peso variável (Art. 181) → não pontua automático; vai p/ revisão humana.
        peso_variavel = regra.peso is None
        enquadrados.append(
            Enquadramento(
                evento_id=ev.evento_id,
                enquadrado=True,
                regra_aplicada=regra.codigo_val,
                artigo_ctb=regra.artigo_ctb,
                ficha_mbedv=regra.ficha_mbedv,
                natureza=regra.natureza_enum,
                peso=(regra.peso or 0),
                excecao_aplicada=None,
                justificativa=ev.descricao or regra.conduta_observavel,
                confianca_enquadramento=ev.confianca,
                requer_revisao_humana=(
                    regra.requer_revisao_humana
                    or regra.confiabilidade_deteccao == "baixa"
                    or peso_variavel
                ),
                timestamp_s=ts,
            )
        )

    return SaidaNormativo(
        exame_id=exame_id,
        matriz_versao=matriz.versao,
        enquadramentos=enquadrados,
        eventos_nao_enquadrados=nao_enquadrados,
    )


def _codigo_do_evento(ev: EventoDetectado) -> str | None:
    """Código bruto da regra carregado no evento pelo detector (R1020-* ou Art.*)."""
    cand = ev.contexto_adicional.get("regra_id") if ev.contexto_adicional else None
    if cand:
        return str(cand)
    if ev.evento_id and (ev.evento_id.startswith("R1020-") or ev.evento_id.startswith("Art.")):
        return ev.evento_id
    return None
