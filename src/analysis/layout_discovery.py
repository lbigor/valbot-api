"""Fase 1 da arquitetura modular — descobre o layout de câmeras de um vídeo de
exame antes de rodar a análise principal.

Usa Gemini 2.5 Flash via Vertex AI (mesma cred GCP do analyzer principal,
muito mais barato que Pro pra essa tarefa simples de classificação):
  • Custo: ~$0.075 / 1M input tokens vs $1.25 do Pro = 17× mais barato.
  • Latência: ~3-8s vs 20-30s do Pro.
  • Free tier do Vertex não existe nesse contexto — autenticação é por
    service account; cobrança é por uso (centavos/exame).

Devolve um `CameraMap` que o composer (Phase 2b) consome pra montar o
user_prompt direcionado.

A análise considera apenas os primeiros segundos do vídeo (o layout não muda
durante o exame). Mesmo assim mandamos o vídeo inteiro pro Vertex porque
truncamento client-side via ffmpeg é cara de manter; o prompt instrui o
modelo a olhar só o início.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_PROMPT = (
    PROJECT_ROOT / "tooling" / "bench_demo" / "presets" / "v26" / "discovery" / "layout_2x2.md"
)

CameraName = Literal["frontal", "interna", "lateral_direita", "traseira_esq", "desconhecido"]
QuadrantName = Literal["TL", "TR", "BL", "BR"]


@dataclass
class QuadrantInfo:
    """Identificação de um quadrante do vídeo."""

    camera: CameraName = "desconhecido"
    confianca: float = 0.0
    descricao: str = ""


@dataclass
class CameraMap:
    """Resultado da fase de discovery. Consumido pelo composer e pelo analyzer.

    `layout_detectado`:
      • `vip_intelbras_2x2`  → layout VIP canônico (TL=frontal, TR=lat_d, BL=int, BR=tras_e)
      • `hikvision_2x2`      → layout Hikvision canônico
      • `desconhecido`       → fabricante novo OU vídeo defeituoso — quadrantes
                               podem estar preenchidos mesmo assim (usa os
                               campos `quadrantes` em vez do enum).

    `confianca_layout < 0.6` → o sistema deve preferir o caminho de fallback
    (prompt v25 monolítico) e logar pra inspeção humana.
    """

    layout_detectado: Literal["vip_intelbras_2x2", "hikvision_2x2", "desconhecido"] = "desconhecido"
    confianca_layout: float = 0.0
    quadrantes: dict[QuadrantName, QuadrantInfo] = field(default_factory=dict)
    fabricante_provavel: str = "desconhecido"
    # Custo desse discovery (preenchido pelo caller; útil pra contabilidade).
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    raw_response: str = ""

    @property
    def confiavel(self) -> bool:
        """True quando o resultado é seguro o suficiente pra alimentar o composer.

        Threshold baixado pra 0.5 (era 0.6). A inferência por fabricante
        (`_infer_layout_from_fabricante`) recupera casos onde o flash reconhece
        o fabricante mas deixa `layout_detectado=desconhecido` — após inferência
        o enum vira hikvision_2x2/vip_intelbras_2x2 e este gate passa.
        """
        return self.confianca_layout >= 0.5 and self.layout_detectado != "desconhecido"

    def quadrante_por_camera(self, camera: CameraName) -> QuadrantName | None:
        """Inverte o mapa — útil pro composer ('onde tá a câmera FRONTAL?')."""
        for q, info in self.quadrantes.items():
            if info.camera == camera:
                return q  # type: ignore[return-value]
        return None


# Schema server-side do discovery — garante JSON válido (evita truncamento que
# fazia o parse falhar e cair pra "desconhecido"). Binário: sem "desconhecido".
_QUAD_SCHEMA = {
    "type": "object",
    "properties": {
        "camera": {
            "type": "string",
            "enum": ["frontal", "interna", "lateral_direita", "traseira_esq"],
        },
        "confianca": {"type": "number"},
        "descricao": {"type": "string"},
    },
    "required": ["camera", "confianca"],
}
_LAYOUT_SCHEMA = {
    "type": "object",
    "properties": {
        "layout_detectado": {"type": "string", "enum": ["vip_intelbras_2x2", "hikvision_2x2"]},
        "confianca_layout": {"type": "number"},
        "quadrantes": {
            "type": "object",
            "properties": dict.fromkeys(("TL", "TR", "BL", "BR"), _QUAD_SCHEMA),
            "required": ["TL", "TR", "BL", "BR"],
        },
        "fabricante_provavel": {"type": "string", "enum": ["VIP", "Hikvision"]},
    },
    "required": ["layout_detectado", "confianca_layout", "quadrantes", "fabricante_provavel"],
}


# Ordem canônica de quadrantes por fabricante (fonte: cat_B/base.md + mbedv).
# Usada pra inferir o layout quando o flash reconhece o fabricante mas deixa
# `layout_detectado=desconhecido` (inconsistência comum do gemini-2.5-flash).
_FAB_CANONICO = {
    "vip": (
        "vip_intelbras_2x2",
        {"TL": "frontal", "TR": "lateral_direita", "BL": "interna", "BR": "traseira_esq"},
    ),
    "vip intelbras": (
        "vip_intelbras_2x2",
        {"TL": "frontal", "TR": "lateral_direita", "BL": "interna", "BR": "traseira_esq"},
    ),
    "intelbras": (
        "vip_intelbras_2x2",
        {"TL": "frontal", "TR": "lateral_direita", "BL": "interna", "BR": "traseira_esq"},
    ),
    "hik": (
        "hikvision_2x2",
        {"TL": "interna", "TR": "frontal", "BL": "traseira_esq", "BR": "lateral_direita"},
    ),
    "hikvision": (
        "hikvision_2x2",
        {"TL": "interna", "TR": "frontal", "BL": "traseira_esq", "BR": "lateral_direita"},
    ),
}


def _derive_layout_from_quadrantes(cm: CameraMap) -> None:
    """Deriva VIP vs Hikvision da POSIÇÃO das câmeras, não do label do modelo.

    Premissa do negócio: SÓ existem 2 modelos de câmera (VIP Intelbras e
    Hikvision). Logo `fabricante_provavel=outro/desconhecido` é sempre falso —
    todo vídeo é um dos dois. A diferença canônica é a posição de 2 câmeras:

        câmera     | VIP  | Hikvision
        -----------|------|----------
        interna    | BL   | TL
        frontal    | TL   | TR

    Esta função olha ONDE o modelo colocou `interna` e `frontal` nos quadrantes
    e deriva o enum + confiança, ignorando o `layout_detectado`/`fabricante`
    que o flash devolveu. Só cai pra fallback se nem `interna` nem `frontal`
    foram localizadas (vídeo realmente ilegível).
    """
    # Onde estão interna e frontal?
    pos = {
        info.camera: q
        for q, info in cm.quadrantes.items()
        if info.camera not in ("desconhecido", "", None)
    }
    interna_q = pos.get("interna")
    frontal_q = pos.get("frontal")

    votos_vip = 0
    votos_hik = 0
    if interna_q == "BL":
        votos_vip += 1
    elif interna_q == "TL":
        votos_hik += 1
    if frontal_q == "TL":
        votos_vip += 1
    elif frontal_q == "TR":
        votos_hik += 1

    if votos_vip == 0 and votos_hik == 0:
        return  # nem interna nem frontal localizadas — mantém o que veio (fallback)

    if votos_vip >= votos_hik:
        layout_enum, ordem = (
            "vip_intelbras_2x2",
            {"TL": "frontal", "TR": "lateral_direita", "BL": "interna", "BR": "traseira_esq"},
        )
        fab = "VIP"
    else:
        layout_enum, ordem = (
            "hikvision_2x2",
            {"TL": "interna", "TR": "frontal", "BL": "traseira_esq", "BR": "lateral_direita"},
        )
        fab = "Hikvision"

    cm.layout_detectado = layout_enum  # type: ignore[assignment]
    cm.fabricante_provavel = fab
    # Confiança proporcional à concordância das âncoras (1 ou 2 votos).
    derivada = 0.95 if (votos_vip == 2 or votos_hik == 2) else 0.75
    cm.confianca_layout = max(cm.confianca_layout, derivada)
    # Completa quadrantes faltantes com a ordem canônica derivada.
    for q, cam in ordem.items():
        q = cast(QuadrantName, q)
        cam = cast(CameraName, cam)
        info = cm.quadrantes.get(q)
        if info is None or info.camera in ("desconhecido", "", None):
            cm.quadrantes[q] = QuadrantInfo(
                camera=cam, confianca=derivada, descricao="derivado_da_posicao"
            )
    log.info(
        "layout_discovery: derivado %s (fab=%s, votos vip=%d hik=%d, conf=%.2f) — binário forçado",
        layout_enum,
        fab,
        votos_vip,
        votos_hik,
        cm.confianca_layout,
    )


def _infer_layout_from_fabricante(cm: CameraMap) -> None:
    """Recupera casos `layout=desconhecido` quando o fabricante foi reconhecido.

    O gemini-2.5-flash frequentemente devolve `fabricante_provavel=Hikvision`
    com `confianca_layout>=0.7` mas `layout_detectado=desconhecido` — uma
    contradição que mandava o exame pro fallback v25 (detecta 0). Quando o
    fabricante bate no padrão canônico e a confiança é razoável, inferimos o
    enum e preenchemos os quadrantes na ordem oficial do fabricante.
    """
    if cm.layout_detectado != "desconhecido":
        return  # flash já resolveu, nada a fazer
    fab = (cm.fabricante_provavel or "").strip().lower()
    canon = _FAB_CANONICO.get(fab)
    if canon is None:
        return  # fabricante não-canônico (ex: "outro"/"desconhecido") — mantém fallback
    if cm.confianca_layout < 0.7:
        return  # confiança baixa demais pra inferir com segurança
    layout_enum, ordem = canon
    cm.layout_detectado = layout_enum  # type: ignore[assignment]
    # Só preenche quadrantes que o flash deixou vazio/desconhecido.
    for q, cam in ordem.items():
        q = cast(QuadrantName, q)
        cam = cast(CameraName, cam)
        info = cm.quadrantes.get(q)
        if info is None or info.camera in ("desconhecido", "", None):
            cm.quadrantes[q] = QuadrantInfo(
                camera=cam, confianca=cm.confianca_layout, descricao="inferido_do_fabricante"
            )
    log.info(
        "layout_discovery: inferido %s do fabricante=%s (conf=%.2f) — recuperado do fallback",
        layout_enum,
        cm.fabricante_provavel,
        cm.confianca_layout,
    )


def _load_discovery_prompt() -> str:
    if not DISCOVERY_PROMPT.exists():
        raise FileNotFoundError(
            f"Discovery prompt não encontrado em {DISCOVERY_PROMPT}. "
            "Verifique que o asset está no container."
        )
    return DISCOVERY_PROMPT.read_text(encoding="utf-8")


def _strip_json_fence(text: str) -> str:
    """Remove ```json ... ``` se o modelo desobedeceu e devolveu com fence."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def _parse_response(raw: str) -> CameraMap:
    """Parsing tolerante a malformações leves. Erro vira CameraMap desconhecido."""
    cm = CameraMap(raw_response=raw)
    try:
        clean = _strip_json_fence(raw)
        data = json.loads(clean)
    except Exception as e:
        log.warning("layout_discovery: JSON inválido (%s) — devolvendo desconhecido", e)
        return cm

    cm.layout_detectado = data.get("layout_detectado", "desconhecido")  # type: ignore[assignment]
    cm.confianca_layout = float(data.get("confianca_layout") or 0.0)
    cm.fabricante_provavel = str(data.get("fabricante_provavel") or "desconhecido")

    quad_raw = data.get("quadrantes") or {}
    for q in ("TL", "TR", "BL", "BR"):
        info_raw = quad_raw.get(q) or {}
        cm.quadrantes[q] = QuadrantInfo(  # type: ignore[index]
            camera=info_raw.get("camera", "desconhecido"),
            confianca=float(info_raw.get("confianca") or 0.0),
            descricao=str(info_raw.get("descricao") or ""),
        )
    return cm


def discover_layout(
    gs_uri: str,
    *,
    project_id: str | None = None,
    location: str | None = None,
    model_name: str = "gemini-2.5-flash",
    # 16384 (não 4096): gemini-2.5-flash é modelo THINKING e os tokens de
    # raciocínio contam dentro do max_output_tokens. Com 4096 o thinking
    # consumia quase tudo e o JSON truncava no meio ("Unterminated string"),
    # derrubando TODA análise pro fallback v25. Validado 07/06/2026.
    max_output_tokens: int = 16384,
    max_tentativas: int = 3,
) -> CameraMap:
    """Wrapper com retry — o gemini-2.5-flash é instável nessa tarefa (varia
    entre `conf=0.0 desconhecido` e `conf=0.95 Hikvision` pro MESMO vídeo).
    Roda até `max_tentativas` vezes e devolve o primeiro resultado `confiavel`
    (ou o de maior confiança se nenhum passar). Custo por tentativa ~$0.01.
    """
    import random
    import time as _time

    melhor: CameraMap | None = None
    for tentativa in range(1, max_tentativas + 1):
        cm = _discover_layout_once(
            gs_uri,
            project_id=project_id,
            location=location,
            model_name=model_name,
            max_output_tokens=max_output_tokens,
        )
        if cm.confiavel:
            if tentativa > 1:
                log.info(
                    "layout_discovery: confiável na tentativa %d/%d", tentativa, max_tentativas
                )
            return cm
        if melhor is None or cm.confianca_layout > melhor.confianca_layout:
            melhor = cm
        log.info(
            "layout_discovery: tentativa %d/%d não-confiável (conf=%.2f) — %s",
            tentativa,
            max_tentativas,
            cm.confianca_layout,
            "tentando de novo" if tentativa < max_tentativas else "esgotado",
        )
        # Quando a falha foi um erro transitório do Vertex (429/503/timeout),
        # martelar de novo na hora só queima quota. Espera com backoff +
        # jitter antes da próxima tentativa. _discover_layout_once é fail-soft
        # (devolve CameraMap com raw_response="<exception> ..."), então
        # detectamos o transitório pela marca + mensagem.
        if tentativa < max_tentativas and _raw_parece_transitorio(cm.raw_response):
            wait = min(30.0, 2.0 * (2 ** (tentativa - 1)))
            wait += random.uniform(0, wait * 0.25)  # noqa: S311 — jitter de backoff, não cripto
            log.warning(
                "layout_discovery: erro transitório do Vertex — aguardando %.1fs antes de reenviar",
                wait,
            )
            _time.sleep(wait)
    return melhor if melhor is not None else CameraMap()


def _raw_parece_transitorio(raw_response: str | None) -> bool:
    """Heurística: o raw_response de uma tentativa fail-soft parece um erro
    transitório do Vertex (429/quota/503/timeout)? Usado só pra decidir backoff
    entre tentativas — nunca altera o resultado."""
    if not raw_response or "<exception>" not in raw_response:
        return False
    msg = raw_response.lower()
    return any(
        k in msg
        for k in (
            "resource exhausted",
            "resourceexhausted",
            "quota",
            "rate limit",
            "ratelimit",
            "too many requests",
            "429",
            "503",
            "unavailable",
            "deadline",
            "timeout",
            "timed out",
        )
    )


def _discover_layout_once(
    gs_uri: str,
    *,
    project_id: str | None = None,
    location: str | None = None,
    model_name: str = "gemini-2.5-flash",
    max_output_tokens: int = 16384,  # thinking-budget: ver nota em discover_layout
) -> CameraMap:
    """Roda o discovery contra um vídeo no GCS. Devolve `CameraMap`.

    O vídeo precisa estar no GCS (igual ao analyzer principal). Se passar
    caminho local, suba pro GCS antes — ou use `discover_layout_from_local`
    (não implementado; análise é GCS-only por design).

    Esta função NÃO levanta exceção em falha do modelo — devolve um
    `CameraMap` com `layout_detectado='desconhecido'` e `confianca_layout=0`.
    Caller deve checar `cm.confiavel` antes de seguir.
    """
    import time

    import vertexai
    from vertexai.generative_models import GenerationConfig, GenerativeModel, Part

    # VERTEX_PROJECT primeiro — é onde o Gemini roda (valbot-497920). GCP_PROJECT
    # e GOOGLE_CLOUD_PROJECT apontam pro projeto ANTIGO (308f1fa8) que tem billing
    # negado ("dunning deny") e causava 403 intermitente no layout discovery,
    # mandando exames pro fallback v25. Esta ordem alinha o discovery com o
    # analyzer principal (gemini_analyzer usa VERTEX_PROJECT).
    project = (
        project_id
        or os.environ.get("VERTEX_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
    )
    loc = location or os.environ.get("VERTEX_LOCATION") or "global"
    if not project:
        raise RuntimeError("GCP_PROJECT / GOOGLE_CLOUD_PROJECT não setado no env")

    log.info(
        "layout_discovery: vertexai.init project=%s location=%s model=%s gs=%s",
        project,
        loc,
        model_name,
        gs_uri,
    )
    vertexai.init(project=project, location=loc)

    system = _load_discovery_prompt()
    model = GenerativeModel(model_name, system_instruction=system)

    video_part = Part.from_uri(gs_uri, mime_type="video/mp4")
    start = time.monotonic()
    try:
        response = model.generate_content(
            [
                video_part,
                "Identifique o layout 2x2 deste vídeo de exame. Responda apenas "
                "com o JSON especificado no system prompt. As `descricao` de cada "
                "quadrante devem ter NO MÁXIMO 6 palavras (ex: 'volante e candidato' "
                "ou 'via à frente') — descrições longas truncam o JSON.",
            ],
            generation_config=GenerationConfig(
                response_mime_type="application/json",
                response_schema=_LAYOUT_SCHEMA,
                temperature=0.0,
                max_output_tokens=max_output_tokens,
            ),
        )
    except Exception as e:
        log.warning("layout_discovery: chamada Gemini falhou (%s)", e)
        return CameraMap(raw_response=f"<exception> {e}")

    elapsed = time.monotonic() - start
    raw = (response.text or "").strip()
    cm = _parse_response(raw)
    # 1º: deriva VIP/HIK da posição das câmeras (binário forçado — só 2 modelos).
    _derive_layout_from_quadrantes(cm)
    # 2º: se ainda desconhecido, tenta inferir do label de fabricante do flash.
    _infer_layout_from_fabricante(cm)
    cm.elapsed_s = round(elapsed, 2)

    # Cost = total_tokens × price per token. Tokens podem vir no usage_metadata.
    try:
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
            output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
            # Gemini 2.5 Flash preço público aprox.: $0.075/M in + $0.30/M out.
            # Constantes hardcoded — atualize se Google mudar pricing.
            in_cost = input_tokens * 0.075 / 1_000_000
            out_cost = output_tokens * 0.30 / 1_000_000
            cm.cost_usd = round(in_cost + out_cost, 6)
    except Exception:
        pass

    log.info(
        "layout_discovery: layout=%s conf=%.2f fab=%s elapsed=%ss cost=$%.6f",
        cm.layout_detectado,
        cm.confianca_layout,
        cm.fabricante_provavel,
        cm.elapsed_s,
        cm.cost_usd,
    )
    return cm
