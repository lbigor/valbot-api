# Gemini via Vertex AI — setup com créditos GCP

> **Status:** validado em 2026-05-05.
> **Por que existe este doc:** o pipeline valbot (`src/analysis/vlm_engine.py`) ainda usa a chave AI Studio (`GOOGLE_API_KEY`), que está em projeto sem billing. Os créditos GCP que existem (R$ 1.703,19 Free Trial) só fluem via Vertex AI. Este doc registra como autenticar, quais modelos funcionam, e qual é o caminho reusável.

---

## TL;DR

- A chave AI Studio `AIza...qeMM` retorna `429 free_tier limit: 0` para qualquer modelo Pro — **não usar** para `gemini-2.5-pro` nem `gemini-3.1-pro-preview`.
- Os créditos GCP (R$ 1.703,19) estão no projeto **`project-308f1fa8-a301-49e6-a69`** (billing `0136E7-D0E380-75438A`), válidos até 24/jul/2026.
- Vertex AI nesse projeto **funciona** para Gemini Pro. Autentica com OAuth (`gcloud auth application-default login`), não com API key.
- `gemini-3-pro-preview` foi descontinuado pelo Google em 26/mar/2026 — substituto oficial é `gemini-3.1-pro-preview`.

---

## AI Studio vs Vertex AI — qual é qual

| | AI Studio (Generative Language API) | Vertex AI |
|---|---|---|
| **Endpoint** | `generativelanguage.googleapis.com` | `*-aiplatform.googleapis.com` (regional) ou `aiplatform.googleapis.com` (global) |
| **Auth** | API key `AIza...` (header `?key=...`) | OAuth (`Authorization: Bearer <token>`) — service account ou ADC |
| **Billing** | Free tier por padrão; pago = habilitar billing **na própria API key** | Usa billing do projeto GCP — **créditos Free Trial cobrem** |
| **Cota Pro** | `free_tier limit: 0` para `gemini-2.5-pro` e `gemini-3.1-pro` | Disponível com billing/créditos |
| **Onde a key vive** | aistudio.google.com | console.cloud.google.com (projeto GCP) |

**Implicação prática:** créditos GCP **não chegam** na chave AI Studio. Se quiser usar os R$ 1.703, é Vertex.

---

## Setup gcloud (uma vez por máquina)

Já feito em `igorlima@`/Mac (2026-05-05):

```bash
# Instalar SDK (se ainda não tiver)
brew install --cask google-cloud-sdk

# Login da conta humana (browser)
gcloud auth login

# ADC (para SDKs Python/Node renovarem token sozinhos)
gcloud auth application-default login

# Setar projeto com créditos
gcloud config set project project-308f1fa8-a301-49e6-a69
gcloud auth application-default set-quota-project project-308f1fa8-a301-49e6-a69

# Habilitar Vertex AI (já estava habilitada nesse projeto)
gcloud services enable aiplatform.googleapis.com

# Conferir
gcloud auth list
gcloud services list --enabled --filter="name:aiplatform"
```

Conta autenticada nesta sessão: `igorbuaiz@gmail.com`.

---

## Modelos validados (HTTP 200 em 2026-05-05)

| Modelo | Region | Status |
|---|---|---|
| `gemini-2.5-pro` | `us-central1` | ✅ funciona |
| `gemini-3.1-pro-preview` | `global` | ✅ funciona |
| `gemini-3.1-pro-preview-customtools` | `global` | ✅ existe (variante p/ tool use) |
| `gemini-3-flash-preview` | `global` | ✅ funciona |
| `gemini-3-pro-preview` | — | ❌ **descontinuado em 26/mar/2026** — usar 3.1 |

**Importante sobre region `global`:** modelos preview da família 3.x não estão em regiões específicas (`us-central1`, etc.) — só aparecem em `global`. URL fica sem prefixo regional: `https://aiplatform.googleapis.com/v1/projects/.../locations/global/...`.

Modelos da família 2.x ficam em regiões normais (`us-central1` recomendado).

---

## Templates de chamada

### `gemini-2.5-pro` (region us-central1)

```bash
PROJECT_ID="project-308f1fa8-a301-49e6-a69"
LOCATION="us-central1"
TOKEN=$(gcloud auth print-access-token)

curl -s -X POST \
  "https://${LOCATION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/publishers/google/models/gemini-2.5-pro:generateContent" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"role":"user","parts":[{"text":"SEU PROMPT"}]}]}'
```

### `gemini-3.1-pro-preview` (region global)

```bash
PROJECT_ID="project-308f1fa8-a301-49e6-a69"
TOKEN=$(gcloud auth print-access-token)

curl -s -X POST \
  "https://aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/global/publishers/google/models/gemini-3.1-pro-preview:generateContent" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"role":"user","parts":[{"text":"SEU PROMPT"}]}]}'
```

### Token expira em ~1h

Quando der HTTP 401, regerar com `gcloud auth print-access-token` ou usar o SDK (`google-cloud-aiplatform` em Python) que renova ADC sozinho via:

```python
import vertexai
from vertexai.generative_models import GenerativeModel

vertexai.init(project="project-308f1fa8-a301-49e6-a69", location="us-central1")
model = GenerativeModel("gemini-2.5-pro")
resp = model.generate_content("seu prompt")
```

---

## Status da chave AI Studio `AIza...qeMM`

- **Não funciona** para Pro (free_tier limit: 0).
- **Funciona** para Flash (`gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-3-flash-preview`) — mas com cota gratuita limitada.
- **Foi exposta na conversa de 2026-05-05** — recomenda-se revogar em [aistudio.google.com/apikey](https://aistudio.google.com/apikey) e gerar nova se for continuar usando AI Studio para algo.

Para o pipeline valbot, **migrar para Vertex** elimina o problema de cota e usa os créditos.

---

## Acompanhar consumo dos créditos

[console.cloud.google.com/billing/0136E7-D0E380-75438A/reports](https://console.cloud.google.com/billing/0136E7-D0E380-75438A/reports) → filtrar por serviço **Vertex AI**. O Free Trial cobre primeiro; quando acabar, vai para zero a menos que ativem billing pago.

[console.cloud.google.com/billing/0136E7-D0E380-75438A/credits/all](https://console.cloud.google.com/billing/0136E7-D0E380-75438A/credits/all) → estado dos créditos em tempo real.

---

## TODO — migração `vlm_engine.py`

Hoje (`src/analysis/vlm_engine.py`):
- `ClaudeBackend` → Anthropic (`ANTHROPIC_API_KEY`)
- backend Gemini → AI Studio (`GOOGLE_API_KEY`)
- Qwen2.5-VL → local

Proposta de migração (não implementada ainda):
1. Adicionar `VertexBackend` com `vertexai.init(project=..., location=...)`.
2. Permitir escolha entre `gemini-2.5-pro` (region `us-central1`) e `gemini-3.1-pro-preview` (region `global`).
3. Manter Anthropic e Qwen como hoje.
4. Variável de ambiente nova: `VERTEX_PROJECT` (default `project-308f1fa8-a301-49e6-a69`) e `VERTEX_LOCATION` (per-modelo).
5. Deprecar `GOOGLE_API_KEY` para o caminho Pro — manter só para Flash se necessário.

Custo estimado para tooling/bench_demo: precisa medir input/output token médio dos vídeos atuais.

---

## Refs oficiais

- [Vertex AI · Gemini 3 Pro (descontinuado)](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-pro)
- [Vertex AI · Gemini 3.1 Pro](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-1-pro)
- [Model versions and lifecycle](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions)
- [Blog: Gemini 3.1 Pro on Gemini Enterprise / Vertex AI](https://cloud.google.com/blog/products/ai-machine-learning/gemini-3-1-pro-on-gemini-cli-gemini-enterprise-and-vertex-ai)
- [Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
