"""Backend Vertex AI para análise de exame de direção via Gemini Pro.

A implementação usa **Vertex AI** (caminho suportado pelos créditos GCP) —
ver `docs/gemini_vertex_setup.md`. O modelo é definido por `VERTEX_MODEL`
(default `gemini-2.5-pro`, region `global`).

Fluxo:

    1.  Recebe o caminho de um vídeo local (ou já um `gs://` URI).
    2.  Faz upload para o bucket GCS do projeto se ainda for local.
    3.  Chama o modelo Gemini de `VERTEX_MODEL` (region `global`) com:
          - system prompt = preset v25 (`valbot-r1-vip-v25.md`).
          - user prompt   = `_build_user_prompt()` — explícito sobre layout
                             dinâmico das 4 câmeras, áudio + vídeo simultâneos
                             e schema JSON de saída.
          - vídeo via `Part.from_uri("gs://...")` — o vídeo INTEIRO, não
                             pré-amostrado por nós.
    4.  Normaliza a resposta no schema `tier_a/0.1` consumido pelo
        `src/reporting/adapter.py` e pelo frontend.

A chamada real ao Vertex consome créditos e exige autenticação ADC; rodar
`gcloud auth application-default login` antes do primeiro uso. O módulo
foi escrito para que `import` funcione mesmo sem `vertexai` instalado —
apenas as funções que chamam o Vertex de fato falham nesse caso, com
mensagem clara.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


# ============================================================================
# Configuração
# ============================================================================

PROJECT_ID = os.environ.get("VERTEX_PROJECT", "project-308f1fa8-a301-49e6-a69")
LOCATION = os.environ.get("VERTEX_LOCATION", "global")
MODEL_NAME = os.environ.get("VERTEX_MODEL", "gemini-2.5-pro")
GCS_BUCKET = os.environ.get("GCS_BUCKET", "valbot-prod")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRESET_DIR = PROJECT_ROOT / "tooling" / "bench_demo" / "presets"
# Override-able via env (VALBOT_PRESET) pra suportar build em ambientes legados
# que ainda referenciam o nome antigo do preset.
DEFAULT_PRESET = os.environ.get("VALBOT_PRESET", "v25/valbot-r1-vip-v25")

# Response schema obrigatório para preset v25 (Vertex valida no servidor).
# Garante que cada infração tenha id, cat, conf, tier, status preenchidos —
# evita o bug v25 onde Gemini emitia detecção com regra_id/gravidade null.
RESPONSE_SCHEMA_V25 = {
    "type": "object",
    "properties": {
        "audio_scan": {
            "type": "object",
            "properties": {
                "duracao_total_s": {"type": "number"},
                "janelas_varridas": {"type": "array", "items": {"type": "string"}},
                "falas_detectadas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ts": {"type": "number"},
                            "ator": {"type": "string"},
                            "fala": {"type": "string"},
                            "tom": {"type": "string"},
                        },
                        "required": ["ts", "ator", "fala"],
                    },
                },
                "ultimos_60s_ouvidos": {"type": "boolean"},
            },
            "required": ["duracao_total_s", "falas_detectadas", "ultimos_60s_ouvidos"],
        },
        "infracoes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "cat": {
                        "type": "string",
                        "enum": ["gravissima", "grave", "media", "leve", "etica"],
                    },
                    "ts_seconds": {"type": "integer"},
                    "ts_end_seconds": {"type": "integer"},
                    "conf": {"type": "number"},
                    "ev": {"type": "string"},
                    "ator": {"type": "string"},
                    "tier": {"type": "string", "enum": ["A", "B"]},
                    "status": {
                        "type": "string",
                        "enum": ["avaliado"],
                    },
                },
                "required": ["id", "cat", "ts_seconds", "conf", "ev", "tier", "status"],
            },
        },
        "pts": {"type": "integer"},
        "res": {"type": "string", "enum": ["aprovado", "reprovado"]},
    },
    "required": ["audio_scan", "infracoes", "pts", "res"],
}

# Response schema v26-lean (modular CTB + MBEDV). IDs Art. XXX ou MBEDV-MEC-*.
RESPONSE_SCHEMA_V26 = {
    "type": "object",
    "properties": {
        "categoria": {"type": "string", "enum": ["A", "B", "C", "D", "E"]},
        "video": {
            "type": "object",
            "properties": {
                "duration_s": {"type": "number"},
                "audio_quality_flag": {"type": "string"},
            },
        },
        "candidato": {
            "type": "object",
            "properties": {"categoria": {"type": "string"}},
        },
        "descricao_video": {"type": "string"},
        "eventos_observados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ts_seconds": {"type": "number"},
                    "descricao_curta": {"type": "string"},
                    "categoria_temporal": {"type": "string"},
                },
                "required": ["ts_seconds", "descricao_curta"],
            },
        },
        "aprovado": {"type": "boolean"},
        "pontuacao_total": {"type": "integer"},
        "infracoes_detectadas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "ts_seconds": {"type": "number"},
                    "ts_end_seconds": {"type": "number"},
                    "descricao": {"type": "string"},
                    "conduta_pontuada": {"type": "string"},
                    "evidencia_visual": {"type": "string"},
                    "evidencia_audio": {"type": "string"},
                    "canal_evidencia": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confianca": {"type": "number"},
                    "status": {"type": "string"},
                    "gravidade": {
                        "type": "string",
                        "enum": ["leve", "media", "grave", "gravissima"],
                    },
                    "pontuacao": {"type": "integer"},
                    "verificacao_examinador": {"type": "string"},
                },
                "required": [
                    "id",
                    "ts_seconds",
                    "descricao",
                    "confianca",
                    "status",
                    "gravidade",
                    "pontuacao",
                ],
            },
        },
        "infracoes_avaliadas": {"type": "array", "items": {"type": "string"}},
        "observacoes_conduta": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string"},
                    "ts_seconds": {"type": "number"},
                    "evidencia": {"type": "string"},
                    "confianca": {"type": "number"},
                },
                "required": ["tipo", "ts_seconds", "evidencia"],
            },
        },
        "escopo_avaliado": {"type": "array", "items": {"type": "string"}},
        "catalog_version": {"type": "string", "enum": ["v26"]},
        "rejected": {"type": "boolean"},
        "rejection_reason": {"type": "string"},
    },
    "required": [
        "categoria",
        "descricao_video",
        "aprovado",
        "pontuacao_total",
        "infracoes_detectadas",
        "catalog_version",
        "rejected",
    ],
}

# Câmeras fixas presentes em TODOS os vídeos do valbot — fonte da verdade:
# `src/rubrics/taxonomia.py:Camera`. A ordem nos quadrantes 2x2 varia por
# fabricante (VIP, Hikvision, terceiro), mas o conjunto é sempre o mesmo.
QUADRANTES: tuple[str, ...] = ("TL", "TR", "BL", "BR")
CAMERAS_FIXAS: tuple[str, ...] = (
    "frontal",
    "lateral_direita",
    "interna",
    "traseira_esq",
)


# Preço Vertex AI Gemini 3.1 Pro Preview (USD por 1M tokens).
# Tier 1: ≤200K tokens de contexto. Tier 2: >200K tokens.
# Vídeo: ~258 tokens/segundo @ 1fps. Áudio: ~32 tokens/segundo.
# Fonte: https://cloud.google.com/vertex-ai/generative-ai/pricing
GEMINI_PRICING = {
    "gemini-3.1-pro-preview": {
        "input_per_1m_tier1": 1.25,
        "input_per_1m_tier2": 2.50,
        "output_per_1m_tier1": 5.00,
        "output_per_1m_tier2": 10.00,
        "tier_threshold": 200_000,
    },
    "gemini-2.5-pro": {
        "input_per_1m_tier1": 1.25,
        "input_per_1m_tier2": 2.50,
        "output_per_1m_tier1": 5.00,
        "output_per_1m_tier2": 10.00,
        "tier_threshold": 200_000,
    },
    # Flash — usado no gate barato de categoria B (1-2 frames).
    "gemini-2.5-flash": {
        "input_per_1m_tier1": 0.15,
        "input_per_1m_tier2": 0.30,
        "output_per_1m_tier1": 0.60,
        "output_per_1m_tier2": 1.20,
        "tier_threshold": 200_000,
    },
}


def _compute_cost_usd(model_name: str, prompt_tokens: int, output_tokens: int) -> dict:
    """Calcula custo USD a partir dos tokens reportados por Vertex.

    Devolve um dict com tokens de input/output, breakdown de preço e total.
    Tolera modelo desconhecido (devolve usd=None) pra não estourar a chamada.
    """
    price = GEMINI_PRICING.get(model_name)
    if not price:
        return {
            "prompt_tokens": prompt_tokens,
            "output_tokens": output_tokens,
            "total_tokens": prompt_tokens + output_tokens,
            "model": model_name,
            "usd": None,
            "note": f"sem tabela de preço para {model_name}",
        }
    total = prompt_tokens + output_tokens
    use_tier2 = total > price["tier_threshold"]
    input_rate = price["input_per_1m_tier2"] if use_tier2 else price["input_per_1m_tier1"]
    output_rate = price["output_per_1m_tier2"] if use_tier2 else price["output_per_1m_tier1"]
    input_usd = prompt_tokens * input_rate / 1_000_000
    output_usd = output_tokens * output_rate / 1_000_000
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "model": model_name,
        "tier": "tier2" if use_tier2 else "tier1",
        "input_usd": round(input_usd, 6),
        "output_usd": round(output_usd, 6),
        "usd": round(input_usd + output_usd, 6),
        "rates_per_1m": {"input": input_rate, "output": output_rate},
    }


def gate_categoria_b(
    gs_uri: str,
    *,
    project_id: str | None = None,
    location: str | None = None,
    model_name: str = "gemini-2.5-flash",
    start_s: int = 90,
    clip_s: int = 12,
) -> dict:
    """GATE BARATO de categoria B — olha um trecho do MEIO do vídeo (onde o
    candidato já está dirigindo) e decide se é um exame prático de direção
    CATEGORIA B. Custo ~US$0,001 vs ~US$0,07 do pipeline completo.

    IMPORTANTE: amostra a partir de `start_s` (default 30s), NÃO o início — os
    primeiros segundos costumam ser cena estática (carro parado, examinador
    preparando), o que fazia o gate rejeitar exames reais como "não é exame".

    Usa o SDK novo `google-genai` (suporta VideoMetadata; o vertexai clássico
    não suporta clipe). FAIL-OPEN: qualquer erro → is_cat_b=True (nunca bloqueia
    um vídeo legítimo por falha do gate).

    Retorna: {is_cat_b, confianca, motivo, cost_usd, tokens_in, tokens_out,
    elapsed_s, model, [erro]}.
    """
    import re as _re

    t0 = time.monotonic()
    fail_open = {
        "is_cat_b": True,
        "confianca": 0.0,
        "motivo": "",
        "cost_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "elapsed_s": 0.0,
        "model": model_name,
        "erro": True,
    }
    try:
        from google import genai  # type: ignore[import-not-found]
        from google.genai import types  # type: ignore[import-not-found]

        proj = project_id or PROJECT_ID
        loc = location or os.environ.get("VERTEX_LOCATION", "global")
        client = genai.Client(vertexai=True, project=proj, location=loc)
        # Recortes de frames ao LONGO do vídeo (início/meio/depois) — não só o
        # começo (que costuma ser cena parada). Robusto a abertura estática.
        offsets = [10, 40, 75]
        win = max(2, clip_s // 3)
        parts = [
            types.Part(
                file_data=types.FileData(file_uri=gs_uri, mime_type="video/mp4"),
                video_metadata=types.VideoMetadata(
                    start_offset=f"{off}s", end_offset=f"{off + win}s"
                ),
            )
            for off in offsets
        ]
        prompt = (
            "As imagens acima são RECORTES de momentos diferentes de UM vídeo de exame "
            "veicular. Decida se é um EXAME PRÁTICO DE DIREÇÃO da CATEGORIA B (automóvel "
            "de passeio, normalmente com VÁRIAS câmeras do veículo — interna mostrando o "
            "candidato ao volante, frontal/laterais mostrando a via). "
            "Se QUALQUER recorte mostrar claramente um carro de exame, é categoria B. "
            "REJEITE (is_cat_b=false) APENAS se tiver CERTEZA de que NÃO é carro: "
            "motocicleta (cat A), caminhão/ônibus (C/D/E). Na DÚVIDA (cena parada, sem "
            "movimento, tela preta, imagem ruim), responda is_cat_b=TRUE — a análise "
            "completa decide depois. Responda SOMENTE em JSON: "
            '{"is_cat_b": true|false, "confianca": 0.0-1.0, "motivo": "frase curta"}'
        )
        schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "is_cat_b": types.Schema(type=types.Type.BOOLEAN),
                "confianca": types.Schema(type=types.Type.NUMBER),
                "motivo": types.Schema(type=types.Type.STRING),
            },
            required=["is_cat_b", "confianca", "motivo"],
        )
        resp = client.models.generate_content(
            model=model_name,
            contents=[*parts, prompt],
            # Flash liga "thinking" por padrão (consome tokens de saída antes do
            # JSON). Este SDK (1.2.0) não deixa desligar via ThinkingConfig, então
            # damos folga no orçamento de saída pra caber thinking + JSON. Saída do
            # Flash é barata (~US$0,60/1M), o custo total segue ~US$0,001.
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.0,
                max_output_tokens=2048,
            ),
        )
        txt = (getattr(resp, "text", None) or "").strip()
        m = _re.search(r"\{.*\}", txt, _re.S)
        data = json.loads(m.group(0)) if m else {}
        um = getattr(resp, "usage_metadata", None)
        pin = int(getattr(um, "prompt_token_count", 0) or 0)
        pout = int(getattr(um, "candidates_token_count", 0) or 0)
        cost = _compute_cost_usd(model_name, pin, pout)
        return {
            "is_cat_b": bool(data.get("is_cat_b", True)),
            "confianca": float(data.get("confianca", 0) or 0),
            "motivo": str(data.get("motivo", ""))[:200],
            "cost_usd": cost.get("usd") or 0.0,
            "tokens_in": pin,
            "tokens_out": pout,
            "elapsed_s": round(time.monotonic() - t0, 2),
            "model": model_name,
        }
    except Exception as e:
        log.warning("gate_categoria_b falhou (%s) — fail-open (segue p/ análise)", e)
        fail_open["motivo"] = f"gate_erro: {e}"[:200]
        fail_open["elapsed_s"] = round(time.monotonic() - t0, 2)
        return fail_open


@dataclass(frozen=True)
class AnalysisOptions:
    """Opções da chamada Vertex. Defaults batem com o caminho recomendado."""

    project_id: str = PROJECT_ID
    location: str = LOCATION
    model_name: str = MODEL_NAME
    gcs_bucket: str = GCS_BUCKET
    preset: str = DEFAULT_PRESET
    rubrica_slug: str = "1020/2025"
    temperature: float = 0.1
    # 16384 (não 8192): gemini-2.5-pro é modelo THINKING e o raciocínio conta
    # dentro do max_output_tokens. Com 8192, exames com muitas infrações
    # truncavam o JSON ("Expecting ',' delimiter"). Alinha com o caminho S3
    # (VALBOT_MAX_OUTPUT_TOKENS=16384). Ceiling não custa se não usado.
    max_output_tokens: int = 16384
    # Anotações do examinador presencial (training_annotations do upload.json).
    # Quando preenchido, vira "ANOTAÇÕES DE REFERÊNCIA" no user_prompt — o
    # modelo verifica cada timestamp com independência (concorda/discorda/
    # sem_evidencia), não copia cego como infração detectada.
    training_annotations: list[dict] | None = None
    # Categoria CNH do exame (A/B/C/D/E). Quando setada + use_modular_v26=True,
    # o analyzer compõe o system prompt via composer v26 com fragments por
    # câmera, em vez do prompt v25 monolítico.
    categoria: str | None = None
    # Quando True, ativa o pipeline 2-fase:
    #   1. Vertex Flash discover_layout(gs_uri) — descobre quem está em cada quadrante
    #   2. compose_system_prompt(categoria, camera_map) — gera prompt direcionado
    #   3. Vertex Pro com prompt modular
    # Fallback automático pro v25 monolítico se discovery não-confiável OU
    # categoria desconhecida OU preset v26 indisponível. Default False
    # (rollout gradual — ativar via env VALBOT_USE_MODULAR_V26=1).
    use_modular_v26: bool = False
    # Modelo do discovery (Flash é 17× mais barato que Pro — vide
    # src/analysis/layout_discovery.py docs)
    discovery_model: str = "gemini-2.5-flash"


# ============================================================================
# Construção dos prompts
# ============================================================================


def _load_preset(preset: str) -> str:
    """Carrega o markdown do preset (sem extensão na chave)."""
    path = PRESET_DIR / f"{preset}.md"
    if not path.exists():
        raise FileNotFoundError(f"Preset não encontrado em {path}. Verifique o argumento `preset`.")
    return path.read_text(encoding="utf-8")


def _bloco_matriz(categoria: str | None) -> tuple[str, str | None]:
    """Monta o bloco da MATRIZ versionada (tabela exam_rules) + a instrução de
    LISTA FECHADA de códigos, que vira a ÚNICA fonte de códigos de infração.

    A Matriz (`backend.matriz.prompt_builder.construir_bloco`) lê as regras
    vigentes de `exam_rules` e devolve (texto, versao). Aqui envelopamos esse
    texto com a regra dura: a IA só pode emitir códigos `artigo_ctb` que
    aparecem nos cabeçalhos `### Art. ...` abaixo — no formato EXATO da Matriz —
    e NUNCA inventar códigos fora dela (nada de `MBEDV-MEC-*`, `MBEDV-estol`,
    `R1020-*`, `Art. 185-I` com hífen, etc).

    Devolve (texto_do_bloco_com_instrucao, matriz_versao). Em caso de falha
    (sem banco/seed) devolve ("", None) — o caller segue sem o bloco, mas loga.
    """
    from backend.matriz import prompt_builder

    bloco, versao = prompt_builder.construir_bloco(categoria)
    instrucao = (
        "═══════════════════════════════════════════════════════════════\n"
        "FONTE ÚNICA E FECHADA DE CÓDIGOS DE INFRAÇÃO — MATRIZ NACIONAL\n"
        f"(versão {versao})\n"
        "═══════════════════════════════════════════════════════════════\n\n"
        "A lista de artigos abaixo é a MATRIZ vigente e é a ÚNICA fonte\n"
        "autorizada de códigos de infração. REGRAS INVIOLÁVEIS sobre códigos:\n\n"
        "  1. LISTA FECHADA: o campo `id` de cada item em `infracoes_detectadas`\n"
        "     e em `infracoes_avaliadas` DEVE ser EXATAMENTE um dos códigos\n"
        "     `artigo_ctb` que aparecem nos cabeçalhos `### Art. ...` da Matriz\n"
        "     abaixo. Se uma conduta que você observou NÃO corresponde a nenhum\n"
        "     artigo da Matriz, NÃO a reporte como infração — no máximo descreva\n"
        "     em `observacoes_conduta` (sem `id` de infração).\n\n"
        "  2. FORMATO CANÔNICO EXATO: copie o código LITERALMENTE como está no\n"
        "     cabeçalho da Matriz, incluindo pontuação e vírgulas. Ex.: use\n"
        "     `Art. 185, I` (com vírgula e espaço), NUNCA `Art. 185-I`,\n"
        "     `Art. 185 I`, `185/I` ou variações. Use `Art. 169`, não `169`.\n\n"
        "  3. PROIBIDO INVENTAR: jamais use códigos que não estejam na Matriz —\n"
        "     nada de `MBEDV-MEC-freio-mao`, `MBEDV-estol`, `MBEDV-*`,\n"
        "     `R1020-X-y`, nem códigos 'aproximados'. Não existe código fora\n"
        "     desta lista.\n\n"
        "  4. Cada artigo abaixo traz as condutas que PONTUAM e as que NÃO\n"
        "     pontuam (exceções). Aplique-as RIGOROSAMENTE antes de marcar\n"
        '     `status: "detectada"`.\n\n'
        "───────────────────────────────────────────────────────────────\n\n"
    )
    return instrucao + bloco, versao


def _ids_da_rubrica(rubrica_slug: str) -> list[str]:
    """Retorna a lista ordenada de IDs (R1020-X-y) da rubrica.

    Importação adiada porque `src.rubrics.taxonomia` depende de paths que
    podem não estar disponíveis em todos os contextos de import.
    """
    from src.rubrics.taxonomia import CATALOGO, Rubrica

    if "1020" not in rubrica_slug:
        raise ValueError(
            f"Rubrica '{rubrica_slug}' não suportada. Pipeline avalia apenas 1020/2025."
        )
    return sorted(i.id for i in CATALOGO if i.rubrica == Rubrica.RES_1020_2025)


def _build_user_prompt(
    rubrica_slug: str,
    training_annotations: list[dict] | None = None,
) -> str:
    """Monta o user prompt que vai junto com o vídeo. Explícito em 3 frentes:

    1.  Layout dinâmico das 4 câmeras (FRONTAL, LATERAL_DIREITA, INTERNA,
        TRASEIRA_ESQ) — modelo descobre qual está em cada quadrante.
    2.  Análise simultânea de áudio + vídeo. Correlação entre os dois canais
        é obrigatória (ex: comando autorizado pelo examinador → não-infração).
    3.  Schema JSON estrito alinhado com `tier_a/0.1` (ts_seconds + canal_evidencia).

    `training_annotations` (opcional) são as anotações do EXAMINADOR PRESENCIAL
    do DETRAN do momento do exame, no formato `[{"timestamp": "HH:MM:SS",
    "anotacoes": "..."}]`. Quando presentes, são injetadas no fim do prompt
    como ÂNCORAS DE ATENÇÃO — o modelo deve analisar cada timestamp com
    cuidado extra, mas com independência: pode CONCORDAR, DISCORDAR ou
    REPORTAR_SEM_EVIDENCIA. Nunca copiar a anotação cegamente como infração.
    """
    ids = ", ".join(_ids_da_rubrica(rubrica_slug))
    annotations_section = _build_annotations_section(training_annotations)
    return f"""Você está auditando o vídeo INTEIRO de um exame prático de direção. \
Analise do segundo 0 até o último frame — não pule trechos, não economize processamento de áudio.

═══════════════════════════════════════════════════════════════
ETAPA 1 — IDENTIFIQUE O LAYOUT DAS CÂMERAS (FAÇA PRIMEIRO)
═══════════════════════════════════════════════════════════════

O vídeo é uma grade 2×2 com 4 quadrantes:
  TL = top-left      TR = top-right
  BL = bottom-left   BR = bottom-right

GARANTIA: existem SEMPRE EXATAMENTE estas 4 câmeras (lista FECHADA), uma em
cada quadrante (bijeção — sem repetir, sem faltar). Só a ORDEM nos
quadrantes varia entre fabricantes (VIP Intelbras, Hikvision, terceiro):

  1. "frontal"          — para-brisa / via à frente; semáforos, placas, faixas.
  2. "lateral_direita"  — janela/espelho direito; meio-fio, ciclista.
  3. "interna"          — candidato + volante + painel; mão, cinto, rosto.
  4. "traseira_esq"     — área traseira esquerda; mudança de faixa, baliza.

Heurísticas:
  • Vê volante de frente + rosto do candidato → "interna".
  • Paisagem em movimento horizontal estável (perspectiva motorista) → "frontal".
  • Retrovisor lateral em primeiro plano + meio-fio do passageiro → "lateral_direita".
  • Roda traseira esquerda + faixa atrás à esquerda → "traseira_esq".

Layouts conhecidos (use como referência, mas SEMPRE confirme olhando o vídeo):
  • VIP Intelbras: TL=frontal, TR=lateral_direita, BL=interna, BR=traseira_esq.
  • Hikvision:      TL=interna, TR=frontal, BL=traseira_esq, BR=lateral_direita.

═══════════════════════════════════════════════════════════════
ETAPA 2 — ANALISE OS DOIS CANAIS (VÍDEO + ÁUDIO)
═══════════════════════════════════════════════════════════════

REGRA INVIOLÁVEL DE ÁUDIO: Antes de devolver o JSON, você OBRIGATORIAMENTE
escutou o áudio do vídeo INTEIRO, segundo a segundo. Se o vídeo tem 5min
(300s), você ouviu os 300s. Áudio quieto NÃO é silêncio — aumente o ganho
mental e identifique falas em volume baixo. Frases sussurradas, irônicas
ou sarcásticas são frequentemente as mais críticas.

CANAIS:
  • VISÃO (4 quadrantes): comportamento do candidato, posicionamento do
    veículo, sinalização da via, faixas, semáforos, placas, mão no volante,
    cinto, espelhos, intermitentes/lanternas/farol.
  • ÁUDIO (faixa contínua): falas do EXAMINADOR ("vire à direita", "siga",
    "pare", "estacione"), comandos autorizando manobras, motor (ligado/
    desligado/calado/forçado), buzinas, frenagem brusca, impacto, pneu
    cantando, conversa do candidato, cinto travando ao puxar, intermitente
    clicando.

CORRELAÇÃO OBRIGATÓRIA entre os canais:
  • Examinador diz "siga" (áudio) com luz vermelha (visão) → NÃO é desobediência
    ao semáforo (comando autorizado). status="nao_detectada".
  • Motor calado em arrancada (áudio: ruído mecânico) + candidato no banco
    (interno) → falha de embreagem. R1020-M-c possível.
  • Intermitente clicando (áudio) sem mudança de faixa (visão) → falso
    intermitente, não conta.
  • Cinto NÃO clica ao puxar (áudio) + candidato visivelmente sem cinto
    (interna) → R1020-G-c.

═══════════════════════════════════════════════════════════════
ETAPA 3 — VERIFIQUE A COBERTURA INTEGRAL DO VÍDEO (MARCOS DE INÍCIO E FIM)
═══════════════════════════════════════════════════════════════

Um exame prático VÁLIDO é delimitado por dois marcos com o VEÍCULO PARADO:

  • MARCO DE INÍCIO: o EXAMINADOR dá a ordem de iniciar o teste (áudio —
    ex.: "pode iniciar", "pode começar", "vamos começar", "ligue e siga")
    com o veículo PARADO (motor pode estar ligado, mas SEM deslocamento).
    Esse é o segundo zero efetivo do exame.
  • MARCO DE FIM: o teste é encerrado com o veículo novamente PARADO —
    candidato imobiliza/estaciona e o examinador encerra (áudio — ex.:
    "pode desligar", "terminamos", "acabou", "pode estacionar").

Você DEVE localizar esses dois marcos e usá-los como PROVA de que assistiu
o vídeo INTEIRO (do início real ao fim real). Se NÃO encontrar a ordem de
início do examinador, ou NÃO encontrar a imobilização final, ou o vídeo
começar/terminar no meio de um deslocamento, então a captura está
INCOMPLETA/CORTADA — registre isso com franqueza no `comentario`.

REGRAS DESTA ETAPA:
  • Bloco APENAS informativo (sinal de integralidade da captura). NÃO gera
    pontos, NÃO altera aprovação, NÃO é infração.
  • `carro_parado` reflete o estado do veículo NO instante do marco: true se
    imobilizado, false se já em deslocamento (sinal de corte).
  • `comando_examinador` cita a FRASE LITERAL do examinador no marco de início.
  • `comentario` é um texto humano curto dizendo se o vídeo foi assistido
    integralmente e o que delimitou início/fim (ou o que faltou).

═══════════════════════════════════════════════════════════════
ETAPA 4 — AVALIE TODAS AS INFRAÇÕES DA RUBRICA {rubrica_slug}
═══════════════════════════════════════════════════════════════

IDS A AVALIAR (responda 1 por uma — mesmo que seja "nao_detectada"):
{ids}

Para cada infração detectada, cite no campo `evidence` qual quadrante e
câmera você usou (ex: "BL [interna]: candidato sem cinto desde 00:14").

═══════════════════════════════════════════════════════════════
FORMATO DE SAÍDA — JSON ESTRITO
═══════════════════════════════════════════════════════════════

{{
  "schema_version": "tier_a/0.1",
  "rubrica": "1020_2025",
  "layout": {{
    "TL": "<frontal|lateral_direita|interna|traseira_esq>",
    "TR": "...",
    "BL": "...",
    "BR": "...",
    "confianca_layout": 0.92,
    "fabricante_provavel": "VIP|HIK|outro|desconhecido"
  }},
  "duracao_estimada_s": 0,
  "cobertura_integral": {{
    "video_analisado_integralmente": true,
    "marco_inicio": {{
      "detectado": true,
      "ts_seconds": 12,
      "carro_parado": true,
      "comando_examinador": "pode iniciar, ligue o carro e siga",
      "evidence": "Áudio aos 00:12: examinador autoriza o início; interna mostra veículo imóvel."
    }},
    "marco_fim": {{
      "detectado": true,
      "ts_seconds": 298,
      "carro_parado": true,
      "evidence": "Aos 04:58 o candidato imobiliza o veículo e o examinador encerra ('pode desligar')."
    }},
    "comentario": "Vídeo analisado integralmente: examinador autorizou o início aos 00:12 com o veículo parado e o teste foi encerrado aos 04:58 com o veículo novamente parado."
  }},
  "infracoes_avaliadas": [
    {{
      "id": "R1020-G-a",
      "severidade": "gravissima|grave|media|leve",
      "pontos": 6,
      "status": "detectada|nao_detectada|pendente_revisao_humana",
      "ts_seconds": 119,
      "duracao_s": 2.3,
      "canal_evidencia": "visao|audio|ambos",
      "quadrante_origem": "TL|TR|BL|BR|null",
      "camera_origem": "<frontal|lateral_direita|interna|traseira_esq>|null",
      "evidence": "Descrição factual citando quadrante + câmera + áudio quando relevante.",
      "confidence": 0.85
    }}
  ]
}}

REGRAS DURAS:
  • Os 4 valores em layout (TL/TR/BL/BR) DEVEM ser exatamente o conjunto
    {{frontal, lateral_direita, interna, traseira_esq}}, sem repetir, sem faltar.
  • ts_seconds = inteiro, segundo absoluto desde o início do vídeo.
  • Para infração não detectada: status="nao_detectada", ts_seconds=null,
    duracao_s=null, evidence="".
  • Comando autorizado pelo examinador (áudio) → status="nao_detectada" e
    evidence cita a frase literal.
  • canal_evidencia="ambos" quando precisou correlacionar áudio E vídeo.
  • Se confianca_layout < 0.7, ainda emita o layout best-effort e marque
    fabricante_provavel="desconhecido".
  • cobertura_integral é OBRIGATÓRIO e sempre presente. Quando um marco não
    for encontrado: detectado=false, ts_seconds=null, carro_parado=false,
    e o `comentario` explica que a captura parece incompleta/cortada.
  • cobertura_integral NÃO pontua, NÃO entra em infracoes_* e NÃO altera
    pontuacao_total nem aprovado — é só sinal de integralidade da captura.

═══════════════════════════════════════════════════════════════
PRINCÍPIO SUPREMO E INVIOLÁVEL — IN DUBIO, NÃO APONTAR
═══════════════════════════════════════════════════════════════

Esta regra tem precedência sobre qualquer outra instrução deste prompt e
do system instruction. NA DÚVIDA, NÃO APONTAR.

Para cada infração, marque status="detectada" SOMENTE quando:
  (a) sua confidence numérica é >= 0.70, E
  (b) a evidência é concretamente verificável (áudio + vídeo quando o caso
      exige correlação), E
  (c) o timestamp está preciso em janela <= ±3 segundos, E
  (d) você não identificou comando autorizador do examinador no intervalo
      [t-3s, t+1s] que possa explicar a manobra.

Em QUALQUER dos seguintes cenários, NÃO use status="detectada" — use
status="nao_detectada" e deixe ts_seconds=null, evidence="":
  • Confidence estimada < 0.70.
  • Evidência apenas visual (ou apenas áudio) em caso que exige correlação.
  • Frame escuro, oclusão parcial, ou áudio mascarado por ruído.
  • Possível comando do examinador no entorno temporal.
  • Janela temporal imprecisa (não consegue cravar ts_seconds em ±3s).

PRINCÍPIO OPERACIONAL — "in dubio pro reo" automatizado:
O VALBOT é camada de TRIAGEM. Cada infração marcada como "detectada" gera
revisão humana de 2 níveis (N1 em 24h + N2 gerencial). Falsos positivos
consomem trabalho humano e podem afetar candidatos indevidamente. A
operação tolera muito melhor um falso negativo (capturado pelo examinador
presencial que permanece no fluxo) do que um falso positivo. Por design,
ERRE PARA O LADO DA OMISSÃO, NÃO DA ACUSAÇÃO.

Antes de finalizar o JSON: releia cada item com status="detectada" e
pergunte "Eu defenderia esta detecção em uma sessão de auditoria perante
a comissão de análise N1 do VALBOT?". Se "talvez não" ou "depende",
mude status para "nao_detectada" e limpe o evidence.

DEVOLVA SOMENTE O JSON. SEM TEXTO ANTES OU DEPOIS.
{annotations_section}"""


def _build_annotations_section(training_annotations: list[dict] | None) -> str:
    """Renderiza o bloco de referência com anotações do examinador presencial.

    Devolve string VAZIA quando não há anotações (não polui o prompt).
    Quando há, injeta âncoras de atenção que o modelo deve verificar com
    INDEPENDÊNCIA — concordar/discordar/reportar_sem_evidencia, nunca copiar.
    """
    if not training_annotations:
        return ""
    lines = [
        "",
        "═══════════════════════════════════════════════════════════════",
        "ANOTAÇÕES DE REFERÊNCIA — Examinador presencial DETRAN",
        "═══════════════════════════════════════════════════════════════",
        "",
        "O EXAMINADOR humano que estava no veículo registrou as observações",
        "abaixo NO MOMENTO do exame. Use como ÂNCORAS DE ATENÇÃO — analise",
        "cada timestamp listado com cuidado redobrado de evidência audio+visual.",
        "",
        "REGRAS de uso destas anotações:",
        "  1. NÃO copie cegamente como infração detectada. Analise com suas",
        "     próprias evidências (visual de 4 quadrantes + áudio segundo-a-segundo).",
        "  2. Se VOCÊ ENCONTROU evidência clara → marque infração normalmente.",
        "  3. Se ESCUTOU/VIU algo diferente do que examinador anotou → reporte",
        "     SUA conclusão. Você é a segunda opinião independente.",
        "  4. Se OLHOU mas não encontrou evidência → NÃO marque infração só",
        "     pra concordar com o examinador. Falsos positivos por simpatia",
        "     são piores que falsos negativos.",
        "",
        "Anotações do examinador (HH:MM:SS — observação):",
    ]
    for ann in training_annotations:
        ts = ann.get("timestamp") or "??:??:??"
        note = (ann.get("anotacoes") or ann.get("note") or "").strip()
        if not note:
            continue
        lines.append(f"  • {ts} — {note}")
    lines.append("")
    return "\n".join(lines)


# ============================================================================
# GCS upload (vídeo nunca passa pela VM em produção)
# ============================================================================


def _is_gcs_uri(uri: str | os.PathLike[str]) -> bool:
    return str(uri).startswith("gs://")


def upload_to_gcs(video_path: Path, bucket: str = GCS_BUCKET) -> str:
    """Sobe um vídeo local para GCS e devolve o `gs://` URI.

    Em produção, o frontend faz PUT direto no GCS via signed URL e essa
    função nem é chamada — o vídeo nem encosta na VM. Mas é útil para
    rodar análise local de vídeos de teste durante desenvolvimento.
    """
    try:
        from google.cloud import storage  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-storage não instalado. Rode `pip install google-cloud-storage`."
        ) from e

    client = storage.Client(project=PROJECT_ID)
    blob_name = f"uploads/{uuid.uuid4()}-{video_path.name}"
    blob = client.bucket(bucket).blob(blob_name)
    log.info("uploading %s to gs://%s/%s", video_path, bucket, blob_name)
    blob.upload_from_filename(str(video_path), content_type="video/mp4")
    return f"gs://{bucket}/{blob_name}"


# ============================================================================
# Chamada principal
# ============================================================================


def analyze_video(
    video: str | Path,
    rubrica_slug: str = "1020/2025",
    options: AnalysisOptions | None = None,
) -> dict:
    """Roda Gemini 3.x Pro Preview no vídeo INTEIRO (visão + áudio) e devolve
    um dict normalizado no schema `tier_a/0.1`.

    `video` pode ser um caminho local (será uploaded para GCS) ou já um
    `gs://` URI. A chamada lê o vídeo direto do GCS — Gemini decodifica
    internamente e amostra frames + áudio.
    """
    try:
        import vertexai  # type: ignore[import-not-found]
        from vertexai.generative_models import (  # type: ignore[import-not-found]
            GenerationConfig,
            GenerativeModel,
            Part,
        )
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "vertexai (google-cloud-aiplatform) não instalado. "
            "Rode `pip install google-cloud-aiplatform`."
        ) from e

    opts = options or AnalysisOptions(rubrica_slug=rubrica_slug)
    started = time.monotonic()

    if _is_gcs_uri(video):
        gs_uri = str(video)
        local_path = None
    else:
        local_path = Path(video)
        if not local_path.exists():
            raise FileNotFoundError(local_path)
        gs_uri = upload_to_gcs(local_path, opts.gcs_bucket)

    # PIPELINE 2-FASE (v26 modular) — só ativa quando use_modular_v26=True E
    # temos categoria. Caso contrário cai no caminho legado (system=v25
    # monolítico). Cost da discovery agregado em `cost.discovery_usd` do
    # result final.
    discovery_meta: dict | None = None
    used_modular = False
    system = ""
    matriz_versao: str | None = None
    if opts.use_modular_v26 and opts.categoria:
        try:
            from src.analysis.layout_discovery import discover_layout
            from src.analysis.prompt_composer import compose_system_prompt

            log.info(
                "v26 pipeline: descobrindo layout via %s (gs=%s, categoria=%s)",
                opts.discovery_model,
                gs_uri,
                opts.categoria,
            )
            cam_map = discover_layout(
                gs_uri,
                project_id=opts.project_id,
                location=opts.location,
                model_name=opts.discovery_model,
            )
            discovery_meta = {
                "layout_detectado": cam_map.layout_detectado,
                "confianca_layout": cam_map.confianca_layout,
                "fabricante_provavel": cam_map.fabricante_provavel,
                "quadrantes": {
                    q: {
                        "camera": info.camera,
                        "confianca": info.confianca,
                        "descricao": info.descricao,
                    }
                    for q, info in cam_map.quadrantes.items()
                },
                "cost_usd": cam_map.cost_usd,
                "elapsed_s": cam_map.elapsed_s,
            }
            if cam_map.confiavel:
                system = compose_system_prompt(opts.categoria, cam_map)
                # MATRIZ versionada (exam_rules) = fonte ÚNICA e FECHADA de
                # códigos de infração. Anexa o bloco das regras vigentes + a
                # instrução de lista fechada/formato canônico ao system prompt.
                try:
                    bloco_matriz, matriz_versao = _bloco_matriz(opts.categoria)
                    system = system + "\n\n" + bloco_matriz
                    log.info(
                        "v26 pipeline: MATRIZ %s anexada ao system (%d chars)",
                        matriz_versao,
                        len(bloco_matriz),
                    )
                except Exception as e:
                    log.exception(
                        "v26 pipeline: falha ao montar bloco da MATRIZ (%s) — system segue sem ele",
                        e,
                    )
                used_modular = True
                log.info(
                    "v26 pipeline: composer gerou prompt (%d chars) — usando modular",
                    len(system),
                )
            else:
                log.warning(
                    "v26 pipeline: layout não confiável (conf=%.2f, layout=%s) — "
                    "fallback pro preset v25 monolítico",
                    cam_map.confianca_layout,
                    cam_map.layout_detectado,
                )
        except Exception as e:
            log.exception("v26 pipeline falhou (%s) — fallback pro preset v25", e)

    if not used_modular:
        system = _load_preset(opts.preset)
        # Mesmo no fallback v25, a MATRIZ é a fonte fechada de códigos. Anexa o
        # bloco quando há categoria (sem categoria o preset v25 mantém seu
        # próprio catálogo de IDs legado).
        if opts.categoria:
            try:
                bloco_matriz, matriz_versao = _bloco_matriz(opts.categoria)
                system = system + "\n\n" + bloco_matriz
                log.info(
                    "v25 fallback: MATRIZ %s anexada ao system (%d chars)",
                    matriz_versao,
                    len(bloco_matriz),
                )
            except Exception as e:
                log.exception(
                    "v25 fallback: falha ao montar bloco da MATRIZ (%s) — system segue sem ele",
                    e,
                )

    user_prompt = _build_user_prompt(opts.rubrica_slug, opts.training_annotations)

    log.info(
        "vertexai.init project=%s location=%s model=%s",
        opts.project_id,
        opts.location,
        opts.model_name,
    )
    vertexai.init(project=opts.project_id, location=opts.location)
    model = GenerativeModel(opts.model_name, system_instruction=system)

    log.info(
        "calling Gemini with %s (preset=%s, rubrica=%s)", gs_uri, opts.preset, opts.rubrica_slug
    )
    video_part = Part.from_uri(gs_uri, mime_type="video/mp4")
    # response_schema condicional por modo do pipeline:
    #   - v25 monolítico → RESPONSE_SCHEMA_V25 (IDs custom R1020-*, infracoes flat)
    #   - v26-lean modular → RESPONSE_SCHEMA_V26 (IDs Art. XXX / MBEDV-MEC-*, com
    #     descricao_video + eventos_observados + observacoes_conduta separados)
    gen_config_kwargs = {
        "response_mime_type": "application/json",
        "temperature": opts.temperature,
        "max_output_tokens": opts.max_output_tokens,
    }
    if used_modular:
        gen_config_kwargs["response_schema"] = RESPONSE_SCHEMA_V26
        log.info("v26-lean: aplicando RESPONSE_SCHEMA_V26 (CTB + MBEDV)")
    else:
        gen_config_kwargs["response_schema"] = RESPONSE_SCHEMA_V25
        log.info("v25: aplicando RESPONSE_SCHEMA_V25 (legado CONTRAN 1.020)")

    # Redução de payload de vídeo: media_resolution LOW corta ~4x os tokens por
    # frame (de ~258 p/ ~66 @1fps), evitando o 400 "Request contains an invalid
    # argument" que o Vertex devolve em vídeos longos/grandes (~266MB médio). O
    # gate de categoria B já reduz via janelamento; a análise full não reduzia
    # nada — daí ~215 vídeos batendo 400 no backlog. Tunável por env
    # (VALBOT_MEDIA_RESOLUTION = low|medium|high|off; default low).
    _media_res = os.environ.get("VALBOT_MEDIA_RESOLUTION", "low").strip().lower()
    if _media_res not in ("", "off", "none"):
        try:
            from vertexai.generative_models import (  # type: ignore[import-not-found]
                MediaResolution,
            )

            _mr_map = {
                "low": MediaResolution.MEDIA_RESOLUTION_LOW,
                "medium": MediaResolution.MEDIA_RESOLUTION_MEDIUM,
                "high": MediaResolution.MEDIA_RESOLUTION_HIGH,
            }
            if _media_res in _mr_map:
                gen_config_kwargs["media_resolution"] = _mr_map[_media_res]
                log.info("aplicando media_resolution=%s (reduz payload de vídeo)", _media_res)
            else:
                log.warning("VALBOT_MEDIA_RESOLUTION=%r inválido — ignorado", _media_res)
        except Exception as e:  # SDK antigo sem MediaResolution — degrada sem reduzir
            log.warning("media_resolution indisponível neste SDK (%s) — segue sem", e)

    # Feature-detect final: SDKs antigos podem não aceitar o kwarg
    # media_resolution em GenerationConfig — nesse caso remove e segue, em vez de
    # quebrar a análise inteira com TypeError.
    try:
        gen_config = GenerationConfig(**gen_config_kwargs)
    except TypeError as e:
        if "media_resolution" in gen_config_kwargs:
            log.warning("GenerationConfig rejeitou media_resolution (%s) — removendo", e)
            gen_config_kwargs.pop("media_resolution", None)
            gen_config = GenerationConfig(**gen_config_kwargs)
        else:
            raise
    response = model.generate_content(
        [video_part, user_prompt],
        generation_config=gen_config,
    )

    raw_text = response.text  # type: ignore[attr-defined]
    elapsed = time.monotonic() - started
    log.info("Gemini response: %d chars in %.1fs", len(raw_text), elapsed)
    if used_modular:
        # FASE 0 do conserto v26: dump do JSON cru pra mapear o schema real
        # (o normalizador v26 é desenhado a partir disto). Marcador único pra grep.
        log.info("V26_RAW_DUMP_BEGIN %s V26_RAW_DUMP_END", raw_text[:12000])

    # Extrai usage_metadata (tokens reais cobrados) e calcula USD.
    # `usage_metadata` é um proto Vertex — campos prompt_token_count /
    # candidates_token_count. Se a SDK não expor (versão antiga), cai pra 0.
    prompt_tokens = 0
    output_tokens = 0
    try:
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
            output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
    except Exception:  # pragma: no cover — defesa, não bloqueia análise
        log.warning("não consegui extrair usage_metadata da resposta Gemini")
    cost = _compute_cost_usd(opts.model_name, prompt_tokens, output_tokens)
    cost["elapsed_s"] = round(elapsed, 2)
    log.info(
        "Gemini cost: %s tokens (in=%d out=%d) → $%s",
        cost["total_tokens"],
        prompt_tokens,
        output_tokens,
        cost.get("usd"),
    )

    raw = _parse_json_resilient(raw_text)
    if used_modular:
        # Pipeline v26 modular tem schema próprio (infracoes_detectadas como
        # objetos auto-descritivos, infracoes_avaliadas como IDs string, layout
        # vindo do discovery). Normalizador dedicado, sem depender do canon v25.
        result = _normalize_v26(
            raw,
            gs_uri=gs_uri,
            local_path=local_path,
            elapsed_s=elapsed,
            preset="v26/cat_" + (opts.categoria or "B"),
            model=opts.model_name,
            discovery_meta=discovery_meta,
        )
    else:
        result = _normalize(
            raw,
            gs_uri=gs_uri,
            local_path=local_path,
            rubrica_slug=opts.rubrica_slug,
            elapsed_s=elapsed,
            preset=opts.preset,
            model=opts.model_name,
        )
    # Agrega custo da discovery (se houve) — visível separado no cost final
    # pra contabilidade. O total fica em `cost.usd` (Pro) + `cost.discovery_usd`
    # (Flash).
    if discovery_meta is not None:
        cost["discovery_usd"] = discovery_meta.get("cost_usd", 0.0)
        cost["discovery_elapsed_s"] = discovery_meta.get("elapsed_s", 0.0)
        result["layout_discovery"] = discovery_meta
        result["pipeline_version"] = "v26" if used_modular else "v25_fallback_after_discovery"
    else:
        result["pipeline_version"] = "v25"
    # Rastreabilidade (spec §4.4): qual versão da MATRIZ alimentou o prompt.
    if matriz_versao:
        result["matriz_versao"] = matriz_versao
    result["cost"] = cost
    return result


# ============================================================================
# Parsing + normalização
# ============================================================================


def _parse_json_resilient(text: str) -> dict:
    """Extrai um JSON de uma resposta Gemini. O modelo às vezes envolve em
    fences ```json apesar do `response_mime_type` — esse parser tolera isso.
    """
    text = text.strip()
    if text.startswith("```"):
        # remove code fence opcional
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # tenta achar o objeto JSON no meio do texto
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))


_SEV_V26 = {
    "leve": "Leve",
    "media": "Média",
    "média": "Média",
    "grave": "Grave",
    "gravissima": "Gravíssima",
    "gravíssima": "Gravíssima",
}


def _map_infracao_v26(it: dict) -> dict:
    """Mapeia um item de `infracoes_detectadas` (schema v26) pro objeto de
    infração do schema tier_a/0.1 consumido por adapter/PDF/frontend."""
    grav = str(it.get("gravidade") or "").strip().lower()
    ts = it.get("ts_seconds")
    ts_end = it.get("ts_end_seconds")
    evid = " | ".join(s for s in (it.get("evidencia_visual"), it.get("evidencia_audio")) if s)
    canal = it.get("canal_evidencia")
    if isinstance(canal, list):
        canal = ",".join(canal)
    return {
        "id": it.get("id"),
        "descricao": it.get("descricao", ""),
        "severidade": _SEV_V26.get(grav, grav.capitalize() or "—"),
        "pontos": int(it.get("pontuacao") or 0),
        "tier": "A",
        "status": it.get("status") or "detectada",
        "timestamp_s": ts,
        "ts_seconds": ts,
        "duracao_s": (ts_end - ts)
        if (isinstance(ts_end, (int, float)) and isinstance(ts, (int, float)))
        else None,
        "canal_evidencia": canal or "visao",
        "quadrante_origem": it.get("quadrante_origem"),
        "camera_origem": it.get("camera_origem"),
        "evidence": evid,
        "confidence": float(it.get("confianca") or 0.0),
        "base_legal": it.get("id"),  # no v26 o próprio ID já é o artigo do CTB
        "conduta_pontuada": it.get("conduta_pontuada"),
        "verificacao_examinador": it.get("verificacao_examinador"),
        "cameras_relevantes": [],
    }


def _codigos_validos_matriz(categoria=None):
    """Conjunto FECHADO de codigos de infracao validos = artigos vigentes da
    Matriz (tabela `exam_rules`), no formato canonico `artigo_ctb` (ex:
    "Art. 185, I"). Reusa a MESMA fonte que alimenta o prompt
    (`prompt_builder._regras_vigentes`) — logo o que a IA "pode" emitir e o que
    a blindagem aceita sao, por construcao, identicos.

    Devolve (set_de_codigos, versao). Em caso de falha (sem banco/seed) devolve
    (set() vazio, None) — e o caller, ao ver set vazio, NAO descarta nada (nao
    da pra distinguir "codigo invalido" de "matriz indisponivel").
    """
    try:
        from backend.matriz import prompt_builder

        regras, versao = prompt_builder._regras_vigentes()
        codigos = {str(r.get("artigo_ctb")).strip() for r in regras if r.get("artigo_ctb")}
        return codigos, versao
    except Exception as e:
        log.warning("BLINDAGEM_MATRIZ_INDISPONIVEL: %s — nao vou descartar codigos", e)
        return set(), None


def _aplica_blindagem_matriz(detectadas, avaliados_ids, categoria=None):
    """BLINDAGEM (lista fechada): descarta qualquer infracao cujo `id` NAO exista
    na Matriz vigente (`exam_rules`). Garante zero codigo inventado mesmo se o
    modelo escapar da lista fechada do prompt. Loga cada descarte com marcador
    unico `BLINDAGEM_CODIGO_INVALIDO` (grep-avel).

    Devolve (detectadas_filtradas, avaliados_filtrados, descartados) onde
    `descartados` e a lista de ids invalidos descartados (com duplicatas
    contadas uma vez por ocorrencia, pra metrica).
    """
    validos, versao = _codigos_validos_matriz(categoria)
    if not validos:
        # Matriz indisponivel — fail-open: nao descarta (ja logado em helper).
        return detectadas, avaliados_ids, []

    descartados = []

    def _ok(cid):
        c = str(cid or "").strip()
        if c in validos:
            return True
        descartados.append(c)
        log.warning(
            "BLINDAGEM_CODIGO_INVALIDO: id=%r nao existe na Matriz vigente "
            "(versao=%s) — DESCARTADO",
            c,
            versao,
        )
        return False

    det_ok = [d for d in detectadas if _ok(d.get("id"))]
    aval_ok = [s for s in avaliados_ids if str(s or "").strip() in validos]
    if descartados:
        log.warning(
            "BLINDAGEM_RESUMO: %d codigo(s) invalido(s) descartado(s) de %d detectada(s) — %s",
            len(descartados),
            len(detectadas),
            descartados,
        )
    return det_ok, aval_ok, descartados


def _normalize_v26(
    raw: dict,
    gs_uri: str,
    local_path: Path | None,
    elapsed_s: float,
    preset: str,
    model: str,
    discovery_meta: dict | None,
) -> dict:
    """Normaliza a resposta do pipeline v26 modular pro schema tier_a/0.1.

    Diferenças vs v25 (`_normalize`):
      - `infracoes_detectadas` já vêm como objetos auto-descritivos (não
        re-derivamos do canon/taxonomia — usamos os campos do próprio item).
      - `infracoes_avaliadas` são IDs string (CTB) que o modelo olhou e
        descartou → viram `escopo_avaliado`.
      - layout vem do discovery (camera_map), não do corpo da resposta.
      - propaga `observacoes_conduta` (código de conduta MBEDV §4-5).
    """
    detectadas_raw = raw.get("infracoes_detectadas") or []
    detectadas = [_map_infracao_v26(i) for i in detectadas_raw if isinstance(i, dict)]

    # IDs avaliados-e-descartados (strings no v26) + os detectados → escopo.
    avaliados_ids = [s for s in (raw.get("infracoes_avaliadas") or []) if isinstance(s, str)]
    escopo = avaliados_ids + [d["id"] for d in detectadas if d.get("id")]
    # BLINDAGEM (lista fechada da Matriz): descarta qualquer id de infracao
    # que NAO exista em exam_rules ANTES de somar pontos/escopo. Roda aqui
    # (antes do calculo de pontuacao_total/aprovado) pra que codigo invalido
    # jamais infle a nota nem o veredito.
    detectadas, avaliados_ids, _codigos_invalidos = _aplica_blindagem_matriz(
        detectadas, avaliados_ids
    )
    escopo = avaliados_ids + [d["id"] for d in detectadas if d.get("id")]

    # Layout a partir do discovery.
    quad = (discovery_meta or {}).get("quadrantes") or {}
    layout = {q: (quad.get(q) or {}).get("camera", "desconhecida") for q in QUADRANTES}
    layout["confianca_layout"] = float((discovery_meta or {}).get("confianca_layout") or 0.0)
    layout["fabricante_provavel"] = (discovery_meta or {}).get(
        "fabricante_provavel", "desconhecido"
    )

    pontuacao_total = raw.get("pontuacao_total")
    if pontuacao_total is None:
        pontuacao_total = sum(d["pontos"] for d in detectadas)
    aprovado = raw.get("aprovado")
    if aprovado is None:
        aprovado = pontuacao_total <= 10

    # IMPERÍCIA REITERADA (MBEDV "condições mínimas de domínio do veículo"):
    # 3+ ocorrências da MESMA falta mecânica (MBEDV-MEC-*) reprova o candidato
    # mesmo que a soma fique ≤10. Ex: 4 estols (8pts) → reprovado por não
    # apresentar domínio mínimo. Regra determinística — não depende do modelo.
    from collections import Counter as _Counter

    _mec = _Counter(
        d.get("id")
        for d in detectadas
        if str(d.get("id") or "").startswith("MBEDV-MEC") and d.get("status") == "detectada"
    )
    _impericia = {mid: c for mid, c in _mec.items() if c >= 3}
    if _impericia and aprovado:
        aprovado = False
        _det = "; ".join(f"{mid} ×{c}" for mid, c in _impericia.items())
        raw.setdefault("rejection_reason", "impericia_reiterada")
        raw["rejection_details"] = (
            f"Reprovado por imperícia reiterada (condições mínimas de domínio "
            f"do veículo, MBEDV): {_det}. Soma de pontos ({pontuacao_total}) "
            f"ficaria ≤10, mas a repetição da mesma falta mecânica caracteriza "
            f"falta de domínio."
        )
        log.info("v26: imperícia reiterada → reprovado (%s)", _det)

    vid = raw.get("video") or {}
    return {
        "schema_version": "tier_a/0.1",
        "rubrica": "1020_2025",
        "video": {
            "filename": local_path.name if local_path else gs_uri.rsplit("/", 1)[-1],
            "hash": None,
            "duration_s": float(vid.get("duration_s") or 0.0),
            "fps": None,
            "size": None,
            "layout": layout,
            "audio_quality_flag": vid.get("audio_quality_flag"),
            "gs_uri": gs_uri,
        },
        # Sinal de integralidade da captura (marcos início/fim com carro parado).
        # Informativo — não pontua, não altera aprovado (constituição §V).
        "cobertura_integral": _normalize_cobertura(raw),
        "escopo_avaliado": escopo,
        "escopo_pendente_infraestrutura": [],
        "infracoes_avaliadas": detectadas,
        "infracoes_pendentes_infraestrutura": [],
        "infracoes_detectadas": detectadas,
        "observacoes_conduta": raw.get("observacoes_conduta") or [],
        "codigos_invalidos_descartados": _codigos_invalidos,
        "pontuacao_total": int(pontuacao_total or 0),
        "aprovado": bool(aprovado),
        "rejected": bool(raw.get("rejected", False)),
        "rejection_reason": raw.get("rejection_reason") or "",
        "rejection_details": raw.get("rejection_details") or "",
        "layout_disagreement": raw.get("layout_disagreement"),
        # CoT visível propagado pro laudo/dashboard (v26-lean).
        "descricao_video": raw.get("descricao_video") or "",
        "eventos_observados": raw.get("eventos_observados") or [],
        # Marca a rubrica usada — v26 = CTB + MBEDV (novo); v25 fica no histórico.
        "catalog_version": raw.get("catalog_version") or "v26",
        "elapsed_s": round(elapsed_s, 2),
        "engine": {"backend": "vertex_gemini", "model": model, "preset": preset},
    }


def _normalize_marco(raw_marco: object) -> dict:
    """Normaliza um marco (início/fim) de `cobertura_integral` pro shape estável.

    Tolerante a ausência/lixo: campo faltando vira o default 'não detectado'.
    `ts_seconds` é coagido para int quando numérico, senão null.
    """
    m = raw_marco if isinstance(raw_marco, dict) else {}
    ts = m.get("ts_seconds")
    try:
        ts = int(ts) if ts is not None else None
    except (TypeError, ValueError):
        ts = None
    return {
        "detectado": bool(m.get("detectado", False)),
        "ts_seconds": ts,
        "carro_parado": bool(m.get("carro_parado", False)),
        "comando_examinador": (m.get("comando_examinador") or "").strip(),
        "evidence": (m.get("evidence") or "").strip(),
    }


def _normalize_cobertura(raw: dict) -> dict:
    """Normaliza o bloco `cobertura_integral` (marcos de início/fim do exame).

    Sinal de integralidade da captura (a IA assistiu do início real ao fim
    real). É puramente INFORMATIVO — não soma pontos, não entra em infrações,
    não altera `aprovado` (constituição §V: integridade ≠ pontuação).

    Sempre devolve o bloco completo, mesmo quando o modelo o omite — assim o
    JSON de saída é estável pra quem consome (`comentario` deixa explícito).
    `video_analisado_integralmente` é derivado: só true quando ambos os marcos
    foram detectados COM o veículo parado, a menos que o modelo já o afirme.
    """
    cob = raw.get("cobertura_integral")
    cob = cob if isinstance(cob, dict) else {}
    inicio = _normalize_marco(cob.get("marco_inicio"))
    fim = _normalize_marco(cob.get("marco_fim"))
    derivado = (
        inicio["detectado"] and inicio["carro_parado"] and fim["detectado"] and fim["carro_parado"]
    )
    integral = cob.get("video_analisado_integralmente")
    integral = bool(integral) if isinstance(integral, bool) else derivado
    comentario = (cob.get("comentario") or "").strip()
    if not comentario:
        if integral:
            comentario = (
                "Cobertura integral confirmada: ordem de início do examinador "
                "com o veículo parado e encerramento com o veículo parado."
            )
        else:
            faltou = []
            if not (inicio["detectado"] and inicio["carro_parado"]):
                faltou.append("marco de início (ordem do examinador com carro parado)")
            if not (fim["detectado"] and fim["carro_parado"]):
                faltou.append("marco de fim (carro parado)")
            comentario = (
                "Cobertura integral NÃO confirmada — captura possivelmente "
                "incompleta/cortada. Faltou: " + "; ".join(faltou) + "."
            )
    return {
        "video_analisado_integralmente": integral,
        "marco_inicio": inicio,
        "marco_fim": fim,
        "comentario": comentario,
    }


def _normalize(
    raw: dict,
    gs_uri: str,
    local_path: Path | None,
    rubrica_slug: str,
    elapsed_s: float,
    preset: str,
    model: str,
) -> dict:
    """Converte a resposta crua do Gemini no schema `tier_a/0.1` consumido
    por `src/reporting/adapter.py` e pelo frontend.

    Garante:
      - `schema_version`, `rubrica`, `video.{filename, hash, duration_s, fps, layout}`.
      - `infracoes_avaliadas[]` com `id`, `descricao`, `severidade`, `pontos`,
        `tier`, `status`, `timestamp_s` (alias de ts_seconds), `evidence`, etc.
      - `escopo_avaliado`, `escopo_pendente_infraestrutura`, `infracoes_detectadas`.
    """
    from src.rubrics.taxonomia import CATALOGO, Rubrica

    # mapa id → metadados canônicos
    canon = {i.id: i for i in CATALOGO if i.rubrica == Rubrica.RES_1020_2025}

    # Layout vindo do Gemini, validado contra o conjunto fechado.
    raw_layout = raw.get("layout") or {}
    layout = {q: raw_layout.get(q, "desconhecida") for q in QUADRANTES}
    valores = [layout[q] for q in QUADRANTES if layout[q] in CAMERAS_FIXAS]
    layout_ok = len(set(valores)) == 4
    confianca_layout = float(raw_layout.get("confianca_layout") or 0.0)
    if not layout_ok:
        confianca_layout = min(confianca_layout, 0.5)
        log.warning(
            "Layout retornado pelo Gemini não cobre as 4 câmeras (got=%s)",
            valores,
        )
    layout["confianca_layout"] = confianca_layout
    layout["fabricante_provavel"] = raw_layout.get("fabricante_provavel", "desconhecido")

    # Infrações
    infracoes_avaliadas: list[dict] = []
    detectadas: list[dict] = []
    raw_infracoes = raw.get("infracoes_avaliadas") or []
    for item in raw_infracoes:
        rid = item.get("id")
        meta = canon.get(rid)
        if meta is None:
            log.warning("Gemini retornou ID desconhecido: %s — descartado", rid)
            continue
        ts = item.get("ts_seconds")
        if ts is None:
            ts = item.get("timestamp_s")
        canal_dependente_layout = item.get("quadrante_origem") in QUADRANTES
        status = item.get("status") or "pendente_revisao_humana"
        if not layout_ok and canal_dependente_layout and status == "detectada":
            log.info(
                "Layout incerto + %s depende de quadrante: rebaixando para revisão humana",
                rid,
            )
            status = "pendente_revisao_humana"

        normalized = {
            "id": rid,
            "descricao": meta.descricao,
            "severidade": meta.severidade.value,
            "pontos": meta.pontos,
            "tier": meta.tier.value,
            "status": status,
            "timestamp_s": ts,
            "ts_seconds": ts,  # alias mantido pro preset v25
            "duracao_s": item.get("duracao_s"),
            "canal_evidencia": item.get("canal_evidencia", "visao"),
            "quadrante_origem": item.get("quadrante_origem"),
            "camera_origem": item.get("camera_origem"),
            "evidence": item.get("evidence", ""),
            "confidence": float(item.get("confidence") or 0.0),
            "base_legal": meta.base_legal,
            "cameras_relevantes": [c.value for c in meta.cameras_relevantes],
        }
        infracoes_avaliadas.append(normalized)
        if status == "detectada":
            detectadas.append(normalized)

    pontuacao_total = sum(i["pontos"] for i in detectadas)

    return {
        "schema_version": "tier_a/0.1",
        "rubrica": "1020_2025",
        "video": {
            "filename": local_path.name if local_path else gs_uri.rsplit("/", 1)[-1],
            "hash": None,  # preenchido pelo wire-up de upload (Etapa 4)
            "duration_s": float(raw.get("duracao_estimada_s") or 0.0),
            "fps": None,
            "size": None,
            "layout": layout,
            "gs_uri": gs_uri,
        },
        # Sinal de integralidade da captura (marcos início/fim com carro parado).
        # Informativo — não pontua, não altera aprovado (constituição §V).
        "cobertura_integral": _normalize_cobertura(raw),
        "escopo_avaliado": [i["id"] for i in infracoes_avaliadas],
        "escopo_pendente_infraestrutura": [
            mid
            for mid, m in canon.items()
            if m.tier.value == "C" and mid not in {i["id"] for i in infracoes_avaliadas}
        ],
        "infracoes_avaliadas": infracoes_avaliadas,
        "infracoes_pendentes_infraestrutura": [],
        "infracoes_detectadas": detectadas,
        # Observações de conduta (MBEDV §4-5): sinais NÃO pontuáveis pra revisão
        # humana decidir penalidade (desacato/instabilidade/imperícia). Propagado
        # cru — não soma em pontuacao_total nem afeta aprovado.
        "observacoes_conduta": raw.get("observacoes_conduta") or [],
        "pontuacao_total": pontuacao_total,
        "aprovado": pontuacao_total <= 10,
        # Preserva campos de rejeição produzidos pelo gate de admissibilidade
        # (PASSO 0 do preset). Quando o Gemini decide que o vídeo não é exame
        # Cat B válido, ele retorna rejected=true + motivo + detalhes —
        # _normalize precisa propagar pra que a SPA exiba a tela de rejeição.
        "rejected": bool(raw.get("rejected", False)),
        "rejection_reason": raw.get("rejection_reason") or "",
        "rejection_details": raw.get("rejection_details") or "",
        "elapsed_s": round(elapsed_s, 2),
        "engine": {
            "backend": "vertex_gemini",
            "model": model,
            "preset": preset,
        },
    }
