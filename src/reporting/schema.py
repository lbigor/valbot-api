"""Contrato tipado do dicionário consumido por src/reporting/templates/laudo.html."""

from __future__ import annotations

from typing import TypedDict


class ExameMeta(TypedDict):
    candidato: str
    cpf: str
    renach: str
    processo: str
    categoria: str
    veiculo: str
    local: str
    examinador: str
    data_exame: str


class RubricaMeta(TypedDict):
    slug: str
    nome: str
    limite_pontuacao: int
    artigo_aprovacao: str
    artigo_reprovacao: str
    pesos: dict[str, int | None]


class Contagem(TypedDict):
    gravissima: int
    grave: int
    media: int
    leve: int


class InfracaoRender(TypedDict, total=False):
    id: str
    titulo: str
    descricao: str
    descricao_longa: str
    gravidade: str
    gravidade_label: str
    pontos: int | None
    timestamp_inicio: str
    timestamp_fim: str
    duracao_fmt: str
    cameras_fmt: str
    evidencia: str
    base_legal: str
    occurrences: int


class EventoTimeline(TypedDict, total=False):
    timestamp: str
    gravidade: str
    gravidade_label: str
    descricao: str
    pct: float


class LaudoContext(TypedDict, total=False):
    laudo_id: str
    emitido_em: str
    modelo_versao: str
    rubrica: RubricaMeta
    exame: ExameMeta
    duracao_seg: float
    duracao_fmt: str
    aprovado: bool
    pontuacao_total: int
    motivo_reprovacao: str
    contagem: Contagem
    infracoes: list[InfracaoRender]
    linha_do_tempo: list[EventoTimeline]
    positivos: list[str]
    pontos_atencao: list[str]
    cobertura_pct: int
    total_itens_avaliados: int
    total_itens_v2: int
    cobertura_v1: list[str]
    itens_v2: list[str]
    video_hash: str
    result_hash: str
    analysis_version: str
