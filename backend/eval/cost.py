"""Fonte ÚNICA de preço para estimar custo de chamadas ao Gemini (Vertex).

Puro e self-contained (NÃO importa src/analysis — o CD não sincroniza src/).
Usado pelo detector (custo de cada chamada) e pelo harness de avaliação.
"""

from __future__ import annotations

# Preço Vertex AI por 1M de tokens (USD). Contexto <= 200k tokens.
# Fonte: cloud.google.com/vertex-ai/generative-ai/pricing (Gemini 2.5 Pro).
# Mantido aqui como tabela única; atualizar quando o preço mudar.
GEMINI_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.5-pro": {"in": 1.25, "out": 10.0},
    "gemini-2.5-flash": {"in": 0.30, "out": 2.50},
}
_DEFAULT = {"in": 1.25, "out": 10.0}


def compute_cost_usd(model_name: str, prompt_tokens: int, output_tokens: int) -> dict:
    """Custo em USD de uma chamada, a partir das contagens de token.

    Devolve o detalhamento p/ auditoria. Modelo desconhecido cai no default
    (preço do Pro) — conservador, nunca subestima silenciosamente.
    """
    price = GEMINI_PRICING.get((model_name or "").strip().lower(), _DEFAULT)
    cin = (prompt_tokens or 0) * price["in"] / 1_000_000
    cout = (output_tokens or 0) * price["out"] / 1_000_000
    return {
        "usd": round(cin + cout, 6),
        "in_usd": round(cin, 6),
        "out_usd": round(cout, 6),
        "prompt_tokens": prompt_tokens or 0,
        "output_tokens": output_tokens or 0,
        "model": model_name,
        "preco_conhecido": (model_name or "").strip().lower() in GEMINI_PRICING,
    }


def custo_de_usage(model_name: str, usage_metadata: dict | None) -> dict:
    """Conveniência: extrai promptTokenCount/candidatesTokenCount do usageMetadata
    (formato REST do Vertex) e calcula o custo."""
    um = usage_metadata or {}
    return compute_cost_usd(
        model_name,
        um.get("promptTokenCount", 0),
        um.get("candidatesTokenCount", 0),
    )
