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


def _gemini_rest_clip(
    video: str, start_s: int, end_s: int, fps: int, prompt: str, system: str
) -> str:
    """Chama o Gemini via API REST NATIVA do Vertex com `videoMetadata.fps`.

    O SDK instalado (google-genai 1.2.0) não expõe `fps` no VideoMetadata; a API
    REST aceita (campo documentado). Recorta [start_s, end_s] e amostra a `fps`
    quadros/segundo — resolução temporal fina para validar paradas breves.
    Devolve o texto (JSON) da resposta do modelo. Levanta em erro de transporte.
    """
    import urllib.request

    import google.auth
    import google.auth.transport.requests

    creds, _ = google.auth.default()
    creds.refresh(google.auth.transport.requests.Request())
    loc = settings.vertex_location or "global"
    host = "aiplatform.googleapis.com" if loc == "global" else f"{loc}-aiplatform.googleapis.com"
    url = (
        f"https://{host}/v1/projects/{settings.vertex_project}/locations/{loc}"
        f"/publishers/google/models/{settings.vertex_model}:generateContent"
    )
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "fileData": {"fileUri": str(video), "mimeType": "video/mp4"},
                        "videoMetadata": {
                            "fps": fps,
                            "startOffset": f"{start_s}s",
                            "endOffset": f"{end_s}s",
                        },
                    },
                    {"text": prompt},
                ],
            }
        ],
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
            "maxOutputTokens": 1024,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.load(r)
    cand = (resp.get("candidates") or [{}])[0]
    return "".join(p.get("text", "") for p in (cand.get("content", {}).get("parts") or []))


def _build_prompt_clip(
    infr: dict, rubrica: str, bloco_mbedv: str, start_s: int, end_s: int
) -> str:
    """Prompt do Comitê para validar UMA infração observando só o seu clipe."""
    rid = infr.get("id") or infr.get("codigo") or "?"
    ev = infr.get("evidence") or infr.get("descricao") or ""
    return f"""Você é o COMITÊ DE IA do Val Auditor (rubrica {rubrica}). Este clipe é o \
trecho {start_s}s–{end_s}s do vídeo do exame, amostrado a 3 quadros/segundo \
(resolução temporal fina — você consegue ver paradas breves).

A 1ª análise apontou ESTA infração neste ponto:
  • {rid} — "{ev}"

Reexamine APENAS este clipe, quadro a quadro, à luz da Matriz MBEDV abaixo:

{bloco_mbedv}

Decida se a infração SE CONFIRMA. Se em QUALQUER quadro a conduta exigida ocorre \
(ex.: parada obrigatória — o veículo aparece TOTALMENTE imóvel, rodas paradas, na \
faixa de retenção antes do cruzamento), então NÃO confirme. Na dúvida sobre a \
imobilização total, "nao_confirmada" (benefício da dúvida ao candidato).

resultado ∈ {{"infracao_confirmada", "excecao_aplicavel", "nao_confirmada"}}.

DEVOLVA SOMENTE JSON:
{{"resultado": "...", "evidencia": "o que viu, com o segundo exato", \
"interpretacao_normativa": "...", "confianca": 0.0}}
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
    """Executa o Comitê por CLIPE: para cada infração, recorta [t-3s, t+3s] e
    valida a 3fps (REST nativo) se a conduta de fato ocorreu naquele timestamp.

    Grounding fino evita a alucinação de timestamps do reexame do vídeo inteiro.
    Em falha total das chamadas, cai no laudo determinístico. Nunca levanta."""
    started = time.monotonic()

    if not settings.comite_habilitado or not video or not infracoes_detectadas:
        return _laudo_deterministico(exame_id, comparacao, deteccao, time.monotonic() - started)

    try:
        bloco_mbedv, _versao = prompt_builder.construir_bloco(None)
    except Exception:  # pragma: no cover — sem banco/seed
        bloco_mbedv = ""

    system = (
        "Você é o Comitê de IA do Val Auditor: valida UMA infração observando só o "
        "clipe do timestamp, com rigor; jamais decide pelo humano; na dúvida refuta."
    )

    causas: list[CausaIdentificada] = []
    verifs: list[VerificacaoComite] = []
    erros = 0
    for it in infracoes_detectadas:
        ts_raw = it.get("timestamp_s") or it.get("ts_seconds") or 0
        try:
            ts = float(ts_raw)
        except (TypeError, ValueError):
            ts = 0.0
        start = max(0, int(ts) - 3)
        end = int(ts) + 3
        prompt = _build_prompt_clip(it, rubrica, bloco_mbedv, start, end)
        try:
            raw = _parse_json(_gemini_rest_clip(str(video), start, end, 3, prompt, system))
        except Exception as e:  # noqa: BLE001 — resiliente por clipe
            erros += 1
            log.warning("comite clip falhou exame=%s ts=%s: %s", exame_id, ts, e)
            raw = {}
        res = raw.get("resultado", "nao_confirmada")
        causas.append(
            CausaIdentificada(
                causa=str(it.get("descricao") or it.get("id") or ""),
                evidencia=raw.get("evidencia", ""),
                interpretacao_normativa=raw.get("interpretacao_normativa", ""),
                confianca_causa=float(raw.get("confianca") or 0.0),
            )
        )
        verifs.append(
            VerificacaoComite(
                regra=str(it.get("id") or ""),
                segmento=f"{start}s-{end}s",
                resultado=res,
            )
        )

    # Todas as chamadas falharam → não inventa: cai no determinístico.
    if erros and erros == len(infracoes_detectadas):
        log.warning("comite exame=%s: todas as chamadas de clipe falharam", exame_id)
        return _laudo_deterministico(exame_id, comparacao, deteccao, time.monotonic() - started)

    confirmadas = sum(1 for v in verifs if v.resultado == "infracao_confirmada")
    conclusao = (
        "concorda_com_examinador"
        if verifs and confirmadas == len(verifs)
        else "manter_divergencia_com_fundamentacao"
    )
    log.info(
        "comite exame=%s clipes=%d confirmadas=%d", exame_id, len(verifs), confirmadas
    )
    return LaudoComite(
        exame_id=exame_id,
        comite_versao=settings.comite_versao + "+clip3fps",
        tempo_processamento_seg=round(time.monotonic() - started, 2),
        tipo_divergencia_analisada=comparacao.tipo_divergencia,
        tipo_divergencia_pos_comite=comparacao.tipo_divergencia,
        causas_identificadas=causas,
        verificacoes_executadas=verifs,
        comentarios_examinador_detectados=[],
        recomendacao_para_auditor=(
            f"{confirmadas}/{len(verifs)} infrações confirmadas no reexame por "
            f"clipe a 3fps (resolução temporal fina por timestamp)."
        ),
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
