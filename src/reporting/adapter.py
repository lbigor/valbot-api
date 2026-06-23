"""Converte saída do pipeline em LaudoContext pronto pro template Jinja."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.reporting.schema import LaudoContext
from src.rubrics.taxonomia import (
    CATALOGO,
    PONTOS,
    Camera,
    Infracao,
    Rubrica,
    Severidade,
    por_id,
)

_SEV_LABEL = {
    Severidade.GRAVISSIMA: "GRAVÍSSIMA",
    Severidade.GRAVE: "GRAVE",
    Severidade.MEDIA: "MÉDIA",
    Severidade.LEVE: "LEVE",
}

_CAMERA_LABEL = {
    Camera.FRONTAL: "Frontal",
    Camera.LATERAL_DIREITA: "Lateral direita",
    Camera.INTERNA: "Interna",
    Camera.TRASEIRA_ESQ: "Traseira-esq",
    Camera.AUDIO: "Áudio",
}

_RUBRICA_NOME = {
    Rubrica.RES_1020_2025: "Res. CONTRAN 1.020/2025",
}


def _fmt_tempo(seg: float) -> str:
    m, s = divmod(int(seg), 60)
    return f"{m:02d}:{s:02d}"


def _fmt_duracao(seg: float) -> str:
    if seg < 60:
        return f"{seg:.1f}s"
    m, s = divmod(seg, 60)
    return f"{int(m)}m{int(s):02d}s"


def _rubrica_meta(rubrica: Rubrica, limite_pontuacao: int) -> dict[str, Any]:
    pesos = PONTOS[rubrica]
    return {
        "slug": rubrica.value.replace("_", "/"),
        "nome": _RUBRICA_NOME[rubrica],
        "limite_pontuacao": limite_pontuacao,
        "artigo_aprovacao": "Anexo II",
        "artigo_reprovacao": "Anexo II",
        "pesos": {
            "gravissima": pesos.get(Severidade.GRAVISSIMA),
            "grave": pesos.get(Severidade.GRAVE),
            "media": pesos.get(Severidade.MEDIA),
            "leve": pesos.get(Severidade.LEVE),
        },
    }


def _cobertura(rubrica: Rubrica) -> dict[str, Any]:
    do_catalogo = [i for i in CATALOGO if i.rubrica == rubrica]
    v1 = [i for i in do_catalogo if i.detectavel_v1]
    v2 = [i for i in do_catalogo if not i.detectavel_v1]
    total = len(do_catalogo) or 1
    return {
        "cobertura_pct": round(len(v1) / total * 100),
        "total_itens_avaliados": len(v1),
        "total_itens_v2": len(v2),
        "cobertura_v1": [i.descricao for i in v1],
        "itens_v2": [i.descricao for i in v2],
    }


def _render_infracao(deteccao: dict[str, Any], info: Infracao) -> dict[str, Any]:
    ts_ini = float(deteccao.get("timestamp_inicio", 0.0))
    duracao = float(deteccao.get("duracao_s", 0.0))
    ts_fim = ts_ini + duracao
    return {
        "id": info.id,
        "titulo": info.descricao,
        "descricao": info.descricao,
        "descricao_longa": deteccao.get("descricao_longa") or info.descricao,
        "gravidade": info.severidade.value,
        "gravidade_label": _SEV_LABEL[info.severidade],
        "pontos": info.pontos,
        "timestamp_inicio": _fmt_tempo(ts_ini),
        "timestamp_fim": _fmt_tempo(ts_fim),
        "duracao_fmt": _fmt_duracao(duracao) if duracao else "",
        "cameras_fmt": ", ".join(_CAMERA_LABEL[c] for c in info.cameras_relevantes) or "—",
        "evidencia": deteccao.get("evidencia", "—"),
        "base_legal": info.base_legal,
        "occurrences": int(deteccao.get("occurrences", 1)),
    }


def _linha_do_tempo(
    infracoes_render: list[dict[str, Any]], duracao_total: float
) -> list[dict[str, Any]]:
    eventos: list[dict[str, Any]] = []
    for inf in infracoes_render:
        m, s = inf["timestamp_inicio"].split(":")
        seg = int(m) * 60 + int(s)
        pct = (seg / duracao_total * 100) if duracao_total else 0.0
        eventos.append(
            {
                "timestamp": inf["timestamp_inicio"],
                "gravidade": inf["gravidade"],
                "gravidade_label": inf["gravidade_label"],
                "descricao": inf["descricao"],
                "pct": round(pct, 2),
            }
        )
    return eventos


def build_context(
    infracoes_detectadas: list[dict[str, Any]],
    candidato: dict[str, Any],
    metadata: dict[str, Any],
) -> LaudoContext:
    """
    infracoes_detectadas: [{id, timestamp_inicio, duracao_s, evidencia, [descricao_longa], [occurrences]}]
    candidato: ExameMeta fields (nome vira candidato; campos faltantes viram '—')
    metadata: {laudo_id, rubrica ('1020_2025'), video_hash, modelo_versao,
               [emitido_em], [result_hash], [analysis_version], [duracao_seg],
               [limite_pontuacao], [local], [examinador], [data_exame]}
    """
    rubrica = Rubrica(metadata.get("rubrica", "1020_2025"))
    limite = int(metadata.get("limite_pontuacao", 10))

    infracoes_render: list[dict[str, Any]] = []
    contagem = {"gravissima": 0, "grave": 0, "media": 0, "leve": 0}
    pontuacao = 0

    for d in infracoes_detectadas:
        info = por_id(d["id"])
        if info is None:
            continue
        infracoes_render.append(_render_infracao(d, info))
        contagem[info.severidade.value] = contagem.get(info.severidade.value, 0) + 1
        pontuacao += info.pontos

    aprovado = pontuacao <= limite
    motivo = ""
    if not aprovado:
        motivo = f"Somou {pontuacao} pontos (limite: {limite})"

    duracao_seg = float(metadata.get("duracao_seg", 240.0))

    ctx: dict[str, Any] = {
        "laudo_id": metadata.get("laudo_id", "LAU-000000"),
        "emitido_em": metadata.get("emitido_em") or datetime.now().strftime("%d/%m/%Y %H:%M"),
        "modelo_versao": metadata.get("modelo_versao", "—"),
        "rubrica": _rubrica_meta(rubrica, limite),
        "exame": {
            "candidato": candidato.get("nome", "—"),
            "cpf": candidato.get("cpf", "—"),
            "renach": candidato.get("renach", "—"),
            "processo": candidato.get("processo", "—"),
            "categoria": candidato.get("categoria", "—"),
            "veiculo": candidato.get("veiculo", "—"),
            "local": metadata.get("local", "—"),
            "examinador": metadata.get("examinador", "—"),
            "data_exame": metadata.get("data_exame") or datetime.now().strftime("%d/%m/%Y"),
        },
        "duracao_seg": duracao_seg,
        "duracao_fmt": _fmt_tempo(duracao_seg),
        "aprovado": aprovado,
        "pontuacao_total": pontuacao,
        "motivo_reprovacao": motivo,
        "contagem": contagem,
        "infracoes": infracoes_render,
        "linha_do_tempo": _linha_do_tempo(infracoes_render, duracao_seg),
        "positivos": metadata.get("positivos", []),
        "pontos_atencao": metadata.get("pontos_atencao", []),
        "video_hash": metadata.get("video_hash", "—"),
        "result_hash": metadata.get("result_hash", "—"),
        "analysis_version": metadata.get("analysis_version", "valbot-v1"),
        **_cobertura(rubrica),
    }
    return ctx  # type: ignore[return-value]
