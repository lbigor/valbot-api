"""
VLM validator — gatekeeper visual via LLaVA local (Ollama).

Camada final do pipeline: depois que o avaliador simbólico decide que um
evento R1020-G-a é candidato a `approved` (sinal forte + carro andou),
mostramos o crop da bbox pro LLaVA e perguntamos numa pergunta atômica
multiple-choice se aquilo é DE FATO uma placa Pare/semáforo, ou se é
faixa de pedestre / outdoor / outra coisa.

Filosofia central do projeto: "VLM nunca recebe imagem crua, só gráfico
simples + pergunta atômica + schema rígido". Aqui o "gráfico" é o crop
da região suspeita (não o frame inteiro), e a "pergunta atômica" é
escolha entre 4 letras.

Custo: ~3-8s por chamada em MPS Mac M-series. Modelo `llava:latest`
(LLaVA-1.6 Vicuna 7B Q4_K_M, ~4.7GB), roda local via Ollama.

Uso CLI:
    .venv/bin/python -m tooling.vlm_validator --crop /tmp/valbot_review/X.png
    .venv/bin/python -m tooling.vlm_validator --crop X.png --model llava:13b
    .venv/bin/python -m tooling.vlm_validator --status      # checa Ollama+modelo

Uso programático:
    from tooling.vlm_validator import validar_crop
    res = validar_crop(Path("/tmp/.../foo.png"))
    # res = {"resposta": "b", "raw": "b - pedestrian crossing", "model": "llava:latest", "elapsed_s": 4.2}
"""

from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path
from typing import Literal

import httpx

OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llava:13b"

# Pergunta atômica em inglês — LLaVA é mais forte assim. As respostas
# vêm em inglês também, salvas como `raw` no motivo do voto pra debug.
PROMPT_PARE_GATEKEEPER = """Look at this image from a Brazilian street. There is a green rectangle marking a region.

Inside the green rectangle, what do you see? Choose ONE:

(a) A red octagonal STOP/PARE sign on a pole, OR a traffic light
(b) White stripes painted on the road (zebra crossing for pedestrians)
(c) A wall, building, billboard, fence, vehicle, or natural scenery
(d) Nothing clear or empty asphalt

Answer with the letter and a brief 5-word reason. Example: 'b - white zebra stripes on road'."""


Resposta = Literal["a", "b", "c", "d", "?"]


def ollama_status(timeout: float = 2.0) -> dict:
    """Confere se Ollama está rodando e quais modelos tem."""
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=timeout)
        r.raise_for_status()
        models = [m.get("name", "") for m in r.json().get("models", [])]
        return {"running": True, "models": models}
    except Exception as e:
        return {"running": False, "models": [], "error": str(e)}


def validar_crop(
    crop_path: Path,
    prompt: str = PROMPT_PARE_GATEKEEPER,
    model: str = DEFAULT_MODEL,
    timeout: float = 60.0,
) -> dict:
    """
    Manda crop pro Ollama+LLaVA. Retorna:
        {"resposta": "a|b|c|d|?", "raw": str, "model": str,
         "elapsed_s": float, "ok": bool, "error": str|None}

    Em caso de erro (Ollama off, timeout, parsing falhou), `ok=False` e
    `resposta="?"`. Cliente decide degradação graciosa.
    """
    crop_path = Path(crop_path)
    if not crop_path.exists():
        return {
            "resposta": "?",
            "raw": "",
            "model": model,
            "elapsed_s": 0.0,
            "ok": False,
            "error": f"crop não existe: {crop_path}",
        }

    img_bytes = crop_path.read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode()

    t0 = time.time()
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "images": [img_b64],
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 60,
                    "top_p": 0.1,
                },
            },
            timeout=timeout,
        )
        r.raise_for_status()
        body = r.json()
    except httpx.HTTPError as e:
        return {
            "resposta": "?",
            "raw": "",
            "model": model,
            "elapsed_s": round(time.time() - t0, 2),
            "ok": False,
            "error": f"http: {e!s}",
        }
    except Exception as e:
        return {
            "resposta": "?",
            "raw": "",
            "model": model,
            "elapsed_s": round(time.time() - t0, 2),
            "ok": False,
            "error": f"unknown: {e!s}",
        }

    raw = (body.get("response") or "").strip().lower()
    elapsed = round(time.time() - t0, 2)

    # Parse robusto: procura primeira letra a/b/c/d nas primeiras 16 chars,
    # ignorando markdown ("**a**"), parênteses ("(a)"), pontuação.
    resposta: Resposta = "?"
    head = raw[:16]
    for ch in head:
        if ch in "abcd":
            resposta = ch  # type: ignore[assignment]
            break

    return {
        "resposta": resposta,
        "raw": raw[:140],
        "model": model,
        "elapsed_s": elapsed,
        "ok": True,
        "error": None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crop", type=Path, help="caminho do crop PNG")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="modelo Ollama")
    ap.add_argument(
        "--status", action="store_true", help="só checa se Ollama está OK e tem modelo VLM"
    )
    ap.add_argument("--prompt", help="override do prompt (default = PARE gatekeeper)")
    args = ap.parse_args()

    if args.status:
        st = ollama_status()
        print(json.dumps(st, indent=2))
        if st["running"]:
            vlm_models = [
                m for m in st["models"] if "llava" in m.lower() or "moondream" in m.lower()
            ]
            print(
                f"\nVLMs disponíveis: {vlm_models or '(nenhum — rode `ollama pull llava:latest`)'}"
            )
        return

    if not args.crop:
        ap.error("forneça --crop <path> ou --status")

    res = validar_crop(args.crop, prompt=args.prompt or PROMPT_PARE_GATEKEEPER, model=args.model)
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
