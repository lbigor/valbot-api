"""Funções PURAS do detector de Art. 208 — zero rede, zero import pesado.

É o coração testável: parse de timestamp, montagem do payload REST com
videoMetadata, agregação de janelas em veredito, custo. A chamada de rede vive
em rest.py e é injetada (call_fn) — no CI usa-se um fake.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from backend.eval import cost as _cost

_MMSS = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{1,2})")


def parse_mmss(s) -> int | None:
    """'1:23'->83, '0:05'->5, '1:02:03'->3723, 90->90. None se não parsear."""
    if isinstance(s, (int, float)):
        return int(s)
    m = _MMSS.search(str(s or ""))
    if not m:
        return None
    h = int(m.group(1) or 0)
    return h * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def fmt_offset(seg: int) -> str:
    """Formato de offset do videoMetadata: 12 -> '12s'."""
    return f"{max(0, int(seg))}s"


def janela_offsets(ts_seg: int, janela_s: int, dur_total: int | None = None) -> tuple[str, str]:
    """Janela [ts-janela, ts+janela] em offsets string, com clamp em 0 e no teto."""
    s0 = max(0, ts_seg - janela_s)
    s1 = ts_seg + janela_s
    if dur_total is not None:
        s1 = min(s1, dur_total)
    return fmt_offset(s0), fmt_offset(s1)


def montar_payload(
    gs_uri: str,
    prompt: str,
    *,
    fps: int,
    start_offset: str | None = None,
    end_offset: str | None = None,
    response_schema: dict | None = None,
    media_resolution: str = "MEDIA_RESOLUTION_LOW",
    max_output_tokens: int = 4096,
) -> dict:
    """Corpo REST de generateContent (Vertex) com vídeo + videoMetadata."""
    vm: dict = {"fps": fps}
    if start_offset is not None:
        vm["startOffset"] = start_offset
        vm["endOffset"] = end_offset
    gen: dict = {
        "temperature": 0,
        "responseMimeType": "application/json",
        "mediaResolution": media_resolution,
        "maxOutputTokens": max_output_tokens,
    }
    if response_schema:
        gen["responseSchema"] = response_schema
    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "fileData": {"fileUri": gs_uri, "mimeType": "video/mp4"},
                        "videoMetadata": vm,
                    },
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": gen,
    }


def _texto_da_resposta(resp_json: dict) -> str:
    return resp_json["candidates"][0]["content"]["parts"][0]["text"]


def parse_candidatos(resp_json: dict) -> list[dict]:
    """Extrai os candidatos do estágio 1; normaliza ts -> segundos ('ts_seg')."""
    data = json.loads(_texto_da_resposta(resp_json))
    out = []
    for c in data.get("candidatos") or []:
        seg = parse_mmss(c.get("ts"))
        if seg is not None:
            out.append({"ts": c.get("ts"), "ts_seg": seg, "tipo": c.get("tipo")})
    return out


def parse_veredito_janela(resp_json: dict) -> dict:
    """Veredito do estágio 2 de uma janela."""
    data = json.loads(_texto_da_resposta(resp_json))
    return {
        "houve_208": bool(data.get("houve_208")),
        "estado_visto": data.get("estado_visto"),
        "evidencia": data.get("evidencia_visual"),
        "confianca": float(data.get("confianca") or 0.0),
    }


@dataclass
class Evento208:
    ts_seg: int
    evidencia: str | None = None
    confianca: float = 0.0


def agregar_janelas(
    janelas: list[dict], *, limiar_confianca: float = 0.0
) -> tuple[bool, list[Evento208]]:
    """houve_208 = qualquer janela positiva com confiança >= limiar."""
    eventos = [
        Evento208(j.get("ts_seg", 0), j.get("evidencia"), j.get("confianca", 0.0))
        for j in janelas
        if j.get("houve_208") and float(j.get("confianca") or 0.0) >= limiar_confianca
    ]
    return (len(eventos) > 0, eventos)


def custo_da_resposta(resp_json: dict, model_name: str) -> dict:
    """Custo USD de uma resposta (delega o preço a backend.eval.cost)."""
    return _cost.custo_de_usage(model_name, resp_json.get("usageMetadata"))


@dataclass
class Resultado208:
    houve_208: bool
    eventos: list = field(default_factory=list)
    custo_usd: float = 0.0
    versao: str = ""
    n_candidatos: int = 0
    detalhe: dict = field(default_factory=dict)
