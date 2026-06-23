"""Val Auditor Exames — backend v2.

Reescrita modular do backend alinhada à Especificação Funcional v2.0
(CONTRAN 1.020/2025 + MBEDV). Organiza o produto nos 5 motores da spec §2.2
mais o Comitê de IA (§10) e o fluxo de Ordens de Serviço / decisão humana
(§11-§12), reaproveitando o pipeline de análise existente em ``src/``.

Camadas:

    backend.core        — config, db (pool psycopg), segurança (API keys/sessão)
    backend.models      — contratos pydantic de toda a plataforma (spec §5-§14)
    backend.engines     — os 5 motores: evidencias, deteccao, normativo,
                          pontuacao, comparacao
    backend.committee   — Comitê de IA (2ª passada focada nas infrações achadas)
    backend.workflow    — Ordens de Serviço + fluxo humano de 4 níveis
    backend.dashboard   — indicadores operacionais e regulatórios
    backend.reporting   — laudo explicável (PDF via src/reporting + JSON + hash)
    backend.pipeline    — orquestra Motor 1→2→3→4→5 → Comitê → OS
    backend.api         — routers FastAPI que expõem tudo acima
"""

__version__ = "2.0.0"
