"""Motor de Evidências (spec §5).

Ponto de entrada da plataforma: captura, valida e organiza os insumos do exame.
Normaliza os dois shapes do payload de integração atual (objeto único e lote)
para o contrato canônico ``PayloadExame`` e aplica as validações da spec §5.5,
classificando falhas conforme §5.6.

Não baixa o vídeo nem chama a IA — isso é do pipeline. Aqui é validação pura,
testável sem rede.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.core.config import settings
from backend.models import (
    CODIGO_PARA_RESULTADO,
    PESO_POR_NATUREZA,
    CandidatoPayload,
    ExaminadorPayload,
    InfracaoOficial,
    Natureza,
    PayloadExame,
    ResultadoExame,
    ResultadoOficial,
    TipoExame,
)

log = logging.getLogger("valbot.evidencias")


@dataclass
class ResultadoValidacao:
    ok: bool
    erros: list[str] = field(default_factory=list)  # bloqueiam processamento
    avisos: list[str] = field(default_factory=list)  # não bloqueiam
    campos_faltantes: list[str] = field(default_factory=list)
    falha_tipo: str | None = None  # erro_acesso | hash_divergente | payload_incompleto

    def add_erro(self, msg: str, tipo: str | None = None) -> None:
        self.erros.append(msg)
        self.ok = False
        if tipo and not self.falha_tipo:
            self.falha_tipo = tipo


# ---------------------------------------------------------------------------
# Normalização dos shapes de integração → PayloadExame
# ---------------------------------------------------------------------------


def normalizar(raw: dict) -> PayloadExame:
    """Converte um item de init-upload (shape A objeto único OU shape B lote)
    no contrato canônico ``PayloadExame``.

    Aceita tanto o formato plano atual (``url``, ``renach``, ``candidato_nome``…)
    quanto um payload já estruturado conforme a spec §5.4 (``url_video``,
    ``candidato: {...}``, ``resultado_oficial: {...}``).
    """
    # Já estruturado (spec §5.4)?
    if "url_video" in raw or "resultado_oficial" in raw:
        return PayloadExame.model_validate(raw)

    candidato = CandidatoPayload(
        nome=raw.get("candidato_nome"),
        cpf_mascarado=_mascarar_cpf(raw.get("candidato_cpf")),
        categoria_pretendida=_categoria(raw.get("categoria")),
        renach=str(raw.get("renach")) if raw.get("renach") is not None else None,
        processo=str(raw.get("processo")) if raw.get("processo") is not None else None,
    )
    examinador = ExaminadorPayload(
        matricula=raw.get("examinador_matricula"),
        nome=raw.get("examinador"),
        eh_preposto=bool(raw.get("eh_preposto", False)),
    )

    resultado_oficial = _resultado_oficial(raw)

    return PayloadExame(
        exame_id=str(raw["id"]) if raw.get("id") is not None else None,
        url_video=raw.get("url") or raw.get("url_video") or "",
        hash_video=raw.get("hash_video"),
        unidade=raw.get("local") or raw.get("unidade"),
        data_hora_exame=raw.get("data_hora_exame"),
        tipo_exame=_tipo_exame(raw.get("tipo_exame")),
        candidato=candidato,
        examinador=examinador,
        resultado_oficial=resultado_oficial,
        veiculo=raw.get("veiculo"),
        auto_escola=raw.get("auto_escola"),
        rubrica=raw.get("rubrica", "1020/2025"),
        training_annotations=raw.get("training_annotations") or [],
    )


def _resultado_oficial(raw: dict) -> ResultadoOficial | None:
    """Monta o resultado oficial a partir do payload de integração.

    Hoje o integrador costuma mandar só ``resultado_exame`` (A/R/N). Quando
    vierem ``pontuacao_oficial`` e ``infracoes_oficiais``, são incorporados —
    habilitando as divergências 2/3/4 (spec §9).
    """
    cod = raw.get("resultado_exame")
    if cod is None and "pontuacao_oficial" not in raw and "infracoes_oficiais" not in raw:
        return None
    decisao = (
        CODIGO_PARA_RESULTADO.get(str(cod).upper(), ResultadoExame.NAO_AVALIADO)
        if cod
        else ResultadoExame.NAO_AVALIADO
    )
    infracoes = [
        InfracaoOficial(
            artigo_ctb=i.get("artigo_ctb") or i.get("artigo") or "",
            natureza=_natureza(i.get("natureza")),
            peso=i.get("peso"),
        )
        for i in (raw.get("infracoes_oficiais") or raw.get("infracoes") or [])
        if isinstance(i, dict) and (i.get("artigo_ctb") or i.get("artigo"))
    ]
    return ResultadoOficial(
        decisao=decisao,
        pontuacao=raw.get("pontuacao_oficial"),
        houve_interrupcao=bool(raw.get("houve_interrupcao", False)),
        motivo_interrupcao=raw.get("motivo_interrupcao"),
        infracoes=infracoes,
    )


# ---------------------------------------------------------------------------
# Validações (spec §5.5)
# ---------------------------------------------------------------------------


def validar(payload: PayloadExame, *, duracao_seg: float | None = None) -> ResultadoValidacao:
    res = ResultadoValidacao(ok=True)

    # Campos obrigatórios mínimos para processar.
    if not payload.url_video:
        res.add_erro("url_video ausente", tipo="payload_incompleto")
    if not (payload.candidato.renach or payload.exame_id):
        res.add_erro("identificador ausente (renach/exame_id)", tipo="payload_incompleto")

    # Campos da spec §5.4 que enriquecem auditoria mas não bloqueiam.
    for campo, presente in {
        "unidade": payload.unidade,
        "tipo_exame": payload.tipo_exame != TipoExame.DESCONHECIDO,
        "examinador.matricula": payload.examinador.matricula,
        "resultado_oficial": payload.resultado_oficial is not None,
    }.items():
        if not presente:
            res.campos_faltantes.append(campo)

    # Duração compatível (≥1min, ≤30min por default — spec §5.5).
    if duracao_seg is not None:
        if duracao_seg < settings.duracao_min_seg:
            res.add_erro(f"duração {duracao_seg:.0f}s < mínimo {settings.duracao_min_seg}s")
        elif duracao_seg > settings.duracao_max_seg:
            res.avisos.append(f"duração {duracao_seg:.0f}s acima de {settings.duracao_max_seg}s")

    # Coerência resultado oficial × soma das infrações apontadas (spec §5.5).
    coer = _checar_coerencia(payload.resultado_oficial)
    if coer:
        res.avisos.append(coer)

    return res


def checar_hash(esperado: str | None, calculado: str | None) -> ResultadoValidacao:
    """Validação anti-adulteração (spec §5.6): hash do vídeo deve conferir."""
    res = ResultadoValidacao(ok=True)
    if esperado and calculado and esperado.split(":")[-1] != calculado.split(":")[-1]:
        res.add_erro(
            f"hash divergente: esperado={esperado} calculado={calculado}",
            tipo="hash_divergente",
        )
    return res


def _checar_coerencia(oficial: ResultadoOficial | None) -> str | None:
    if oficial is None or oficial.pontuacao is None or not oficial.infracoes:
        return None
    soma = sum(
        (
            i.peso
            if i.peso is not None
            else (PESO_POR_NATUREZA.get(i.natureza, 0) if i.natureza else 0)
        )
        for i in oficial.infracoes
    )
    if soma != oficial.pontuacao:
        return f"pontuacao_oficial ({oficial.pontuacao}) != soma das infrações apontadas ({soma})"
    return None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _mascarar_cpf(cpf: str | None) -> str | None:
    """Mascara CPF para conformidade LGPD (spec §17.1): ***.XXX.XXX-**."""
    if not cpf:
        return None
    digitos = "".join(ch for ch in cpf if ch.isdigit())
    if len(digitos) != 11:
        return cpf if "*" in cpf else None
    return f"***.{digitos[3:6]}.{digitos[6:9]}-**"


def _categoria(v):
    from backend.models import CategoriaCNH

    if not v:
        return None
    try:
        return CategoriaCNH(str(v).upper())
    except ValueError:
        return None


def _tipo_exame(v) -> TipoExame:
    if not v:
        return TipoExame.DESCONHECIDO
    try:
        return TipoExame(str(v).lower())
    except ValueError:
        return TipoExame.DESCONHECIDO


def _natureza(v) -> Natureza | None:
    if not v:
        return None
    try:
        return Natureza(str(v).lower())
    except ValueError:
        return None
