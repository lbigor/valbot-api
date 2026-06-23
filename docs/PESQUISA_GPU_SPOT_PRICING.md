# Pesquisa: Preços spot e on-demand de GPUs em cloud (Maio 2026)

**Data da coleta:** 2026-05-02
**Escopo:** preços USD/hora (spot e on-demand) para Datacenter (B200, B100, H200, H100 SXM/PCIe, A100 80/40GB, L40S/L40, MI300X, MI325X, TPU v5e/v5p/Trillium) e Consumer/Prosumer (RTX 5090, 4090, 6000 Ada, A6000) em hyperscalers, GPU-clouds especializados e marketplaces.
**Carga-alvo do usuário:** Qwen2.5-VL 72B + DeepSeek-R1 70B + Whisper-v3-turbo + Co-DETR + Sapiens-2B em ensemble multi-pass; meta de processar 1 vídeo de 10min em ≤60s numa H100.

> **Nota de método.** Todos os valores abaixo foram coletados via WebSearch entre 25 e 30 de abril de 2026, predominantemente das fontes getdeploying.com, computeprices.com, thundercompute.com, jarvislabs.ai, runpod.io/pricing, vast.ai/pricing, lambda.ai/pricing, coreweave.com/pricing, voltagepark.com, hyperstack.cloud, oracle.com/cloud/price-list e blogs oficiais dos respectivos provedores. Mercado spot tem alta variância intradiária — onde possível indico data específica do snapshot. Onde a fonte não traz dado público, marco "n/d".

---

## 1. Tabela mestra — preço médio por GPU (USD/hora)

> **Convenção de leitura.** "Spot" = interruptible/preemptível/community/marketplace (preço pode dobrar ou desaparecer). "On-demand" = dedicado, sem interrupção. Quando o provedor só vende em bundle 8x, normalizei para por-GPU dividindo o preço de nó por 8.

### 1.1 Datacenter / High-end

| GPU | Spot — provedor mais barato | Spot $/h | On-demand mediano | On-demand mais caro | Observações |
|---|---|---|---|---|---|
| **B200 (192GB HBM3e)** | Reserva 36m getdeploying | **2,25** | 4,99 (RunPod) — 6,08 (Lambda) — 6,25 (Modal serverless) | 14,24 (hyperscalers premium) | 23 provedores listam B200; spot bateu 2,25 em 18/04/2026; sem oferta sólida em AWS/GCP ainda |
| **B100 (192GB HBM3e)** | n/d (oferta pública pobre) | n/d | 2,25–6 (provedor único listado) | n/d | Limitada a poucos provedores; não recomendo prever orçamento até GA mais ampla |
| **H200 (141GB HBM3e)** | Vast.ai marketplace ~3,00; GCP Spot 3,72 | **2,50–3,72** | 3,59–4,54 (RunPod / Spheron); 3,80 (Jarvislabs); 2,50 (GMI Cloud) | 10–13,78 (Azure / OCI bundle); Oracle 10,00 fixo | GMI Cloud $2,50/h on-demand é o piso público real |
| **H100 SXM 80GB** | Vast.ai ~1,49 (promo); Voltage Park 2,00–2,50; ThunderCompute 1,38 | **1,38–2,00** | 2,69 (RunPod), 2,40 (Hyperstack), 2,86–3,78 (Lambda PCIe→SXM), 3,11 (mediano mercado) | 5,40–6,98 (Azure), 12,30 (Baseten serverless ponta) | OCI fixo $10/GPU/h em bundle BM.GPU.H100.8 |
| **H100 PCIe 80GB** | RunPod Community 1,99; Vast.ai 1,87 | **1,49–1,99** | 1,99 (RunPod), 2,86 (Lambda), 4,25 (CoreWeave) | 5–7 (hyperscalers) | Diferença de 25–35% pra SXM por causa de NVLink |
| **A100 80GB** | Vast.ai 0,67; RunPod Community 1,19; DataCrunch 0,80 | **0,67–1,29** | 1,29–1,57 (Vast on-demand / RunPod Secure 1,89), 1,48 (Lambda), 2,49 (Lambda H100-PCIe spec); 3,18 (Paperspace) | 4–5 (hyperscalers) | Mediana caiu de ~$2/h em 2024 para ~$1,5/h hoje |
| **A100 40GB** | Vast.ai marketplace ~0,55 | **0,55–0,80** | 1,29 (mediano) | 3 (hyperscalers) | Pouca diferença de preço pra 80GB; preferir 80GB |
| **L40S 48GB** | spot 0,28–0,32 (marketplace) | **0,28–0,90** | 1,27 (Fluence), 1,55–1,82 (Nebius), 2–3 (mediano) | 7,58 (premium HA) | Excelente custo pra inferência VLM única-instância |
| **L40 48GB** | n/d | n/d | 1,57–2,40 (provedor médio) | 4–5 (hyperscalers) | Substituído pelo L40S na maioria dos catálogos |
| **MI300X 192GB** | Vast.ai/Hot Aisle 0,50–1,71 | **0,50–1,71** | 2,00–2,35 (mediano), 1,85 (TensorWave), 2,50 (DigitalOcean), 3,90 (Crusoe-equiv) | 6–7,86 (premium) | Vultr, TensorWave, RunPod, OCI, Cirrascale, Crusoe, Seeweb, Scaleway |
| **MI325X 256GB** | n/d (marketplace fino) | **2,00 (3-yr reserva)** | 2,29 (mediano) | 2,55 | Cobertura: DigitalOcean, TensorWave, Vultr |
| **TPU v5e (chip-h)** | Spot ~0,40–0,50 | **0,40–0,50** | 1,20 (chip-h on-demand); v5e-8 pod 2,56 | 1,20 | Mais barato do que NVIDIA equivalente para inference batch |
| **TPU v5p (chip-h)** | Spot estimado 1,60–2,10 | **~1,60–2,10** | 4,20 (chip-h on-demand) | 4,20 | Treinamento de fronteira |
| **TPU Trillium (v6, chip-h)** | n/d direto | **1,22 (3-yr commit)** | 2,70 (on-demand); 1,89 (1-yr) | 2,70 | 2,1× perf/$ vs v5e em LLMs densos |

### 1.2 Consumer / Prosumer

| GPU | Spot mais barato | Spot $/h | On-demand mediano | Provedores |
|---|---|---|---|---|
| **RTX 5090 32GB** | Vast.ai 0,13 (spot extremo) — 0,35 (marketplace) | **0,13–0,55** | 0,65 (CloudRift), 0,86 (Spheron), 0,99 (RunPod) | Vast, CloudRift, Spheron, RunPod, Runcrate |
| **RTX 4090 24GB** | Vast.ai 0,10–0,29 | **0,10–0,34** | 0,39–0,59 (Vast estável); 0,69 (RunPod Pro Community) | Vast.ai, RunPod, Salad, FluidStack, Genesis |
| **RTX 6000 Ada 48GB** | spot 0,27 | **0,27–0,40** | 0,77 (RunPod), 0,90–1,57 (mediano) | RunPod, Verda, AceCloud |
| **RTX A6000 48GB** | RunPod Community 0,49 | **0,25–0,49** | 0,49–0,77 (RunPod), 0,77 (Cudo); ThunderCompute 0,27 (RTX A6000 mais barato) | RunPod, Cirrascale, ThunderCompute, CudoCompute |

---

## 2. Detalhamento por provedor

### 2.1 Hyperscalers

#### **AWS — EC2 P5 (8× H100 SXM)**
- On-demand p5.48xlarge: $55–$66/h por nó (US-East/Ohio mais barato), ≈ **$3,90–$4,20/GPU-h** após corte de ~44% anunciado em jun/2025.
- Spot: drops a **~$2,50/GPU-h** em horários de baixa demanda; taxa de interrupção H100 = **4,1% por hora** (acima da média ~5% dos GPUs convencionais).
- Capacity Blocks for ML: contratos curtos (1–14 dias) com preço similar a 1y reserved (~$2,50/GPU-h).
- 1-year Savings Plan: efetivo ~$2,00/GPU-h. 3-year: ~$1,90.
- **Egress: $0,08–$0,12/GB.** Storage S3 padrão $0,023/GB/mês.

#### **GCP — A3 / A3-Mega / A3-Ultra**
- A3-Mega (8× H100 SXM): $80–$90/h por nó on-demand, ≈ **$10–$11/GPU-h** (US-Central).
- A3-High (1× H100): on-demand ~$3,00/GPU-h.
- A3-Ultra (8× H200, requer reserva ou Spot/Flex-start): mais caro que A3-Mega.
- Spot: desconto **60–91%** em GPUs gerais, mas em A3 o desconto é menor (~30–50%); spot H200 ≈ $3,72/GPU-h.
- TPU pricing já listado acima.

#### **Azure — ND H100 v5 (8× H100 SXM)**
- ND96isr H100 v5 on-demand: **$98,32/h por nó** ≈ $12,29/GPU-h (US-East/Central) — o mais caro entre hyperscalers.
- Spot: ~$70–$75/h por nó (~20–30% off), ≈ **$8,75–$9,40/GPU-h**. Risco de eviction.
- Reservas: 1y/3y disponíveis; ~$6,98/GPU-h efetivo em 1y.

#### **Oracle Cloud (OCI)**
- BM.GPU.H100.8 (bare metal 8× H100): **$80/h** por nó = $10/GPU-h fixo.
- BM.GPU.H200.8: **$10/GPU-h** (mantém o preço da geração anterior).
- L40S e A10 disponíveis; Supercluster H200 com InfiniBand 3,2 Tbps.
- **Sem cobrança de egress significativa** — diferencial vs AWS/Azure.

### 2.2 GPU-specialized clouds

#### **RunPod**
- **Community Cloud (spot/preemptível):** RTX 4090 0,34, RTX 5090 0,99, A100 80GB 1,19, H100 PCIe 1,99, B200 4,99.
- **Secure Cloud (on-demand, infra própria):** ~50% mais caro que Community.
- H200 SXM: 3,59 (on-demand) / 4,31 (HGX); H100 SXM 2,69; L40S 1,19 (on-demand).
- B200 com commit 6m: 4,34; 1-yr: 4,24.
- **Sem egress fees.** Storage persistente NVMe ~$0,07/GB/mês; armazenamento "network volume" ~$0,05/GB/mês.
- SOC2 II + HIPAA + GDPR (HIPAA obtido em 06/02/2026).

#### **Vast.ai (marketplace)**
- RTX 4090 0,29 (spot promocional), 0,39–0,59 estável.
- RTX 5090 0,35.
- A100 80GB spot 0,67.
- H100 SXM spot 1,49 (promoção); marketplace média 1,87 PCIe.
- Tipos: on-demand, **interruptible** (50%+ off), reserved (até 50% off).
- Risco: confiabilidade altamente variável — prosumer-grade. Muitos hosts são datacenters pequenos ou colocations sem SLA.

#### **Lambda Labs**
- H100 PCIe **2,86**, H100 SXM **3,78**, H200 ~3,62, B200 **6,08**, A100 80GB **1,48**.
- 1-Click Clusters (8× H100, 2-week min): preços negociados; ≥$3/GPU-h.
- Sem egress fees.

#### **CoreWeave**
- H100 PCIe **4,25**; bundle 8× H100 HGX **$49,24/h** (~$6,15/GPU-h).
- Spot: até **54% off**; reservas: até **60% off**.
- Sem ingress/egress/data-transfer fees.
- Storage tier: $0,015/GB/mês (cold) → $0,070/GB/mês (distributed file).

#### **Paperspace (DigitalOcean)**
- A100 on-demand 3,18; H100 5,95 (preços altos para o segmento).
- Tier de preço de 1,15 A100 só com commit 36m.
- Notebooks Gradient: Free / Pro $8/m / Growth $39/m.

#### **Hyperstack**
- H100 SXM on-demand **2,40**, reserved a partir de **1,90**.
- Spot disponível.

#### **TensorDock**
- H100 on-demand ~2,50; spot ~1,60. Marketplace agregado, similar a Vast.

#### **FluidStack**
- H100 on-demand **2,10** sem mínimo. Usado para clusters multi-nó.

#### **Crusoe Cloud**
- H100 on-demand **3,90** (premium por energia 100% limpa, gás flare/renovável).

#### **Voltage Park**
- H100 on-demand **1,99** (sem ingress/egress/suporte). Spot $2,00–$2,50.
- Reserved 12+ meses negociáveis.

#### **DataCrunch (Verda)**
- H100 SXM5 on-demand **2,29**; spot **0,80**.
- Datacenters europeus.

#### **Modal (serverless)**
- H100 $0,002778/s = **~$4,56–$4,76/h**. B200 $6,25/h.
- Cobra por segundo; ideal para spikes.

#### **Together AI**
- Pricing por modelo (LLM tokens) e dedicated endpoints. Reservas >6 dias para HGX H100/H200/B200/GB200.
- Não publica $/GPU-h; usuário precisa consultar.

#### **Replicate**
- Per-second billing, mas tarifa não é simples $/h; cobra por execução.

#### **Cudo Compute**
- 8× H100 ~$19,60/h — caríssimo em multi-GPU on-demand. Reservas longas mais competitivas.

#### **Massed Compute**
- H100 SXM/NVL/PCIe disponíveis; preços não publicados em tabela; checar com vendas.

#### **Genesis Cloud (Europa)**
- Cluster HGX H100/H200/B200 com InfiniBand 3,2Tbps. RTX A5000 a partir de $0,25/h.

#### **Civo, Atlantic.net, Yotta, Salad**
- Civo: oferece H100/A100/B200 on-demand; preços não detalhados em snapshots públicos abrangentes.
- Salad: distributed (consumer GPUs idle); cobra $0,004/h por vCPU + $0,001/h/GB RAM + GPU hourly. Save up to 90%. Confiabilidade baixa, mas barato pra batch.

#### **ThunderCompute**
- H100 a partir de **$1,38/h** (mais barato H100 publicado). RTX A6000 a $0,27/h.
- Modelo: GPU "compartilhada" via abstração CUDA — boa pra inference, **ruim para training intensivo**.

#### **PrimeIntellect, Shadeform, OblivusCloud (marketplace)**
- PrimeIntellect: H100 marketplace **$1,50–$4,00/h**; agrega 15+ clouds.
- Shadeform: agregador puro; melhor preço varia hora a hora.
- OblivusCloud: presença pequena; pouca pricing pública.

#### **AceCloud, Cirrascale, Latitude.sh, Nscale**
- AceCloud: on-demand + spot disponíveis; preços não detalhados em busca pública.
- Cirrascale: bare-metal corporativo; tipicamente $3–4/GPU-h reservado.
- Latitude.sh: H100 disponível; preços não públicos snapshot.
- Nscale: provedor europeu; preços n/d em busca pública.

---

## 3. Top 5 mais baratos por GPU (snapshot abr–maio 2026)

### H100 SXM (spot)
1. **ThunderCompute — $1,38/h** (compartilhada CUDA)
2. **Vast.ai — $1,49/h** (marketplace promoção)
3. **Voltage Park — $1,99–2,00/h**
4. **Spheron — $2,01/h**
5. **DataCrunch (Verda) — $2,29/h**

### H100 SXM (on-demand dedicado)
1. **Hyperstack — $2,40/h**
2. **GMI Cloud — $2,40/h**
3. **RunPod Secure — $2,69/h**
4. **Lambda — $2,86/h (PCIe) / $3,78 (SXM)**
5. **CoreWeave — $4,25/h (PCIe)**

### H200 (on-demand)
1. **GMI Cloud — $2,50/h**
2. **RunPod — $3,59/h**
3. **Jarvislabs — $3,80/h**
4. **Spheron — $4,54/h**
5. **CoreWeave / OCI — $10/h**

### B200 (best of)
1. **Reserva 36m via getdeploying — $2,25/h**
2. **RunPod (1-yr commit) — $4,24/h**
3. **RunPod on-demand — $4,99/h**
4. **Lambda — $6,08/h**
5. **Modal serverless — $6,25/h**

### A100 80GB (spot)
1. **Vast.ai — $0,67/h**
2. **DataCrunch — $0,80/h**
3. **RunPod Community — $1,19/h**
4. **Lambda on-demand — $1,48/h**
5. **Hyperscaler spot — ~$1,80/h**

### RTX 4090 / 5090 (spot)
1. **Vast.ai 4090 — $0,10–0,29/h** / **5090 — $0,13–0,35/h**
2. **CloudRift 5090 — $0,65/h on-demand**
3. **RunPod Community — 4090 $0,34, 5090 $0,99**
4. **Spheron 5090 — $0,86/h**
5. **Salad (consumer 4090 distribuído) — sub-$0,30/h dependendo de spot**

---

## 4. Tendência de preço 2024 → 2026

| GPU | Q1 2024 | Q4 2024 | Q4 2025 | Maio 2026 | Variação |
|---|---|---|---|---|---|
| H100 SXM (mediano spot) | $7–$10 | $4–$6 | $2,00–$2,50 | **$2,29 mediano / $1,38 piso** | **−72%** |
| H100 SXM (AWS on-dem) | $7,38 | $5,80 | $3,93 | **$3,90–$4,20** | **−45%** após corte AWS jun/2025 |
| H200 (mediano) | n/a (ainda não GA) | $6–$8 | $3,80–$5,00 | **$3,62–$4,54** | tendência de queda; H200 +19% nominal entre abr/25 e mai/26 (oferta apertada por demanda B200 atrasada) |
| B200 (mediano) | n/a | n/a (lançamento Q4/25) | $8–$12 | **$4,99 (RunPod) / $2,25 reserva 36m** | descida agressiva conforme TSMC ramp Blackwell |
| A100 80GB | $2,30 | $1,80 | $1,49 | **$1,29–$1,57** | **−40%** desde 2024 |
| RTX 4090 | $0,80 | $0,55 | $0,40 | **$0,29–$0,39 spot** | **−60%** desde 2024 |

**Eventos-chave:**
- **Jun/2025:** AWS corta P5 em ~44% (H100 mainstream).
- **Out/2025:** RunPod obtém SOC2 II.
- **Q4/2025:** B200 GA em RunPod, Lambda, CoreWeave, Genesis.
- **Dez/2025–Jan/2026:** spike de **+10%** em preços H100 (de $2,00 → $2,20) durante onda de demanda de inference.
- **Mar/2026:** preços B200 começam a quebrar a barreira dos $5/h on-demand.
- **Abr/2026:** B200 spot bate $2,25/h em pico-baixo em provedores marketplace.

**Outlook restante 2026:** consenso aponta H100 <$2/h sustentado por meio do ano e B200 estabilizando em $2,50–$3,00/h on-demand até Q4. H200 deve cair 15–20% conforme B200 absorve demanda premium.

---

## 5. Spot reliability — como cada provedor se comporta

| Provedor | Modelo spot | Taxa de interrupção típica | Aviso prévio | Notas |
|---|---|---|---|---|
| **AWS Spot (P5/H100)** | Bid + reclaim | **4,1% por hora** (acima do 5% médio do parque) | 2 min | Concentra interrupção em horários de pico de demanda (tarde EUA) |
| **GCP Spot (A3)** | Preempção | <5% típico, mas spread pequeno em A3 | 30s | Preço só recalcula a cada 30 dias |
| **Azure Spot (ND v5)** | Eviction policy | varia 5–15% | 30s | Eviction "delete" ou "deallocate" |
| **RunPod Community** | Mercado peer; preempção sem aviso garantido | **Médio-alto** em GPUs disputadas | Não garantido | Preço ~50% do Secure |
| **RunPod Secure** | On-demand puro | Praticamente zero | n/a | SLA real |
| **Vast.ai interruptible** | Mercado bid | Alta (host pode revogar a qualquer momento) | host-dependent | Marketplace com hosts não-padronizados |
| **Voltage Park spot** | Spot estilo AWS | 5–10% | 2 min | Mais previsível que marketplace |
| **CoreWeave Spot** | Spot puro | 10–20% típico | minutos | Desconto de até 54% |
| **Salad** | Distributed (consumer) | **Muito alta** (PCs domésticos podem desligar) | nenhum | Só pra batch interrupção-tolerante |

**Recomendação operacional:** rodar com **checkpoint a cada N segundos** se usar spot. Para Qwen 72B + DeepSeek 70B, custo de re-iniciar sessão é alto (5–10min carregando pesos), então spot só compensa se o pipeline for interruption-aware.

---

## 6. Storage e egress

| Provedor | Egress | Storage frio ($/GB/mês) | Storage quente | Ingress |
|---|---|---|---|---|
| AWS | $0,08–$0,12/GB | S3 IA $0,0125 | EBS gp3 $0,08 | grátis |
| GCP | $0,08–$0,12/GB | Coldline $0,004 | SSD persistente $0,17 | grátis |
| Azure | $0,08–$0,087/GB | Cool $0,01 | Premium SSD $0,15 | grátis |
| OCI | **10 TB grátis/mês**, $0,0085/GB depois | Object $0,0085 | Block $0,0255 | grátis |
| **RunPod** | **grátis** | $0,07/GB | NVMe persistente | grátis |
| **CoreWeave** | **grátis** | $0,015 (cold) → $0,070 (distributed) | $0,070 | grátis |
| **Lambda** | **grátis** | n/d (incluído) | n/d | grátis |
| **Voltage Park** | **grátis** | n/d | incluído | grátis |
| **Vast.ai** | host-dependente, geralmente grátis até cota | host-dependente | host-dependente | host-dependente |

**Para o pipeline do usuário** (vídeos 500MB–2GB + modelos 80–200GB):
- Pull dos modelos **uma única vez** por instância: 200GB no AWS = ~$24 em egress se vier de outro lugar; **zero em RunPod/CoreWeave/Lambda/Voltage Park**.
- Stream de vídeos: 1.000 vídeos de 1GB = 1 TB. Em hyperscaler = $80–$120 só de egress; em neo-cloud = $0.
- **Conclusão:** orçar **NUNCA** rodar batch grande em hyperscaler sem cache local. Neo-clouds são 40–85% mais baratos no compute *e* eliminam fee de transfer.

---

## 7. Multi-GPU (2× H100 / 8× H100) e desconto de nó

- **Bundle 8× H100 HGX** dá descontos consistentes de **10–20%** vs 8 GPUs separadas no mesmo provedor (NVLink/InfiniBand já incluso). Exemplos:
  - GMI Cloud 8× H100 cluster: $4,39/GPU-h on-demand (vs $5–$6 single-GPU em comparáveis).
  - CoreWeave 8× H100 HGX bundle: $6,15/GPU-h vs $4,25 PCIe single (penalidade por SXM/NVLink, não desconto).
  - AWS p5.48xlarge: ~$3,90/GPU-h on-demand.
- **2× H100 (Qwen 72B tensor-parallel):** raramente há desconto explícito — geralmente paga 2× single-GPU. Exceção: provedores que vendem só por nó (CoreWeave/Lambda 1-Click) tipicamente exigem 8 mínimo.
- **Recomendação para 2× H100 com Qwen 72B:** RunPod Secure 2× H100 SXM custa ~$5,38/h; Hyperstack reserved 2× = ~$3,80/h; Vast.ai 2× H100 spot = ~$3,00/h se marketplace tiver host com 2 placas no mesmo nó.

---

## 8. Reservas — quando vale a pena commit

| Termo | Desconto típico | Quando faz sentido |
|---|---|---|
| 1 mês | 10–15% | Validação de pipeline (suficiente para Valbot) |
| 3 meses | 20–30% | Beta de produto; ainda permite abandonar |
| 6 meses | 30–40% | Produção early-stage com volume previsível |
| 1 ano | 40–50% | Produção estável, throughput conhecido |
| 3 anos | **60–84%** | Apenas quem tem orçamento de infra dedicada |

Exemplos numéricos:
- **B200 RunPod:** on-demand $4,99 → 6m commit $4,34 (−13%) → 1y $4,24 (−15%).
- **TPU Trillium:** on-demand $2,70 → 1y $1,89 (−30%) → 3y $1,22 (−55%).
- **B200 marketplace 36m floor:** $2,25 (vs ~$14 cap on-demand, −84%).
- **AWS Savings Plan 3y:** ~$1,90/GPU-h H100 (vs $4,20 on-demand, −55%).

**Para o caso Valbot** (pipeline batch, vídeo a vídeo, ~10s–60s por vídeo): commit longo só faz sentido quando volume diário cruza ~12h/dia continuous. Antes disso, **on-demand em RunPod/Hyperstack/Voltage Park** é o ponto ótimo.

---

## 9. Recomendação operacional para a carga Valbot

**Restrições da carga:**
- Qwen2.5-VL 72B FP8: ~80GB VRAM com KV cache; cabe em 1× H100 80GB justinho ou 2× H100 confortável.
- DeepSeek-R1 70B FP8: idem.
- Whisper-v3-turbo: ~3GB; trivial.
- Co-DETR + Sapiens 2B: <10GB combinados.
- Ensemble multi-pass = picos de 110–140GB se rodar todos juntos → **2× H100 ou 1× H200 (141GB)** é o sweet spot.

**Top 3 placas custo-efetivas para o pipeline:**

1. **H200 141GB single-GPU em GMI Cloud / RunPod ($2,50–$3,59/h on-demand)** — única placa que segura todo o ensemble sem tensor-parallel. Latência mais previsível. Custo por vídeo (~60s alvo): $0,04–$0,06.

2. **2× H100 SXM em Hyperstack / Voltage Park / RunPod ($4–$5/h por par)** — exige tensor-parallel mas mais barato em USD/h efetivo. Custo por vídeo: $0,07–$0,08.

3. **B200 192GB em RunPod ou marketplace ($2,25 reservado / $4,99 on-demand)** — 3–4× throughput de H100; se atingir 15–20s/vídeo, custo cai para $0,02–$0,04. Recomendado quando marketplace tiver oferta 36m a $2,25.

**Top 3 provedores recomendados:**

1. **RunPod (Secure Cloud para produção, Community para batch interruption-tolerant)** — sem egress, SOC2/HIPAA, billing por segundo, 3 datacenters EUA + Europa. **Recomendação primária**.

2. **Hyperstack** — H100 SXM $2,40/h on-demand é piso muito agressivo; reservas $1,90. Ótimo plano B se RunPod ficar lotado.

3. **Voltage Park** — H100 $1,99 on-demand sem fees ocultos. Ótimo para experimentos longos sem commit.

**Watchpoints (riscos, pegadinhas):**

- **Spot é falsa economia para 70B+ models.** Carregar pesos leva 5–10min; uma preempção mata o orçamento de várias horas spot.
- **Vast.ai marketplace varia drasticamente em performance disco.** Hosts com SSD lento dobram tempo de loading de modelo. Filtrar por `disk_bw>1500MB/s` e `inet_down>500Mbps`.
- **Hyperscalers cobram egress brutal.** 1 TB de vídeo no AWS = ~$90 só de transferência. Fica 4× mais caro que o GPU-time em si para batch alto.
- **B200 ainda tem oferta limitada.** Se cluster cair, fallback para H200 deve estar pronto. Não confiar em SLA de single-provider para B200 em maio/2026.
- **Preço H100 voltou a subir 10% em Dez/2025–Jan/2026** — ciclo de demanda inference NVIDIA cria spikes; lock-in de 1m faz sentido pra suavizar.
- **Modal/Replicate cobram per-second; pra cargas com cold start de 2min carregando Qwen, fica caríssimo** ($0,15+ por inferência).
- **OCI tem floor fixo $10/GPU-h** — ignorar para batch a menos que precise da rede InfiniBand 3,2Tbps de Supercluster.
- **TPU é tentador no preço, mas Qwen2.5-VL não tem suporte oficial JAX** — re-implementar é caro em engenharia.

---

## 10. Fontes consultadas

- getdeploying.com/gpus (compara 42–58 provedores; principal agregador)
- computeprices.com (preços live por GPU/provedor)
- thundercompute.com/blog/* (séries históricas e snapshots mensais)
- jarvislabs.ai/blog/h100-price, /h200-price, /a100-price
- runpod.io/pricing + runpod.io/articles/*
- vast.ai/pricing
- lambda.ai/pricing
- coreweave.com/pricing
- voltagepark.com/pricing
- hyperstack.cloud/gpu-pricing
- oracle.com/cloud/price-list
- spheron.network/blog/gpu-cloud-pricing-comparison-2026
- silicondata.com/blog (séries de mercado spot H100)
- modal.com/blog/nvidia-b200-pricing
- gmicloud.ai/blog (séries 2025–2026)
- intuitionlabs.ai/articles/h100-rental-prices-cloud-comparison
- aws.amazon.com/ec2/spot/pricing/, ec2/capacityblocks/pricing/
- cloud.google.com/spot-vms/pricing, /tpu/pricing
- instances.vantage.sh (Azure ND H100 v5)
- northflank.com/blog (cheapest providers comparison)
- inworld.ai/resources/nvidia-b200-gpu-cloud
- deploybase.ai/articles/* (RunPod, Lambda, Modal, B200 deep dives)

Snapshot temporal: principais valores convergem para janela **abril–maio 2026** com pequenas variações intradiárias. Mercado spot continua altamente volátil; revalidar antes de qualquer commit acima de 1 mês.
