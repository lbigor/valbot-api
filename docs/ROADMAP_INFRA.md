# LaudoAI — Infraestrutura: Hoje vs Proposto

## Estrutura Atual

```
MacBook Pro (usuário)
│
├── Backend Python (tooling/dev_backend_stub.py) — 1 instância
├── Frontend Vite (localhost:5173) — 1 instância
├── Template-match NCC serial — 1 vídeo por vez
├── VLM: Claude Haiku via API Anthropic — pago por token
│     └── recebe gráfico 2D simbólico (não frame real)
├── YOLO custom — template-match local (13 crops hardcoded)
├── Storage local (storage/) — sem backup, sem fila
└── Processamento manual — usuário inicia cada análise
```

### Gargalos atuais

| Problema | Impacto |
|----------|---------|
| Serial: 1 vídeo/vez | ~60–90 min por vídeo completo |
| API Anthropic paga | ~$0.08–0.15 por vídeo (Haiku) |
| VLM nunca vê frame real | Perde nuances visuais (cinto preto em roupa escura, placa ocluída) |
| 13 crops hardcoded | Não generaliza para sinalizações novas |
| Sem fila de processamento | Não escala além de 5–10 vídeos/dia |
| Modelo pequeno (Haiku) | Hallucinations frequentes em perguntas de visão |
| Sem retro-treino automático | Examples.jsonl cresce mas não melhora modelo |

---

## Estrutura Proposta

```
Mac Studio M4 Max 128GB (Fase 1)
│
├── Ollama — Qwen2.5-VL 7B (online) / 72B (quando disponível)
│     └── recebe frame real + pergunta atômica — offline, grátis
├── Ray (Python) — 8 workers paralelos por vídeo
├── Backend FastAPI — 4 instâncias paralelas
├── MinIO local — S3-compatible, substitui storage/ plano
├── Label Studio — revisão humana anotada, exporta COCO/YOLO
├── MLflow — rastreia experimentos, mAP por iteração
└── Fila de processamento — todos os vídeos entram, processam overnight
│
Servidor Dedicado Linux (Fase 2)
│
├── 2× RTX 4090 48GB VRAM total
├── YOLO v8m / v8l fine-tune — treino em <2h para 10k imagens
├── LLaVA 34B / Qwen2.5-VL 72B — modelos grandes, máxima precisão
├── Vertex AI local (via docker) — pipeline ML gerenciado
└── Retro-treino automático semanal — examples.jsonl → novo best.pt
```

---

## Tempo Ganho por Fase

### Fase 0 — Hoje (MacBook Pro M2)

| Operação | Tempo atual |
|----------|------------|
| Template-match 1 vídeo (15 min) | ~25 min |
| Chamadas VLM por vídeo (~40 frames) | ~8 min (API Anthropic) |
| **Total por vídeo** | **~33 min** |
| Lote de 10 vídeos (serial) | **~5.5 horas** |
| Lote de 100 vídeos | **~55 horas (impossível)** |

### Fase 1 — Mac Studio M4 Max 128GB

| Operação | Tempo estimado | Ganho |
|----------|---------------|-------|
| Template-match 1 vídeo | ~6 min (4× cores) | **4× mais rápido** |
| VLM local Qwen2.5-VL 7B (~40 frames) | ~2.5 min (offline) | **3× mais rápido + grátis** |
| **Total por vídeo** | **~8.5 min** | **4× ganho** |
| Lote de 10 vídeos (8 workers paralelos) | **~17 min** | **19× ganho** |
| Lote de 100 vídeos | **~2.8 horas** | **viável overnight** |
| Lote de 1.000 vídeos | **~28 horas (2 noites)** | **viável em semana** |

### Fase 2 — + Servidor Dedicado Linux (2× RTX 4090)

| Operação | Tempo estimado | Ganho vs Fase 0 |
|----------|---------------|-----------------|
| Template-match 1 vídeo | ~3 min (GPU acelerado) | **8× mais rápido** |
| VLM Qwen2.5-VL 72B (~40 frames) | ~4 min (GPU local) | modelo maior, offline |
| **Total por vídeo** | **~7 min** | **5× ganho** |
| Lote de 10 vídeos | **~8 min** | **40× ganho** |
| Lote de 1.000 vídeos (paralelo Mac+Linux) | **~10 horas** | **processo em 1 noite** |
| Fine-tune YOLO v8m (10k imagens) | **~1.5 horas** | antes: inviável |
| Fine-tune YOLO v8l (50k imagens) | **~8 horas** | antes: inviável |

---

## Projeção de Melhoria por Modelo

Base atual: precisão estimada ~65% (cinto), ~55% (sinalização vertical).

| Modelo VLM | Parâmetros | Precisão estimada cinto | Precisão sinalização | Custo/chamada |
|------------|-----------|------------------------|---------------------|---------------|
| Claude Haiku (atual) | ~7B equiv. | ~65% | ~55% | $0.003/1k tokens |
| Qwen2.5-VL 7B (offline) | 7B | ~70% | ~62% | grátis |
| Gemma 3 27B (offline) | 27B | ~78% | ~72% | grátis |
| LLaMA 3.2 Vision 90B (offline) | 90B | ~84% | ~80% | grátis |
| **Qwen2.5-VL 72B (offline)** | **72B** | **~85%** | **~82%** | **grátis** |
| Gemini 1.5 Flash (API) | ~70B equiv. | ~87% | ~84% | $0.075/1M tokens |
| Gemini 1.5 Pro (API) | ~175B equiv. | ~91% | ~89% | $3.50/1M tokens |

> Projeção baseada em benchmarks públicos de VQA (Visual Question Answering) e OCR em cenas de trânsito.
> Ganho real depende de fine-tune com dataset DETRAN BR — modelos maiores offline superam Flash quando fine-tunados.

### Com fine-tune em dataset próprio (Fase 2+)

| Dataset tamanho | Modelo base | Precisão esperada pós-treino |
|-----------------|-------------|------------------------------|
| 500 exemplos | YOLO v8n | ~78% |
| 2.000 exemplos | YOLO v8m | ~85% |
| 5.000 exemplos | YOLO v8l | ~90% |
| 10.000 exemplos | YOLO v8x + Qwen2.5-VL 72B fine-tuned | **~93–95%** |

---

## O que Comprar — Valores em Dólar

### Fase 1 — Mac Studio M4 Max (imediato)

| Item | Especificação | Preço USD |
|------|--------------|-----------|
| **Mac Studio M4 Max** | 16-core CPU, 40-core GPU, 128GB RAM, 1TB SSD | **$2.999** |
| Thunderbolt SSD externo | 4TB Samsung T9 — storage dos vídeos | $280 |
| Switch Ethernet 2.5Gb | Caso adicione servidor futuro | $45 |
| **Total Fase 1** | | **$3.324** |

**Economia mensal em API (Haiku):** processando 200 vídeos/mês → ~$30/mês economizados.
**Payback:** ~9 anos pela economia de API — justificativa real é velocidade e escala, não economia de API.

### Fase 2 — Servidor Dedicado Linux (6–12 meses)

| Item | Especificação | Preço USD |
|------|--------------|-----------|
| **GPU 1: RTX 4090** | 24GB GDDR6X, PCIe 4.0 | **$1.750** |
| **GPU 2: RTX 4090** | idem | **$1.750** |
| CPU: Threadripper 7960X | 24-core, PCIe 5.0 | $1.400 |
| Placa-mãe TRX50 | Suporta 2× RTX 4090 + 128GB DDR5 | $550 |
| RAM: 128GB DDR5 ECC | 4× 32GB | $380 |
| PSU: 1600W Platinum | Para 2× 4090 | $280 |
| Case + cooler | Tower server Fractal Define 7 XL | $250 |
| NVMe: 2TB PCIe 5.0 | Dataset local | $180 |
| **Total Fase 2** | | **$6.540** |

### Fase 3 — Cloud Burst (opcional, escala >1.000 vídeos/dia)

| Item | Especificação | Custo |
|------|--------------|-------|
| GCS Standard | 10TB vídeos raw | $200/mês |
| Cloud Run jobs | 500 vídeos/dia em GPU A100 spot | ~$150/mês |
| BigQuery | Analytics examples.jsonl | ~$20/mês |
| **Total Fase 3** | Ativo apenas quando necessário | **~$370/mês** |

---

## Resumo Executivo

| Fase | Investimento | Throughput | Precisão estimada | Quando |
|------|-------------|------------|-------------------|--------|
| Hoje | $0 | 10 vídeos/dia | ~60% | agora |
| **Fase 1** | **$3.324** | **100+ vídeos/dia** | **~72%** | **comprar agora** |
| Fase 2 | $6.540 | 500+ vídeos/dia | **~88% (com fine-tune)** | 6–12 meses |
| Fase 3 | $370/mês | ilimitado | ~93% | quando escalar |

**Ação imediata:** Mac Studio M4 Max 128GB $2.999 + SSD externo 4TB $280 = **$3.279**.
Já na primeira semana: pipeline roda overnight sem intervenção, Qwen2.5-VL 7B local substitui Haiku, custo API zero.
