# ADR 0001 — Vertex AI ao invés de OpenRouter ou AI Studio para Gemini

- **Status:** aceito
- **Data:** 2026-05-05
- **Decisores:** Igor Lima

## Contexto

O pipeline VLM do valbot precisa chamar `gemini-3.1-pro-preview` no vídeo inteiro (visão + áudio). Existem três caminhos para acessar o modelo:

1. **AI Studio** (`generativelanguage.googleapis.com` via API key `AIza...`).
2. **OpenRouter** (proxy unificado para vários providers, slug `@preset/valbot-r1-vip-v25`).
3. **Vertex AI** (`aiplatform.googleapis.com` via OAuth/ADC, atrelado a billing GCP).

O projeto Free Trial GCP `project-308f1fa8-a301-49e6-a69` tem R$ 1.703,19 de crédito (válido até 24/jul/2026, billing `0136E7-D0E380-75438A`). A chave AI Studio `AIza...qeMM` está num projeto sem billing — `free_tier limit: 0` em qualquer modelo Pro.

## Decisão

Usar **Vertex AI** com OAuth (Service Account atrelada à VM ou ADC local) para todas as chamadas Gemini Pro.

## Consequências

### Positivas
- Os créditos GCP cobrem ~640 análises de 10 minutos a $0.53 cada.
- Token rotacionado pelo metadata server (sem JSON de SA pra vazar).
- Alinha com setup já documentado em `docs/gemini_vertex_setup.md`.
- Mesmo bucket GCS (`valbot-prod`) que armazena os vídeos é lido pelo Vertex via `Part.from_uri("gs://...")` — bandwidth interno gratuito.
- `gemini-3.1-pro-preview` está em region `global` (sem regional pinning), funciona com a VM em qualquer zona.

### Negativas
- Setup de auth mais complexo que API key (precisa `gcloud auth application-default login` em dev local + Service Account na VM).
- SDK Python `google-cloud-aiplatform` é grande (~80 MB com deps) — aumenta tamanho da imagem Docker.
- Não dá pra usar OpenRouter pra benchmark contra outros providers (Qwen, GPT) sem segundo path; bench legado em `tooling/bench_demo` usa caminho separado.

### Mitigações
- Variável de ambiente `VALBOT_USE_MOCK_VLM=1` permite dev local sem auth GCP.
- O nome do módulo (`src/analysis/openrouter_gemini.py`) foi mantido por compat semântica com a terminologia do produto, apesar de implementar Vertex.
