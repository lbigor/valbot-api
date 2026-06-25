"""Pipeline de auditoria — orquestra os 5 motores → Comitê → OS (spec §2.3).

Costura toda a cadeia da spec para um exame:

    [1] Evidências  → valida/normaliza o payload
    [2] Detecção    → eventos brutos (Gemini)            ← reusa src/analysis
    [3] Normativo   → enquadra na Matriz (aplica §3.5)
    [4] Pontuação   → soma, limite ≤10, interrupção
    [5] Comparação  → classifica divergência vs oficial
        Comitê de IA → 2ª passada focada (só se houve divergência)
        OS          → abre Ordem de Serviço (só se houve divergência)
    Laudo           → JSON explicável + integridade

Cada etapa é persistida (``backend.persistence``) para auditabilidade. Sem
divergência, o exame é ENCERRADO sem trabalho humano (spec §2.3); com
divergência, segue para Comitê + OS (Auditor → Supervisor).

A função aceita um ``result`` já pronto (do analyzer atual) OU um caminho de
vídeo para rodar a detecção — assim integra com o fluxo existente sem reprocessar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend import persistence
from backend.committee import comite as comite_engine
from backend.compliance import repositorio as compliance_repo
from backend.engines import comparacao, deteccao, evidencias, normativo, pontuacao
from backend.engines.normativo import MatrizNacional
from backend.models import (
    ComentarioCompliance,
    Comparacao,
    Encaminhamento,
    LaudoComite,
    PayloadExame,
    ResultadoPontuacao,
    SaidaDeteccao,
    SaidaNormativo,
    TipoCompliance,
    TipoDivergencia,
)
from backend.reporting import laudo as laudo_mod
from backend.workflow import ordens

log = logging.getLogger("valbot.pipeline")


@dataclass
class ResultadoPipeline:
    exame_id: str
    deteccao: SaidaDeteccao
    normativo: SaidaNormativo
    pontuacao: ResultadoPontuacao
    comparacao: Comparacao
    comite: LaudoComite | None
    os_id: str | None
    laudo: dict
    compliance: list[ComentarioCompliance]


def _coletar_compliance(
    exame_id: str, deteccao_out: SaidaDeteccao, normativo_out: SaidaNormativo, result: dict | None
) -> list[ComentarioCompliance]:
    """Reúne os sinais NÃO-pontuáveis em comentários de compliance (spec §6/§10/§4-5).

    Três fontes: conduta inadequada do examinador, conduta do candidato (§4-5) e
    condutas detectadas fora do escopo pontuável do MBEDV (cinto, baliza, técnicas).
    """
    comentarios: list[ComentarioCompliance] = []

    # 1. Conduta inadequada do examinador (áudio).
    for c in deteccao_out.comentarios_examinador:
        comentarios.append(
            ComentarioCompliance(
                exame_id=exame_id,
                tipo=TipoCompliance.EXAMINADOR_INADEQUADO,
                descricao=c.descricao or c.transcricao or "",
                origem_codigo=c.evento_id,
                timestamp_s=c.timestamp_audio_seg,
                transcricao=c.transcricao,
                classificacao=c.classificacao,
            )
        )

    # 2. Conduta do candidato (MBEDV §4-5) — sinalizada pelo modelo, não pontua.
    for obs in (result or {}).get("observacoes_conduta") or []:
        if not isinstance(obs, dict):
            continue
        comentarios.append(
            ComentarioCompliance(
                exame_id=exame_id,
                tipo=TipoCompliance.CONDUTA_CANDIDATO,
                descricao=obs.get("descricao") or "",
                classificacao=obs.get("classificacao"),
                timestamp_s=obs.get("ts_seconds") or obs.get("timestamp_s"),
            )
        )

    # 3. Condutas detectadas fora do escopo pontuável do MBEDV (cinto, baliza, técnicas).
    sem_ficha = {
        n.evento_id
        for n in normativo_out.eventos_nao_enquadrados
        if n.motivo == "compliance_sem_ficha"
    }
    if sem_ficha:
        por_id = {e.evento_id: e for e in deteccao_out.eventos_detectados}
        for eid in sem_ficha:
            ev = por_id.get(eid)
            if not ev:
                continue
            comentarios.append(
                ComentarioCompliance(
                    exame_id=exame_id,
                    tipo=TipoCompliance.CONDUTA_SEM_FICHA,
                    descricao=ev.descricao or "",
                    origem_codigo=(ev.contexto_adicional or {}).get("regra_id"),
                    timestamp_s=ev.timestamp_video_seg or ev.timestamp_audio_seg,
                )
            )
    return comentarios


def processar(
    payload: PayloadExame,
    *,
    hash_exame: str,
    video: str | None = None,
    result: dict | None = None,
    matriz: MatrizNacional | None = None,
    persistir: bool = True,
) -> ResultadoPipeline:
    """Executa a cadeia completa para um exame. Não levanta por falha de IA —
    cai nos caminhos resilientes de cada motor."""
    exame_id = payload.exame_id or hash_exame
    matriz = matriz or MatrizNacional.carregar()

    # [1] Evidências — valida o que veio e marca o que falta (não bloqueia aqui;
    # lacunas viram divergência no Motor de Comparação).
    validacao = evidencias.validar(payload, duracao_seg=payload.duracao_video_seg)
    if validacao.campos_faltantes:
        log.info("evidencias exame=%s campos_faltantes=%s", exame_id, validacao.campos_faltantes)
    if persistir:
        persistence.salvar_payload(hash_exame, payload)
        # Cada vídeo é uma OS, aberta já aqui (equivale ao init_upload): o número
        # é o ID do upload e o relógio do SLA começa neste instante (spec §12).
        ordens.abrir_os_no_upload(exame_id, hash_exame=hash_exame)

    # [2] Detecção — eventos brutos.
    if result is not None:
        saida_det = deteccao.eventos_de_result(exame_id, result)
    elif video is not None:
        saida_det, result = deteccao.detectar(
            video,
            exame_id=exame_id,
            categoria=payload.candidato.categoria_pretendida.value
            if payload.candidato.categoria_pretendida
            else None,
            training_annotations=payload.training_annotations,
            rubrica=payload.rubrica,
        )
    else:
        raise ValueError("processar() exige `video` ou `result`")
    if persistir:
        persistence.salvar_deteccao(hash_exame, saida_det)

    # [3] Normativo — enquadra aplicando as exceções da §3.5 (passa os
    # comentários do examinador para detectar conduta induzida).
    saida_norm = normativo.enquadrar(
        saida_det.eventos_detectados,
        exame_id=exame_id,
        categoria=payload.candidato.categoria_pretendida.value
        if payload.candidato.categoria_pretendida
        else None,
        comentarios_examinador=saida_det.comentarios_examinador,
        matriz=matriz,
    )
    if persistir:
        persistence.salvar_normativo(hash_exame, saida_norm)

    # [4] Pontuação.
    houve_interrupcao = bool(
        payload.resultado_oficial and payload.resultado_oficial.houve_interrupcao
    )
    rp = pontuacao.calcular(
        saida_norm,
        houve_interrupcao=houve_interrupcao,
        motivo_interrupcao=payload.resultado_oficial.motivo_interrupcao
        if payload.resultado_oficial
        else None,
        modelo_deteccao_versao=saida_det.modelo_versao,
    )
    if persistir:
        persistence.salvar_pontuacao(hash_exame, rp)

    # [5] Comparação — resultado oficial: do payload, ou já persistido.
    oficial = payload.resultado_oficial
    if oficial is None and persistir:
        oficial = persistence.ler_resultado_oficial(hash_exame)
    comp = comparacao.comparar(rp, oficial, evidencia_suficiente=saida_det.evidencia_suficiente)
    if persistir:
        persistence.salvar_divergencia(hash_exame, comp)

    # Comitê de IA — só quando há divergência (encaminhamento = comitê).
    laudo_comite: LaudoComite | None = None
    if comp.encaminhamento.value == "comite_de_ia":
        infracoes_det = (
            [i for i in (result.get("infracoes_detectadas") or []) if isinstance(i, dict)]
            if result
            else []
        )
        try:
            laudo_comite = comite_engine.revisar(
                video,
                exame_id=exame_id,
                infracoes_detectadas=infracoes_det,
                comparacao=comp,
                deteccao=saida_det,
                rubrica=payload.rubrica,
            )
            if persistir:
                persistence.salvar_comite(hash_exame, laudo_comite)
        except comite_engine.ComiteSemIAError as e:
            # IA indisponível (quota/timeout/erro) — NÃO grava laudo determinístico
            # (falsa 2ª opinião). O exame fica PENDENTE de comitê (stage 'comite')
            # e o reprocessador (tooling.reprocessar_comite) re-tenta no próximo
            # ciclo quando a IA voltar. laudo_comite permanece None.
            log.warning("pipeline comite sem IA exame=%s — pendente: %s", exame_id, e)

    # Reencaminhamento pós-comitê (evolução §10): se o Comitê reavaliou com o
    # prompt MBEDV e passou a CONCORDAR com o examinador, a divergência está
    # resolvida — o exame ENCERRA e NÃO entra na fila do Auditor.
    comp_efetiva = comp
    if (
        laudo_comite is not None
        and laudo_comite.tipo_divergencia_pos_comite == TipoDivergencia.SEM_DIVERGENCIA
    ):
        comp_efetiva = comp.model_copy(
            update={
                "tipo_divergencia": TipoDivergencia.SEM_DIVERGENCIA,
                "encaminhamento": Encaminhamento.ENCERRAMENTO,
            }
        )

    # Compliance — sinais NÃO-pontuáveis (examinador, conduta §4-5, condutas sem
    # ficha MBEDV). Persistidos para a tela dedicada; não afetam a pontuação.
    comentarios_compliance = _coletar_compliance(exame_id, saida_det, saida_norm, result)
    if persistir and comentarios_compliance:
        compliance_repo.registrar_varios(hash_exame, comentarios_compliance)

    # Atualiza a OS (já aberta no upload): encerra sem divergência ou encaminha
    # ao Auditor com divergência. O número/SLA da OS vêm do init_upload.
    os_id: str | None = None
    if persistir:
        os_id = ordens.atualizar_pos_analise(hash_exame, comp_efetiva)

    # Laudo explicável (JSON + integridade).
    laudo = laudo_mod.montar_laudo_json(
        exame_id=exame_id,
        payload=payload,
        deteccao=saida_det,
        normativo=saida_norm,
        pontuacao=rp,
        comparacao=comp,
        comite=laudo_comite,
        os_id=os_id,
        video_hash=payload.hash_video or hash_exame,
        compliance=comentarios_compliance,
    )

    log.info(
        "pipeline exame=%s resultado=%s pontos=%s divergencia=%s os=%s",
        exame_id,
        rp.resultado_calculado.value,
        rp.pontuacao_calculada,
        comp.tipo_divergencia.value,
        os_id,
    )
    return ResultadoPipeline(
        exame_id=exame_id,
        deteccao=saida_det,
        normativo=saida_norm,
        pontuacao=rp,
        comparacao=comp,
        comite=laudo_comite,
        os_id=os_id,
        laudo=laudo,
        compliance=comentarios_compliance,
    )
