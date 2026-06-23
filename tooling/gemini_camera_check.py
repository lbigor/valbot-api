"""Validacao rapida do padrao DETRAN de 4 cameras via Gemini Flash.

Roda dentro do container valbot-api:
    docker exec valbot-api python /opt/valbot/tooling/gemini_camera_check.py <hash> [hash ...]
"""

import json
import os
import sys
import time

import vertexai
from vertexai.generative_models import GenerativeModel, Part

vertexai.init(
    project=os.environ.get("VERTEX_PROJECT", "project-308f1fa8-a301-49e6-a69"),
    location=os.environ.get("VERTEX_LOCATION", "global"),
)
model = GenerativeModel("gemini-3.1-pro-preview")  # único modelo confirmado em location=global

PROMPT = """TAREFA UNICA: validar se este video segue o padrao DETRAN.

PADRAO = grid 2x2 com 4 cameras:
  1. PAINEL/FRONTAL  - estrada a frente, painel/velocimetro
  2. LATERAL_DIREITA - retrovisor direito, pista lateral
  3. CAPO/EXTERNA    - vista externa apontando pro veiculo
  4. INTERNA         - habitaculo: candidato, volante, banco

Fabricantes aceitos: VIP Intelbras OU HIK Vision.

Olhe SO os primeiros 5 segundos. Nao analise infracoes nem audio.
SO valide o layout das cameras.

Devolva JSON:
{
  "tem_padrao_4_cameras": true|false,
  "layout_observado": {"TL":"...", "TR":"...", "BL":"...", "BR":"..."},
  "fabricante_provavel": "VIP"|"HIK"|"desconhecido",
  "confianca_layout": 0.0-1.0,
  "veredito": "homologado"|"nao_homologado",
  "motivo_curto": "<1 linha>"
}
DEVOLVA SO O JSON.
"""


def check_one(h: str) -> dict:
    t0 = time.monotonic()
    resp = model.generate_content(
        [
            Part.from_uri(uri=f"gs://valbot-prod/uploads/{h}/video.mp4", mime_type="video/mp4"),
            Part.from_text(PROMPT),
        ],
        generation_config={
            "temperature": 0.0,
            "max_output_tokens": 4096,
            "response_mime_type": "application/json",
        },
    )
    el = time.monotonic() - t0
    try:
        parsed = json.loads(resp.text)
    except Exception:
        parsed = {"raw": resp.text[:200], "parse_error": True}
    # Gemini às vezes devolve [{...}] em vez de {...} — normaliza.
    if isinstance(parsed, list):
        d = (
            parsed[0]
            if parsed and isinstance(parsed[0], dict)
            else {"parse_error": True, "raw_list": parsed}
        )
    elif isinstance(parsed, dict):
        d = parsed
    else:
        d = {"parse_error": True, "raw_type": type(parsed).__name__}
    u = getattr(resp, "usage_metadata", None)
    if u is not None:
        pt = int(getattr(u, "prompt_token_count", 0) or 0)
        ot = int(getattr(u, "candidates_token_count", 0) or 0)
        # gemini-3.1-pro-preview: $1.25/1M in + $5/1M out (tier1)
        d["_cost"] = round((pt * 1.25 + ot * 5.0) / 1_000_000, 5)
        d["_elapsed"] = round(el, 1)
    return d


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("uso: python gemini_camera_check.py <hash> [<hash> ...]", file=sys.stderr)
        return 2
    total = 0.0
    output_dir = "/opt/valbot/storage/camera_validation"
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception:
        output_dir = None

    summary = []
    for h in argv[1:]:
        try:
            d = check_one(h)
            cost = d.pop("_cost", 0)
            el = d.pop("_elapsed", 0)
            total += cost
            print(f"=== {h[:12]} ===")
            print(f"  veredito:    {d.get('veredito')}")
            print(f"  padrao 4cam: {d.get('tem_padrao_4_cameras')}")
            print(
                f"  fabricante:  {d.get('fabricante_provavel')} (conf {d.get('confianca_layout')})"
            )
            print(f"  layout:      {d.get('layout_observado')}")
            print(f"  motivo:      {d.get('motivo_curto')}")
            print(f"  cost ${cost} | {el}s")
            print()
            if output_dir:
                with open(f"{output_dir}/{h}.json", "w") as f:
                    json.dump(
                        {**d, "hash": h, "cost_usd": cost, "elapsed_s": el},
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
            summary.append({"hash": h, **d, "cost_usd": cost, "elapsed_s": el})
        except Exception as e:
            print(f"  {h[:12]}  ERRO: {e}\n")
            summary.append({"hash": h, "error": str(e)})
    if output_dir:
        with open(f"{output_dir}/_summary.json", "w") as f:
            json.dump(
                {"results": summary, "total_cost_usd": round(total, 4)},
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\nsalvo em {output_dir}/", file=sys.stderr)
    print(f"[total ${round(total, 4)}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
