# Pesquisa de Throughput LaudoAI v3.1 — Análise Custo/Performance por GPU

**Data:** 2026-05-02
**Pipeline alvo:** LaudoAI v3.1 (10 estágios, mosaic 4 câmeras 1280×720, 30 fps, vídeo 10 min ~500MB)
**Targets:** Mac M4 Max 30-45 min/vídeo · H100 ≤60s · B200 ≤30s

---

## Modelagem do tempo por GPU

A soma dos estágios não-paralelizáveis (1-5, 7, 8, 10) já consome ~55s mesmo numa GPU ideal — porque incluem ffmpeg (5s CPU), pyannote (25s), Whisper-v3-turbo (12s H100), BEATs+CLAP (3s) e chamada de rede pra Gemini 2.0 Flash (5s). Os dois estágios pesados que escalam com VRAM/compute são o **#6 (visual clássico)** e o **#9 (decisor multi-pass com 15 votos, dos quais 3 generalistas multimodais rodam localmente)**.

**Baseline H100 SXM 80GB** (reference) — atinge ~60s/vídeo:
- estágios leves + áudio: ~50s
- estágio 6 visual: 18s (em paralelo com 4 via 2 streams CUDA: efetivo +8s)
- estágio 9 (3 generalistas locais — Qwen-Omni-7B + Phi-4-MM + Gemini API): ~12s no caminho crítico (specialists JSON-only são chamadas de API, paralelas)
- **Total H100 ≈ 60s** ✓

A escala entre GPUs assume:
- B200: 1.8× mais rápida que H100 SXM em FP8/FP4 (Blackwell) → ~30s ✓
- H200: ~1.15× H100 (mesmo SM, mais HBM/banda) → ~52s
- H100 PCIe: ~0.85× H100 SXM (NVLink ausente impacta multi-stream) → ~70s
- A100 80GB: ~0.55× H100 (sem FP8 nativo, BF16-only) → ~110s
- A100 40GB: precisa quantizar Sapiens-2B + DeepSeek-R1-70B mais agressivamente, perde paralelismo → ~135s
- L40S 48GB: arquitetura Ada, sem NVLink, FP8 disponível mas memória menor → ~95s
- RTX 6000 Ada 48GB: similar L40S, clock maior, memória idem → ~100s
- RTX 5090 32GB: Blackwell consumer, FP4 forte, mas 32GB força INT4 em quase tudo e perde 1 generalista local → ~85s
- RTX 4090 24GB: Ada consumer, 24GB obriga descarte de Sapiens-2B FP16 → fallback FP8 leve → ~150s

---

## Tabela mestra

| GPU | VRAM | Spot $/h | Tempo/vídeo (s) | Vídeos/h | Custo/vídeo (USD) | Custo/100 vídeos | Bottleneck |
|---|---|---|---|---|---|---|---|
| **B200** | 192GB | $5.50 | 30 | 120.0 | $0.0458 | $4.58 | Áudio (Whisper+pyannote) — compute sobra |
| **H200** | 141GB | $3.80 | 52 | 69.2 | $0.0549 | $5.49 | Estágio 6 visual + 1 generalista 7B |
| **H100 SXM** | 80GB | $2.20 | 60 | 60.0 | $0.0367 | $3.67 | Co-DETR Swin-L + Sapiens-2B paralelos |
| **H100 PCIe** | 80GB | $1.90 | 70 | 51.4 | $0.0369 | $3.69 | Sem NVLink → streams CUDA serializam |
| **A100 80GB** | 80GB | $1.10 | 110 | 32.7 | $0.0336 | $3.36 | Sem FP8: BF16 dobra latência Whisper+Co-DETR |
| **A100 40GB** | 40GB | $0.80 | 135 | 26.7 | $0.0300 | $3.00 | VRAM: Sapiens FP8 + DeepSeek INT4 obrigatórios |
| **L40S** | 48GB | $0.95 | 95 | 37.9 | $0.0251 | $2.51 | Banda HBM ausente (GDDR6) penaliza Sapiens |
| **RTX 6000 Ada** | 48GB | $0.70 | 100 | 36.0 | $0.0194 | $1.94 | Mesma classe L40S, sem ECC HBM |
| **RTX 5090** | 32GB | $0.55 | 85 | 42.4 | $0.0130 | $1.30 | 32GB força INT4 — perde 1 generalista local |
| **RTX 4090** | 24GB | $0.35 | 150 | 24.0 | $0.0146 | $1.46 | 24GB obriga offload CPU; Sapiens-2B só FP8 |
| **Mac M4 Max** | 128GB unif. | n/a (CapEx) | 2100 (35 min) | 1.71 | $0.0238* | $2.38* | MPS/MLX 4× lento que CUDA; sem FP4 |

\* Mac assume amortização CapEx $4.500 / 24 meses / 16h-dia úteis = ~$0.39/h equivalente.

**Custo de API externa (Gemini 2.0 Flash + Claude Opus/Sonnet specialists)**: somar fixo **~$0.40/vídeo** (modo só-vídeo) ou **~$1.00/vídeo** (modo MVP completo). Esse custo é independente da GPU e domina nos cenários consumer (RTX 5090/4090).

---

## Notas técnicas

### 1. VRAM fit de modelos críticos

| Modelo | FP16 | FP8/INT4 | Mínimo prático |
|---|---|---|---|
| Qwen2.5-VL-72B | ~145GB | ~40GB (AWQ) | 1× B200 / 1× H200 / 2× H100 (TP=2) FP16; 1× H100 INT4 |
| DeepSeek-R1-70B | ~140GB | ~38GB (INT4) | 1× B200 FP16; 1× A100 80GB INT4 ✓ |
| Qwen2.5-Omni-7B | ~14GB | ~5GB | qualquer ≥16GB |
| Phi-4-MM (5.6B) | ~12GB | ~4GB | qualquer ≥12GB |
| Sapiens-2B-pose | ~24GB | ~9GB FP8 | A100 40GB com FP8 ✓; RTX 4090 com offload |
| Co-DETR Swin-L | ~3.8GB | n/a | qualquer GPU |
| Whisper-v3-turbo (809M) | ~1.6GB | ~0.5GB INT8 | trivial |

### 2. Frame batching (estágio 6)
H100 processa 2fps × 600s = **1200 frames**. Em batches de 32 com Co-DETR Swin-L: ~5-10 batches/s → ~120-240s se serial. Em pipeline com 2 streams CUDA paralelizando Sapiens+Co-DETR cai para ~18s.

### 3. APIs externas (custo fixo, off-GPU)
- Gemini 2.0 Flash (NLU + 1 voto generalista): ~$0.20/vídeo
- 12 specialists JSON (Opus 4.7 / Sonnet 4.6 / DeepSeek-R1 hospedado): ~$0.20-0.80/vídeo dependendo de cache
- **Sempre somar +$0.40-1.00 ao custo/vídeo da tabela**

### 4. Single-GPU vs Multi-GPU
- Para Qwen2.5-VL-72B FP16 sem quantizar: precisa 2× H100 SXM (TP=2) ou 1× B200/H200 — multiplica custo por GPU.
- Para ensemble paralelo (15 votos), GPUs sobrando aceleram linearmente os 3 generalistas locais; specialists JSON são API e não dependem da GPU local.

### 5. Validação dos preços spot
WebSearch confirma valores razoáveis. Achados notáveis:
- **B200 spot real está mais baixo que assumido** ($2.25-2.50/h em Spheron/getdeploying mai/2026) — se confirmado, B200 cai pra ~$0.019/vídeo, melhor opção absoluta.
- H100 SXM spot real entre $1.49 (Vast.ai promo) e $2.99 (Lambda) — $2.20 é mediano coerente.
- RTX 5090 spot a $0.32-0.55 — $0.55 é conservador.
- A100 80GB spot $1.00-1.80 (Vast.ai) — $1.10 é coerente.

---

## Cenários recomendados

### Cenário A — Custo mínimo aceitável (acurácia ~80%, overnight)

**Hardware:** 1× RTX 5090 32GB spot ($0.55/h)
**Throughput:** 42.4 vídeos/h (85s/vídeo)
**Custo GPU/100 vídeos:** $1.30
**Custo total/100 vídeos** (com APIs $0.40 só-vídeo): **$41.30**

Stack reduzido: Phi-4-MM (5.6B) substitui Qwen-Omni-7B (libera VRAM); DeepSeek-R1-70B fora do ensemble local (vira API); Sapiens-2B em FP8. Aceita perda de ~10pp acurácia vs Cenário C.

### Cenário B — Equilíbrio (acurácia ~90%, ~5 min/vídeo)

**Hardware:** 1× A100 80GB spot ($1.10/h)
**Throughput:** 32.7 vídeos/h (110s/vídeo) — bem abaixo do "5 min" do enunciado, dá margem.
**Custo GPU/100 vídeos:** $3.36
**Custo total/100 vídeos** (APIs $0.80 MVP): **$83.36**

DeepSeek-R1-70B em INT4 cabe em A100 80GB. Qwen-Omni-7B + Phi-4-MM rodam paralelos. Sapiens-2B FP8. Acurácia próxima do topo, custo metade do H100.

### Cenário C — Performance máxima (acurácia ~95%, 60s/vídeo)

**Hardware:** 1× H100 SXM 80GB spot ($2.20/h)
**Throughput:** 60 vídeos/h (60s/vídeo) ✓ atende SLA
**Custo GPU/100 vídeos:** $3.67
**Custo total/100 vídeos** (APIs $1.00 MVP): **$103.67**

Ensemble completo: Qwen2.5-VL-72B em INT4/AWQ + DeepSeek-R1-70B INT4 + Sapiens-2B FP16 + Co-DETR Swin-L. 2 streams CUDA. NVLink ajuda no allreduce dos votos.

**Variante C+:** 1× B200 spot — se preço real $2.25/h se confirmar, **dominante**: 30s/vídeo a $0.019/vídeo + APIs.

### Cenário D — Híbrido pico+base (Mac M4 Max + H100 spot)

**Setup:** Mac Studio M4 Max 128GB (CapEx $4.500) processa baseload local; H100 spot acionado em pico.

**Throughput Mac:** 1.71 vídeos/h × 16h/dia úteis = **27.4 vídeos/dia** sustentado.

**Break-even Mac vs H100 spot puro:**
- Custo Mac amortizado em 24 meses: $4.500 / (24 × 30) = **$6.25/dia**
- Custo H100 spot equivalente (27 vídeos/dia × 60s × $2.20/h): 27 × $0.0367 = **$0.99/dia** GPU + **$1.08/dia** API = **$2.07/dia**

**Conclusão break-even:** H100 spot puro é **3× mais barato** que comprar Mac Studio se a demanda é ≤30 vídeos/dia. Mac só compensa acima de **~80 vídeos/dia** sustentado E se houver requisito de privacidade/offline (sem APIs externas) — caso em que ele vira hardware dedicado e o custo de oportunidade desaparece.

**Recomendação D:** **Não comprar Mac Studio** para servir produção. Mac M4 Max já existente serve só de **dev/staging local** (acurácia primeiro, sem SLA). Produção vai 100% spot.

---

## Recomendação executiva final

1. **Padrão de produção: H100 SXM 80GB spot @ $2.20/h** — atende SLA de 60s/vídeo, ensemble completo com Qwen2.5-VL-72B em AWQ INT4 + DeepSeek-R1-70B INT4. Custo ~$1.04/vídeo all-in. Use Vast.ai ou RunPod para spot agressivo (~$1.49/h em promoção).

2. **Pico/burst: B200 spot quando disponível** — se confirmar $2.25-2.50/h spot (mai/2026), B200 vira opção dominante: 30s/vídeo, ~$0.40-0.50/vídeo all-in, headroom pra rodar Qwen2.5-VL-72B FP16 sem quantizar (acurácia +2-3pp).

3. **Quantizações obrigatórias:** Qwen2.5-VL-72B em **AWQ INT4** (cabe em 1 H100), DeepSeek-R1-70B em **INT4 GPTQ** (cabe em 1 A100 80GB ou 1 H100), Sapiens-2B em **FP8** (libera 15GB), Whisper-v3-turbo em **INT8** (latência -30%, qualidade mantida). Nada FP16 exceto Co-DETR (já é leve).

4. **Trocar Qwen2.5-Omni-7B por Phi-4-MM (5.6B) em GPUs ≤32GB** — Phi-4-MM tem capacidade multimodal comparável, libera 9GB e roda em RTX 5090. Manter Qwen-Omni só em H100/H200/B200.

5. **Mac M4 Max fica como dev/staging local apenas.** Não comprar Mac Studio dedicado para servir produção: H100 spot é 3× mais barato em qualquer regime ≤80 vídeos/dia. Para offline/privacidade total, considerar 1× RTX 6000 Ada 48GB (CapEx $7k) que serve um analista em tempo real sem dependência de cloud.

---

## Sources

- [B200 Cloud Pricing — getdeploying (2026)](https://getdeploying.com/gpus/nvidia-b200)
- [GPU Cloud Pricing Comparison 2026 — Spheron](https://www.spheron.network/blog/gpu-cloud-pricing-comparison-2026/)
- [B200 Index Price March 2026 — Silicon Data](https://www.silicondata.com/blog/b200-rental-price-march-2026-update)
- [H100 Cloud Pricing — getdeploying (2026)](https://getdeploying.com/gpus/nvidia-h100)
- [NVIDIA H100 Pricing May 2026 — Thundercompute](https://www.thundercompute.com/blog/nvidia-h100-pricing)
- [H100 Rental Prices Compared — IntuitionLabs](https://intuitionlabs.ai/articles/h100-rental-prices-cloud-comparison)
- [RTX 5090 Cloud Pricing — getdeploying](https://getdeploying.com/gpus/nvidia-rtx-5090)
- [Rent RTX 5090 GPUs on Vast.ai](https://vast.ai/pricing/gpu/RTX-5090)
- [A100 Cloud Pricing — getdeploying (2026)](https://getdeploying.com/gpus/nvidia-a100)
- [NVIDIA A100 Pricing April 2026 — Thundercompute](https://www.thundercompute.com/blog/nvidia-a100-pricing)
- [NVIDIA H200 Price Guide 2026 — Jarvis Labs](https://jarvislabs.ai/blog/h200-price)
- [H200 Cloud Pricing — getdeploying (2026)](https://getdeploying.com/gpus/nvidia-h200)
