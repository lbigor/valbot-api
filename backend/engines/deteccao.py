"""Motor de Detecção (spec §6).

Identifica eventos observáveis no vídeo/áudio. NÃO faz julgamento normativo —
apenas detecta o que acontece e devolve EVENTOS BRUTOS para o Motor Normativo
enquadrar.

Reaproveita o pipeline de análise já em produção
(``src.analysis.openrouter_gemini.analyze_video``), que roda o Gemini 3.x Pro
no vídeo inteiro (visão + áudio) e devolve o schema ``tier_a/0.1``. Aqui,
convertemos as infrações que o Gemini apontou em ``EventoDetectado`` carregando
o código da regra no contexto — o enquadramento formal vira responsabilidade
do Motor Normativo (mantendo as duas etapas auditáveis, spec §6.3).
"""

from __future__ import annotations

import logging

from backend.models import EventoDetectado, SaidaDeteccao

log = logging.getLogger("valbot.deteccao")

# Sinais de contexto que habilitam as não-pontuações da §3.5 (quando o detector
# os emitir). Propagados do item do result para o evento.
_CTX_EXCECOES = (
    "motor_morreu",
    "veiculo_morreu",
    "sem_justa_razao",
    "desligamento_voluntario",
    "reiterado",
    "havia_emergencia",
    "intervencao_preposto",
    "comando_examinador",
    "comando_autorizado",
    "baliza_isolada",
    "tentativas_baliza",
)


def _canal(item: dict) -> str:
    canal = item.get("canal_evidencia") or "visao"
    return str(canal)


def eventos_de_result(exame_id: str, result: dict) -> SaidaDeteccao:
    """Converte um result.json (schema tier_a/0.1) em eventos brutos.

    Usado tanto pelo caminho online (após ``analyze_video``) quanto para
    re-derivar eventos de um result já persistido (reprocesso/teste).
    """
    detectadas = result.get("infracoes_detectadas") or []
    engine = result.get("engine") or {}
    modelo_versao = f"{engine.get('backend', 'vertex_gemini')}/{engine.get('model', '?')}"

    eventos: list[EventoDetectado] = []
    for i, item in enumerate(detectadas, start=1):
        if not isinstance(item, dict):
            continue
        rid = item.get("id") or item.get("codigo")
        ctx = {
            "regra_id": rid,
            "severidade": item.get("severidade"),
            "verificacao_examinador": item.get("verificacao_examinador"),
            "evidence": item.get("evidence"),
        }
        # Propaga sinais de contexto da §3.5 quando o detector os fornecer
        # (motor que morreu, exceções, baliza) — habilitam as não-pontuações.
        for k in _CTX_EXCECOES:
            if k in item:
                ctx[k] = item[k]
        eventos.append(
            EventoDetectado(
                evento_id=f"EV-{i:03d}",
                categoria=_categoria_da_regra(rid),
                descricao=item.get("descricao") or item.get("evidence") or "",
                timestamp_video_seg=item.get("timestamp_s") or item.get("ts_seconds"),
                duracao_seg=item.get("duracao_s"),
                confianca=float(item.get("confidence") or 0.0),
                canal_evidencia=_canal(item),
                quadrante_origem=item.get("quadrante_origem"),
                camera_origem=item.get("camera_origem"),
                contexto_adicional=ctx,
            )
        )

    # Comentários/condutas do examinador captados pelo áudio (não pontuam o
    # candidato; alimentam a auditoria de conduta do examinador — spec §6.2).
    comentarios: list[EventoDetectado] = []
    for j, obs in enumerate(result.get("observacoes_conduta") or [], start=1):
        if not isinstance(obs, dict):
            continue
        classificacao = obs.get("classificacao") or obs.get("tipo")
        if not (
            obs.get("ator") == "examinador" or "examinador" in str(classificacao or "").lower()
        ):
            continue
        comentarios.append(
            EventoDetectado(
                evento_id=f"EX-{j:03d}",
                categoria="evento_examinador",
                descricao=obs.get("descricao") or "",
                timestamp_audio_seg=obs.get("ts_seconds") or obs.get("timestamp_s"),
                transcricao=obs.get("transcricao"),
                classificacao=classificacao or "comentario_potencialmente_inadequado",
                canal_evidencia="audio",
            )
        )

    video = result.get("video") or {}
    return SaidaDeteccao(
        exame_id=exame_id,
        modelo_versao=modelo_versao,
        eventos_detectados=eventos,
        comentarios_examinador=comentarios,
        audio_disponivel=video.get("audio_quality_flag") is not None,
        evidencia_suficiente=not bool(result.get("rejected")),
    )


def detectar(
    video: str,
    *,
    exame_id: str,
    categoria: str | None = None,
    training_annotations: list[dict] | None = None,
    rubrica: str = "1020/2025",
) -> tuple[SaidaDeteccao, dict]:
    """Roda o Gemini no vídeo e devolve (eventos brutos, result.json cru).

    ``video`` pode ser caminho local ou ``gs://`` URI. O result cru é
    propagado para o Motor de Pontuação reaproveitar layout/duração/custo e
    para o Comitê reanalisar os mesmos segmentos.
    """
    from src.analysis.openrouter_gemini import AnalysisOptions, analyze_video

    opts = AnalysisOptions(
        rubrica_slug=rubrica,
        training_annotations=training_annotations,
        categoria=categoria,
        use_modular_v26=bool(categoria),
    )
    result = analyze_video(video, rubrica_slug=rubrica, options=opts)
    saida = eventos_de_result(exame_id, result)
    log.info(
        "deteccao exame=%s eventos=%d comentarios_examinador=%d",
        exame_id,
        len(saida.eventos_detectados),
        len(saida.comentarios_examinador),
    )
    return saida, result


# Mapa grosseiro código→categoria de evento (spec §6.2). O enquadramento fino
# fica no Motor Normativo; aqui é só rotulagem da natureza do evento bruto.
_CATEGORIA_POR_PREFIXO = {
    "R1020-G-a": "sinalizacao",
    "R1020-G-d": "trajetoria",
    "R1020-G-e": "sinalizacao",
    "R1020-G-g": "velocidade",
    "R1020-GR-a": "sinalizacao",
    "R1020-GR-c": "interacao",
    "R1020-GR-f": "equipamentos",
    "R1020-M-d": "trajetoria",
    "R1020-M-e": "comportamento",
}


def _categoria_da_regra(rid: str | None) -> str:
    if not rid:
        return "comportamento"
    if rid in _CATEGORIA_POR_PREFIXO:
        return _CATEGORIA_POR_PREFIXO[rid]
    if "-G-" in rid or "-GR-" in rid:
        return "sinalizacao"
    return "comportamento"
