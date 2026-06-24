"""Comitê de IA (spec §10).

Segunda passada de análise focada. Diferente do Motor de Detecção (que varre o
vídeo inteiro procurando TODAS as condutas da rubrica), o Comitê recebe APENAS
as infrações já encontradas e re-pergunta ao Gemini, com um prompt restrito às
condutas que "devem acontecer no vídeo", para CONFIRMAR ou REFUTAR cada uma com
fundamentação — reanalisando os segmentos correspondentes (spec §10.2).

Princípios inegociáveis (spec §10.1):
  • O Comitê NUNCA encerra o processo nem decide — só explica e fundamenta.
  • O Comitê NÃO reverte a divergência — produz laudo para o humano.
  • Rigor acima de velocidade.

Quando o Vertex não está disponível (dev/teste), cai num modo determinístico
que produz um laudo coerente a partir dos dados já presentes, sem chamar a IA.
"""

from __future__ import annotations

import json
import logging
import time

from backend.core.config import settings
from backend.matriz import prompt_builder
from backend.models import (
    CausaIdentificada,
    ComentarioExaminador,
    Comparacao,
    LaudoComite,
    SaidaDeteccao,
    TipoDivergencia,
    VerificacaoComite,
)

log = logging.getLogger("valbot.comite")


def _decidir_divergencia_pos_comite(raw: dict, tipo_pre: TipoDivergencia) -> TipoDivergencia:
    """Interpreta a conclusão do Comitê para decidir a divergência PÓS-reavaliação.

    "concorda_com_examinador" → SEM_DIVERGENCIA (resolvida, não entra na fila).
    Qualquer outra conclusão → mantém o tipo original (segue ao Auditor).
    """
    conclusao = (raw.get("conclusao_comite") or "").lower()
    if "concord" in conclusao and "examinador" in conclusao:
        return TipoDivergencia.SEM_DIVERGENCIA
    return tipo_pre


def _build_prompt_comite(infracoes: list[dict], rubrica: str, categoria: str | None = None) -> str:
    """Prompt restrito às infrações encontradas — o coração do Comitê.

    Lista cada conduta apontada (com timestamp e evidência) e pede que o modelo
    reexamine SÓ esses pontos do vídeo, decidindo confirmar/refutar e checando
    as exceções do MBEDV (``quando_nao_pontuar``).
    """
    linhas = []
    for it in infracoes:
        rid = it.get("id") or it.get("codigo") or "?"
        ts = it.get("timestamp_s") or it.get("ts_seconds")
        ts_fmt = (
            f"{int(ts) // 60:02d}:{int(ts) % 60:02d}" if isinstance(ts, (int, float)) else "??:??"
        )
        ev = it.get("evidence") or it.get("descricao") or ""
        linhas.append(f'  • {rid} @ {ts_fmt} — "{ev}"')
    lista = "\n".join(linhas) if linhas else "  (nenhuma infração apontada)"

    # Bloco de regras da Matriz vigente (prompt MBEDV) — fonte única §4.1.
    try:
        bloco_mbedv, _versao = prompt_builder.construir_bloco(categoria)
    except Exception:  # pragma: no cover — sem banco/seed, segue sem bloco
        bloco_mbedv = ""

    return f"""Você é o COMITÊ DE IA do Val Auditor, auditando o exame prático de \
direção (rubrica {rubrica}).

Sua tarefa NÃO é varrer o vídeo inteiro. Você recebeu a lista FECHADA de \
infrações que a primeira análise apontou. Reexamine APENAS os segmentos do \
vídeo correspondentes a CADA uma destas infrações — as condutas que "devem \
acontecer no vídeo" — e decida, com rigor, se cada uma se confirma, à luz da \
Matriz MBEDV vigente abaixo:

{bloco_mbedv}

INFRAÇÕES A REVISAR:
{lista}

Para cada infração da lista:
  1. Vá ao timestamp indicado e reexamine visão + áudio do entorno [t-3s, t+3s].
  2. Verifique se há EXCEÇÃO do MBEDV que descaracterize a infração (comando
     autorizado do examinador, emergência, orientação do preposto, ultrapassagem
     regular dentro do tempo necessário, etc.).
  3. Decida: "infracao_confirmada" | "excecao_aplicavel" | "nao_confirmada".

Também relate comentários do EXAMINADOR que possam ter induzido o candidato ao
erro ou sido intimidatórios (proibidos pelo MBEDV) — para auditoria da conduta
do examinador, não do candidato.

CONCLUSÃO (decisão do Comitê após reavaliar com a Matriz MBEDV):
  • Se a reavaliação CONFIRMA o que o examinador apontou (as infrações se
    sustentam pela Matriz vigente), conclua "concorda_com_examinador" — a
    divergência está RESOLVIDA e o exame NÃO precisa de auditoria humana.
  • Se MANTÉM a discordância (exceção aplicável, evidência frágil, enquadramento
    incorreto), conclua "mantem_divergencia_com_fundamentacao" — segue ao Auditor.

DEVOLVA SOMENTE JSON neste formato:
{{
  "causas_identificadas": [
    {{"causa": "...", "evidencia": "Examinador apontou X em 02:15; segmento 02:10-02:20 indica ...",
      "interpretacao_normativa": "Enquadra-se na exceção ... do MBEDV", "confianca_causa": 0.84}}
  ],
  "verificacoes_executadas": [
    {{"regra": "R1020-G-d", "segmento": "02:10-02:20", "resultado": "excecao_aplicavel"}}
  ],
  "comentarios_examinador_detectados": [
    {{"timestamp_audio": 215, "transcricao": "...", "classificacao": "comentario_inadequado_intimidatorio"}}
  ],
  "recomendacao_para_auditor": "Atenção ao segmento ...",
  "conclusao_comite": "concorda_com_examinador | mantem_divergencia_com_fundamentacao"
}}
"""


def _laudo_deterministico(
    exame_id: str,
    comparacao: Comparacao,
    deteccao: SaidaDeteccao,
    tempo: float,
) -> LaudoComite:
    """Laudo sem IA — usado em dev/teste ou quando o Vertex falha.

    Sintetiza causas a partir da divergência e propaga comentários do
    examinador já captados pelo Motor de Detecção.
    """
    causas: list[CausaIdentificada] = []
    verifs: list[VerificacaoComite] = []
    if comparacao.tipo_divergencia != TipoDivergencia.SEM_DIVERGENCIA:
        causas.append(
            CausaIdentificada(
                causa=f"Divergência {comparacao.tipo_divergencia.value} entre cálculo e oficial",
                evidencia=json.dumps(comparacao.detalhes, ensure_ascii=False),
                interpretacao_normativa="Requer verificação humana dos segmentos divergentes",
                confianca_causa=0.5,
            )
        )

    comentarios = [
        ComentarioExaminador(
            timestamp_audio=c.timestamp_audio_seg,
            transcricao=c.transcricao or "",
            classificacao=c.classificacao or "comentario_potencialmente_inadequado",
        )
        for c in deteccao.comentarios_examinador
    ]

    return LaudoComite(
        exame_id=exame_id,
        comite_versao=settings.comite_versao + "+deterministico",
        tempo_processamento_seg=round(tempo, 2),
        tipo_divergencia_analisada=comparacao.tipo_divergencia,
        tipo_divergencia_pos_comite=comparacao.tipo_divergencia,
        causas_identificadas=causas,
        verificacoes_executadas=verifs,
        comentarios_examinador_detectados=comentarios,
        recomendacao_para_auditor=(
            "Revisar os segmentos das infrações apontadas; conferir exceções do MBEDV."
        ),
        conclusao_comite="manter_divergencia_com_fundamentacao",
    )


def _build_prompt_justificativa(infracoes: list[dict], rubrica: str, bloco_mbedv: str) -> str:
    """Prompt do Comitê: AMPARA a decisão do auditor explicando, com fundamentação
    MBEDV, o MOTIVO de cada infração detectada — sem reanalisar o vídeo (raciocina
    sobre a evidência já capturada pela 1ª análise + a Matriz)."""
    linhas = []
    for it in infracoes:
        rid = it.get("id") or it.get("codigo") or "?"
        ts = it.get("timestamp_s") or it.get("ts_seconds")
        ts_fmt = (
            f"{int(ts) // 60:02d}:{int(ts) % 60:02d}" if isinstance(ts, (int, float)) else "??:??"
        )
        ev = it.get("evidence") or it.get("descricao") or ""
        linhas.append(f'  • {rid} @ {ts_fmt} — "{ev}"')
    lista = "\n".join(linhas) if linhas else "  (nenhuma infração apontada)"

    return f"""Você é o COMITÊ DE IA do Val Auditor (rubrica {rubrica}). Sua função é \
AMPARAR a decisão do auditor humano: para CADA infração detectada pela 1ª análise, \
explique com clareza e fundamentação o MOTIVO de ela ter sido aplicada — ou aponte \
por que NÃO se sustenta. Você NÃO decide pelo humano e NÃO reanalisa o vídeo: \
raciocina sobre a evidência registrada e a Matriz MBEDV.

INFRAÇÕES DETECTADAS (id @ timestamp — evidência):
{lista}

Para CADA infração, à luz da Matriz MBEDV abaixo, produza:
  - motivo: por que a conduta caracteriza (ou não) a falta, em linguagem clara e objetiva.
  - conduta_observavel: o que o candidato fez (ou deixou de fazer) que configura a falta.
  - base_legal: o artigo CTB + a ficha MBEDV + gravidade/peso.
  - excecao_aplicavel: se alguma condição de "NÃO pontua" da ficha se aplica — qual, ou "nenhuma".
  - veredicto: "sustenta" | "nao_sustenta" | "revisar" (exige olho humano).
  - confianca: 0.0 a 1.0.

{bloco_mbedv}

DEVOLVA SOMENTE JSON:
{{
  "infracoes": [
    {{"id": "...", "motivo": "...", "conduta_observavel": "...", "base_legal": "...",
      "excecao_aplicavel": "...", "veredicto": "sustenta|nao_sustenta|revisar", "confianca": 0.0}}
  ],
  "recomendacao_para_auditor": "síntese objetiva que ampara a decisão do auditor"
}}
"""


def revisar(
    video: str | None,
    *,
    exame_id: str,
    infracoes_detectadas: list[dict],
    comparacao: Comparacao,
    deteccao: SaidaDeteccao,
    rubrica: str = "1020/2025",
) -> LaudoComite:
    """Executa o Comitê como MOTOR DE JUSTIFICATIVA: explica, com fundamentação
    MBEDV, o MOTIVO de cada infração detectada — para amparar a decisão do auditor.

    NÃO reanalisa o vídeo (1 chamada de TEXTO, barata; a evidência da 1ª análise é
    o insumo). Em falha, cai no laudo determinístico. Nunca levanta. `video` é
    mantido por compatibilidade de assinatura (não usado)."""
    started = time.monotonic()

    if not settings.comite_habilitado or not infracoes_detectadas:
        return _laudo_deterministico(exame_id, comparacao, deteccao, time.monotonic() - started)

    # Matriz RESTRITA às fichas dos artigos detectados — o Comitê só julga essas;
    # encolhe o prompt e evita estourar o tamanho do pedido em exames com muitas
    # infrações (que antes caíam no laudo determinístico).
    artigos = {str(it.get("id") or it.get("codigo") or "") for it in infracoes_detectadas}
    artigos = {a for a in artigos if a}
    try:
        bloco_mbedv, _versao = prompt_builder.construir_bloco(None, artigos=artigos)
    except Exception:  # pragma: no cover — sem banco/seed
        bloco_mbedv = ""

    try:
        import vertexai
        from vertexai.generative_models import GenerationConfig, GenerativeModel

        vertexai.init(project=settings.vertex_project, location=settings.vertex_location)
        model = GenerativeModel(
            settings.vertex_model,
            system_instruction=(
                "Você é o Comitê de IA do Val Auditor: AMPARA a decisão do auditor "
                "humano explicando, com fundamentação MBEDV, o motivo de cada infração "
                "detectada. Rigor e clareza; jamais decide pelo humano."
            ),
        )
        prompt = _build_prompt_justificativa(infracoes_detectadas, rubrica, bloco_mbedv)
        resp = model.generate_content(
            [prompt],
            generation_config=GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=4096,
            ),
        )
        raw = _parse_json(resp.text)
        laudo = _laudo_de_justificativa(exame_id, comparacao, raw, time.monotonic() - started)
        log.info("comite exame=%s justificativas=%d", exame_id, len(laudo.causas_identificadas))
        return laudo
    except Exception as e:  # pragma: no cover — fallback resiliente
        log.warning("comite Gemini falhou exame=%s (%s) — determinístico", exame_id, e)
        return _laudo_deterministico(exame_id, comparacao, deteccao, time.monotonic() - started)


def _laudo_de_justificativa(
    exame_id: str, comparacao: Comparacao, raw: dict, tempo: float
) -> LaudoComite:
    """Mapeia o JSON de justificativas → LaudoComite. Cada infração vira uma
    CausaIdentificada (conduta + MOTIVO + base legal) e uma VerificacaoComite
    (veredicto sustenta/nao_sustenta/revisar)."""
    infs = [i for i in (raw.get("infracoes") or []) if isinstance(i, dict)]
    causas = [
        CausaIdentificada(
            causa=str(i.get("conduta_observavel") or i.get("id") or ""),
            evidencia=str(i.get("motivo") or ""),
            interpretacao_normativa=(
                str(i.get("base_legal") or "")
                + (
                    f" · Exceção: {i.get('excecao_aplicavel')}"
                    if i.get("excecao_aplicavel")
                    and str(i.get("excecao_aplicavel")).strip().lower() not in ("nenhuma", "")
                    else ""
                )
            ),
            confianca_causa=float(i.get("confianca") or 0.0),
        )
        for i in infs
    ]
    verifs = [
        VerificacaoComite(
            regra=str(i.get("id") or ""),
            segmento=str(i.get("base_legal") or ""),
            resultado=str(i.get("veredicto") or "revisar"),
        )
        for i in infs
    ]
    sustenta = sum(1 for i in infs if str(i.get("veredicto")) == "sustenta")
    conclusao = (
        "concorda_com_examinador"
        if infs and sustenta == len(infs)
        else "manter_divergencia_com_fundamentacao"
    )
    return LaudoComite(
        exame_id=exame_id,
        comite_versao=settings.comite_versao + "+justificativa",
        tempo_processamento_seg=round(tempo, 2),
        tipo_divergencia_analisada=comparacao.tipo_divergencia,
        tipo_divergencia_pos_comite=comparacao.tipo_divergencia,
        causas_identificadas=causas,
        verificacoes_executadas=verifs,
        comentarios_examinador_detectados=[],
        recomendacao_para_auditor=str(raw.get("recomendacao_para_auditor") or ""),
        conclusao_comite=conclusao,
    )


def _laudo_de_raw(exame_id: str, comparacao: Comparacao, raw: dict, tempo: float) -> LaudoComite:
    return LaudoComite(
        exame_id=exame_id,
        comite_versao=settings.comite_versao,
        tempo_processamento_seg=round(tempo, 2),
        tipo_divergencia_analisada=comparacao.tipo_divergencia,
        tipo_divergencia_pos_comite=_decidir_divergencia_pos_comite(
            raw, comparacao.tipo_divergencia
        ),
        causas_identificadas=[
            CausaIdentificada(
                causa=c.get("causa", ""),
                evidencia=c.get("evidencia", ""),
                interpretacao_normativa=c.get("interpretacao_normativa", ""),
                confianca_causa=float(c.get("confianca_causa") or 0.0),
            )
            for c in (raw.get("causas_identificadas") or [])
            if isinstance(c, dict)
        ],
        verificacoes_executadas=[
            VerificacaoComite(
                regra=v.get("regra", ""),
                segmento=v.get("segmento", ""),
                resultado=v.get("resultado", ""),
            )
            for v in (raw.get("verificacoes_executadas") or [])
            if isinstance(v, dict)
        ],
        comentarios_examinador_detectados=[
            ComentarioExaminador(
                timestamp_audio=c.get("timestamp_audio"),
                transcricao=c.get("transcricao", ""),
                classificacao=c.get("classificacao", ""),
            )
            for c in (raw.get("comentarios_examinador_detectados") or [])
            if isinstance(c, dict)
        ],
        recomendacao_para_auditor=raw.get("recomendacao_para_auditor", ""),
        conclusao_comite=raw.get("conclusao_comite", "manter_divergencia_com_fundamentacao"),
    )


def _parse_json(text: str) -> dict:
    import re

    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        return json.loads(m.group(0)) if m else {}
