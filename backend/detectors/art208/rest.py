"""Camada de rede do detector — ÚNICA que fala com o Vertex (REST).

Isolada de propósito: nos testes do CI é substituída por um call_fn fake, então
nada aqui roda no CI. Usa a API REST generateContent porque o google-genai do
container (1.2.0) não suporta videoMetadata.fps. NÃO importa src/analysis (o CD
não sincroniza src/) — é self-contained.
"""

from __future__ import annotations

import json
import os
import urllib.request


def adc_token() -> str:
    """Access token via metadata server da VM (ADC). Falha clara se ausente."""
    req = urllib.request.Request(
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/token",
        headers={"Metadata-Flavor": "Google"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 — metadata server (URL fixa)
        return json.load(r)["access_token"]


def vertex_generate_content(
    payload: dict,
    *,
    project_id: str | None = None,
    location: str | None = None,
    model_name: str = "gemini-2.5-pro",
    timeout_s: int = 900,
) -> dict:
    """POST generateContent no Vertex; devolve o JSON cru da resposta."""
    proj = project_id or os.environ["VERTEX_PROJECT"]
    loc = location or os.environ.get("VERTEX_LOCATION", "us-central1")
    url = (
        f"https://{loc}-aiplatform.googleapis.com/v1/projects/{proj}"
        f"/locations/{loc}/publishers/google/models/{model_name}:generateContent"
    )
    req = urllib.request.Request(  # noqa: S310 — endpoint Vertex (https fixo)
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {adc_token()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as r:  # noqa: S310
        return json.load(r)
