# Bench Valbot — Resumo executivo

## 1. Onde colocar crédito

| Site | Crédito | Como entrar |
|---|---|---|
| **openrouter.ai** | **US$ 30** (R$ 165) via Stripe (cartão BR) | Login com Google |
| **aistudio.google.com** | **US$ 0** (free tier) | Login com Google |

**Total: US$ 30 num único lugar (OpenRouter).**

## 2. Fluxo

```
VOCÊ (~7 min)
  1. Cadastra openrouter.ai + aistudio.google.com
  2. Coloca US$ 30 no OpenRouter
  3. Salva 2 API keys em ~/Documents/envkey.txt no formato:
       OPENROUTER_API_KEY=sk-or-v1-...
       GOOGLE_API_KEY=AIzaSy...
                        │
                        ▼
EU (autônomo, ~2h, em background)
  1. Construo o harness (src/bench/)
  2. Faço peer-review do prompt (3 LLMs com personas opostas)
  3. Te envio prompt_review.md → você aprova/rejeita (~2 min)
  4. Disparo 270 chamadas (9 vídeos × 10 modelos × 3 rodadas)
  5. Consolido tudo em summary.html
                        │
                        ▼
VOCÊ recebe
  storage/benchmarks/<ts>/summary.html
  → grid 9 vídeos × 10 modelos com laudos lado a lado
  → escolhe o vencedor
```

**Único ponto onde você precisa voltar no meio:** aprovar o `prompt_review.md` (~2 min de leitura). Garante que o prompt está bom antes de queimar crédito.

## O que eu defino sozinho

- **10 modelos do bench**: Gemini 2.5 Pro, Gemini 3.1 Pro, GPT-5.5, Claude Opus 4.7, Qwen3-VL-235B, InternVL3-78B, Kimi K2.6, LLaVA-Video, Cosmos-Reason 2, DeepSeek V3.2 (via ponte text-only)
- **Peer-review (3 revisores + consolidador)**:
  - A: GPT-5.5 (auditor técnico)
  - B: Claude Opus 4.7 (advogado CONTRAN cético)
  - C: Cosmos-Reason 2 (examinador veicular físico)
  - Consolidador: Gemini 2.5 Pro (tie-breaker)
- **Determinismo**: temperature=0, seed=42, 3 rodadas + moda
- **Schema padrão**: laudo v3.1-bench (1 infração = 1 janela contínua, com confiança)
- **Legislação**: Resolução CONTRAN 1.020/2025 + MBEDV (apenas)
- **Paralelismo, retries, fallbacks, agregação**: tudo automatizado

## Custo total

**~US$ 30** one-time no OpenRouter. Sem assinatura mensal. Sem GPU própria.

## Pós-bench — fine-tuning fica em aberto

Decisão sobre fine-tuning **só depois** que o bench rodar. As 4 informações que vamos cruzar pra decidir:

1. Acurácia comparativa dos 10 modelos
2. Custo por vídeo em produção (sem fine-tune)
3. Latência por modelo
4. Determinismo entre rodadas

Caminhos disponíveis (todos viáveis, nenhum eliminado a priori):

| Estratégia | Quando faz sentido |
|---|---|
| **Few-shot prompting** | Filtro antes de qualquer SFT — fecha 60–80% do gap em ~70% dos casos, custo zero |
| **Managed via API** (Vertex AI Gemini, OpenAI GPT, Fireworks Qwen, Together AI) | Custo $15–80, tempo 1–4h, zero MLOps |
| **Self-hosted GPU alugada** (Vast.ai/RunPod hot-spot + LLaMA-Factory) | Privacidade total, controle hyperparam, custo $6–200 treino + $1.500/mês servir 24/7 |
| **NVIDIA Cosmos Cookbook** (recipe oficial AV/DETRAN) | Cosmos-Reason 2 specialist, 1× H100 chega ($6–12 treino), serve em $5/mês via NeMo |
| **DeepSeek V3.2 fine-tune text-only** | Especializa só raciocínio jurídico, $1/mês em produção |

Detalhe completo no plano em §11 (matriz 10 modelos × 5 caminhos com simulação de custo, tempo, latência).

## Plano completo

`/Users/igorlima/.claude/plans/preciso-adaptar-nosso-algoritmo-enumerated-platypus.md`
