"""
gemini_test_suggestions.py — pede ao Gemini uma lista de tarefas de teste E2E
adicionais a partir de screenshots da SPA do VALBOT.

Roda DENTRO do container valbot-api (onde vertexai + ADC já estão wired).

Uso:
    docker exec valbot-api python /opt/valbot/tooling/gemini_test_suggestions.py \
        /opt/valbot/screenshots/*.png

Saída: JSON em stdout com lista de tarefas estruturadas.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import vertexai
from vertexai.generative_models import GenerativeModel, Part

PROJECT_ID = os.environ.get("VERTEX_PROJECT", "project-308f1fa8-a301-49e6-a69")
LOCATION = os.environ.get("VERTEX_LOCATION", "global")
MODEL_NAME = os.environ.get("VERTEX_MODEL", "gemini-3.1-pro-preview")

SYSTEM_PROMPT = """\
Você é um QA Sênior especializado em testes E2E de SPAs React. Vai receber
screenshots da SPA "VALBOT" (auditoria de exames de direção do DETRAN). A
plataforma roda em https://valbot.com.br/video.

Já existe uma suíte Playwright com 49 asserts cobrindo:
  - Login é a porta principal (sem sessão)
  - Login flow via quick role auditor
  - Dashboard: KPIs + 3 charts recharts
  - Alertas: lista, filter pills, badges severidade
  - Relatórios: viewer paper + download PDF mock
  - Vídeos: lista de cards reais + botões Ver laudo/PDF/Reanalisar
  - Vídeos → /api/laudo/{hash}/pdf retornando PDF binário
  - Auditoria: KPIs, sidebar calibração, tabela amostras
  - Regras: rubrica CONTRAN, sliders

Sua tarefa: devolver JSON com NOVOS testes que ainda NÃO foram cobertos,
priorizando por risco. Olhe os screenshots e identifique:
  - Fluxos críticos não testados (ex: logout, recarga, sessão expirada)
  - Edge cases visuais (estados loading, error, empty)
  - Acessibilidade (foco, contraste, keyboard nav)
  - Mobile/responsivo
  - Performance (lazy load, throttling)
  - Segurança client-side (XSS em campos, CSRF, hash UUID no PDF)
  - Funcionalidades dos botões que ainda não foram clicados
  - Validações de formulário
  - Integrações backend (timeouts, 4xx/5xx, retries)

Devolva SOMENTE JSON com este schema:
{
  "summary": "string — visão geral dos gaps",
  "tests": [
    {
      "id": "TC-001",
      "title": "string",
      "priority": "P0|P1|P2",
      "category": "auth|ui|a11y|perf|security|integration|edge",
      "page": "login|dashboard|alertas|relatorios|videos|auditoria|regras|global",
      "preconditions": "string",
      "steps": ["string", "string"],
      "expected": "string",
      "playwright_hint": "selector ou pseudo-código"
    }
  ]
}

Entre 15 e 25 testes. Foque em cobertura real, não em duplicar o que já existe.
DEVOLVA SOMENTE O JSON. SEM TEXTO ANTES OU DEPOIS.
"""


def main(argv: list[str]) -> int:
    paths = [Path(p) for p in argv[1:] if Path(p).is_file()]
    if not paths:
        print("erro: nenhum arquivo de imagem foi passado", file=sys.stderr)
        return 2

    print(f"[gemini-test] {len(paths)} screenshots → {MODEL_NAME} @ {LOCATION}", file=sys.stderr)
    for p in paths:
        size_kb = p.stat().st_size / 1024
        print(f"  • {p.name} ({size_kb:.1f}KB)", file=sys.stderr)

    vertexai.init(project=PROJECT_ID, location=LOCATION)
    model = GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)

    parts: list[Part] = [
        Part.from_text(
            "Aqui estão screenshots da SPA do VALBOT em produção. Cada um corresponde "
            "a uma tela diferente. Use-os pra propor a lista de testes faltantes."
        ),
    ]
    for p in paths:
        parts.append(Part.from_data(data=p.read_bytes(), mime_type="image/png"))
        parts.append(Part.from_text(f"^ screenshot: {p.name}"))

    print("[gemini-test] chamando Gemini…", file=sys.stderr)
    response = model.generate_content(
        parts,
        generation_config={
            "temperature": 0.4,
            "max_output_tokens": 16384,  # 8192 truncou — bump pra cobrir 15-25 testes completos.
            "response_mime_type": "application/json",
        },
    )

    text = response.text
    # Valida JSON
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[gemini-test] JSON inválido: {e}", file=sys.stderr)
        print(text)
        return 1

    # Cost info no stderr
    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        prompt_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
        out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
        # tier1 ≤200k tokens: $1.25/1M in + $5/1M out
        cost = (prompt_tok * 1.25 + out_tok * 5.0) / 1_000_000
        print(
            f"[gemini-test] tokens in={prompt_tok} out={out_tok} → ${cost:.4f}",
            file=sys.stderr,
        )

    json.dump(parsed, sys.stdout, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
