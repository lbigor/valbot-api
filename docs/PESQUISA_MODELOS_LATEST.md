# Pesquisa: Versões Mais Recentes de Qwen-VL e YOLO em 2026

**Data da pesquisa:** 2026-05-02
**Pipeline atual LaudoAI:** Qwen2.5-VL-7B/72B (jan/2025), Qwen2.5-Omni-7B (mar/2025), YOLOv11s/YOLOv11s-pose (set/2024)

---

## Resumo Executivo (~300 palavras)

A paisagem de modelos VLM e detectores de objetos evoluiu de forma agressiva entre o final de 2025 e o início de 2026. **Tudo que o LaudoAI usa hoje tem sucessor direto, com licença Apache 2.0 mantida e com ganhos materiais em precisão e latência.**

Do lado **Qwen**, a família Qwen3-VL foi liberada em ondas entre setembro e outubro de 2025 (235B-A22B em 2025-09-23; 30B-A3B em 2025-10-04; 4B/8B em 2025-10-15; 2B/32B em 2025-10-21). Saltos importantes: contexto nativo 256K (expansível a 1M), OCR em 32 idiomas (vs. 10 do Qwen2.5-VL), DeepStack para features ViT multi-camada, MRoPE intercalado para vídeo, e variantes "Thinking" com cadeia de raciocínio explícita. Em março de 2026 saiu **Qwen3.5-Omni** (sucessor direto do Omni-7B usado hoje), com latência audio-vídeo de 507 ms em streaming, 113 idiomas em ASR e 36 em TTS — relevante porque a arquitetura v3.1 do LaudoAI depende de ensemble áudio+vídeo.

Do lado **YOLO**, três marcos: YOLOv12 (fev/2025, attention-centric), YOLOv13 (jun/2025, hypergraph correlation, +3.0 mAP vs. YOLO11-N), e o oficial **Ultralytics YOLO26** (jan/2026), que removeu DFL, é nativamente NMS-free, roda 43% mais rápido em CPU, e mantém a API `ultralytics` idêntica.

### As 3 ações imediatas

1. **Trocar Qwen2.5-VL-72B → Qwen3-VL-32B-Thinking-FP8 no H100.** Cabe em 1×H100 80GB sem AWQ, é ~2× mais rápido e empata/supera o 72B em MMMU/OCRBench. Atualizar `process_vision_info()` para `image_patch_size=16, return_video_metadata=True`.
2. **Trocar `yolo11s.pt`/`yolo11s-pose.pt` → `yolo26s.pt`/`yolo26s-pose.pt`.** Drop-in via Ultralytics CLI, sem mudança de imports. Pesos não são compatíveis (rebaixar), mas a API é idêntica. Ganho: NMS-free (latência -43% em CPU) e melhor recall em objetos pequenos (placas distantes).
3. **Trocar Qwen2.5-Omni-7B → Qwen3-Omni-30B-A3B-Instruct (MoE, ~3B ativos).** Apache 2.0, 234 ms first-packet, AWQ-4bit já disponível na comunidade (cabe em 24GB), SOTA em 32/36 benchmarks de áudio-visual.

---

## 1. Tabela Qwen-VL — versões disponíveis (maio/2026)

| Modelo | Release | Tamanho (params) | VRAM mín FP16 | VRAM mín AWQ-4bit | MMMU | OCRBench | Notas |
|---|---|---|---|---|---|---|---|
| Qwen2.5-VL-7B (atual Mac) | 2025-01 | 7B dense | ~16 GB | ~7 GB | ~58 | ~86 | Pipeline atual; OCR em 10 idiomas |
| Qwen2.5-VL-72B (atual H100) | 2025-01 | 72B dense | ~145 GB (FP16) | ~40 GB | 70.2 | 88.6 (MMBench-EN) | Cabe em 1×H100 só com AWQ-4 |
| **Qwen3-VL-2B** | 2025-10-21 | 2B dense | ~5 GB | ~2 GB | — | — | Edge / mobile |
| **Qwen3-VL-4B** | 2025-10-15 | 4B dense | ~10 GB | ~4 GB | — | — | Substituto Mac M-series |
| **Qwen3-VL-8B-Instruct** | 2025-10-15 | 8B dense | ~18 GB | ~8 GB | superior ao 2.5-VL-7B | melhor (32 idiomas) | **Recomendado Mac** |
| **Qwen3-VL-8B-Thinking** | 2025-10-15 | 8B dense | ~18 GB | ~8 GB | melhor reasoning | igual | CoT explícito |
| **Qwen3-VL-30B-A3B** (MoE) | 2025-10-04 | 30B total / ~3B ativos | ~65 GB | ~18 GB | competitivo c/ 72B-2.5 | superior | Excelente custo-benefício |
| **Qwen3-VL-32B-Instruct/Thinking-FP8** | 2025-10-21 | 32B dense | ~65 GB FP16 / ~32 GB FP8 | ~16 GB | supera Qwen2.5-VL-72B | supera | **Recomendado H100 (substitui 72B)** |
| **Qwen3-VL-235B-A22B** | 2025-09-23 | 235B total / 22B ativos | ~470 GB FP16 | ~120 GB | SOTA open | SOTA open | Multi-GPU only |
| Qwen3-VL Technical Report | 2025-11-27 | — | — | — | — | — | arXiv:2511.21631 |

**Capacidades novas (Qwen3-VL):**
- Contexto nativo **256K tokens** (expansível 1M) — vs. 128K do 2.5-VL.
- **DeepStack** para features ViT multi-camada (ganho em detalhes finos como placas e overlays).
- **Interleaved-MRoPE** para modelagem espaço-temporal em vídeo (relevante para LaudoAI: detecta sequência de eventos no vídeo).
- **Text-based time alignment** — timestamps explícitos em vídeo (cinto-frame-X, sinal-frame-Y vira nativo).
- OCR em **32 idiomas** (vs. 10), com robustez a luz baixa, blur e texto inclinado.
- Variantes **Thinking** com chain-of-thought (útil para "examinador-oráculo bayesiano" no LaudoAI).

**Licença:** Apache 2.0, comercial sem restrições (igual ao 2.5-VL).

**Tooling em maio/2026:**
- vLLM ≥ 0.11.0 já suporta Qwen3-VL (recipe oficial em docs.vllm.ai).
- SGLang suporta e está **3× mais rápido que vLLM** em Qwen3-VL no H100 PCIe (50–60 ms/img vs. 170–180 ms/img — issue #29869 do vllm).
- TensorRT-LLM já suporta família Qwen3.

---

## 1b. Qwen-Omni evolução

| Modelo | Release | Tamanho | VRAM | Latência first-packet | Idiomas ASR/TTS |
|---|---|---|---|---|---|
| Qwen2.5-Omni-7B (atual) | 2025-03-26 | 7B | ~18 GB | ~600 ms | 19 / 10 |
| **Qwen3-Omni-30B-A3B-Instruct** | 2025-09 | 30B MoE (3B ativos) | ~65 GB FP16 / ~18 GB AWQ-4 | **234 ms áudio, 507 ms A+V** | mais amplo |
| **Qwen3-Omni-30B-A3B-Thinking** | 2025-09 | 30B MoE | igual | igual | igual |
| **Qwen3.5-Omni** (Plus/Flash/Light) | 2026-03-30 | variável | — | comparável | **113 / 36** |

**Qwen3-Omni:** SOTA em 22/36 benchmarks áudio-visuais; supera Gemini-2.5-Pro, GPT-4o-Transcribe e Seed-ASR. AWQ-4bit/8bit já publicados pela comunidade no HuggingFace (`cyankiwi/Qwen3-Omni-30B-A3B-Instruct-AWQ-4bit`). Apache 2.0.

---

## 2. Tabela YOLO — versões disponíveis (maio/2026)

| Versão | Release | Família/Autor | Variantes | mAP@COCO (n→x) | Latência T4 (n) | Parâmetros (n→x) | NMS-free? |
|---|---|---|---|---|---|---|---|
| **YOLOv11** (atual) | 2024-09 | Ultralytics | n/s/m/l/x | 39.4 → 54.7 | ~1.5 ms | 2.6M → 56.9M | Não |
| **YOLOv12** | 2025-02-18 | sunsmarterjie (NeurIPS 2025) | n/s/m/l | 40.6 → 53.2 | 1.64 ms | similar v11 | Não (DFL retido) |
| **YOLOv13** | 2025-06 (arXiv 2506.17733) | iMoonLab (IIT) | n/s/l/x | YOLOv13-N: +3.0 vs v11-N, +1.5 vs v12-N | similar | menor | Não |
| **YOLO26** (oficial Ultralytics) | 2026-01-14 | Ultralytics | n/s/m/l/x | melhor que v11/v12 em scale L+ | **CPU −43% vs v11** | 2.4M / 9.4M / 20M / 24-25M / 55-57M | **Sim (nativo)** |
| **YOLO26-pose** | 2026-01-14 | Ultralytics | n/s/m/l/x | até 71.6 mAP50-95 (x) | 1.8 ms (n) | similar acima | Sim |
| **YOLO-World V2.1** | 2025-02 | AILab-CVC | s/m/l | 35.4 LVIS / 52 FPS V100 | — | — | Open-vocab |
| **RT-DETRv2** | 2024-2025 | lyuwenyu | r18/r34/r50/r101 | 55.3 (R50) | 100-118 FPS | — | Sim |

**Evolução chave (YOLO26 vs. YOLO11):**
- **DFL removido** — simplifica inference, melhora portabilidade edge.
- **NMS-free nativo** — o que treina é o que deploya, sem post-processing.
- **ProgLoss** + **STAL** — Small-Target-Aware Label Assignment: ganho real para placas distantes em vídeo (relevante para o pipeline LaudoAI que depende de detectar R-1, sinais).
- **MuSGD optimizer** — convergência mais rápida em fine-tune.
- **5 tarefas no mesmo framework**: detecção, segmentação, pose, OBB, classificação.

**RT-DETRv2 vs. YOLO26 (maio/2026):**
- Em GPU farto, RT-DETRv2-R50 (55.3 mAP) ainda compete bem — mas na L+ scale o YOLO26 fica par a par com latência muito menor em CPU/edge.
- RT-DETR continua exigindo memória e tempo de treino significativamente maiores (Transformer).
- **Recomendação para LaudoAI:** ficar em YOLO26, já que o overhead VLM (Qwen3-VL) já come o "transformer budget" da pipeline.

**YOLO-World V2.1 (open-vocab):** lançou nova versão fev/2025 com pesos pré-treinados e suporte a image prompts. **Não recomendo para detectar placas BR sem fine-tune** — o detector clássico (YOLO26 + crops em `sinalizacao/`) com VLM atômico continua mais barato e mais alinhado com a "filosofia central" do LaudoAI (gráfico simbólico + pergunta atômica).

---

## 3. Migration path — `yolo11s` → `yolo26s`

A boa notícia: **a API Ultralytics é idêntica.**

### Passos (toda alteração no código):

```python
# ANTES
from ultralytics import YOLO
model = YOLO("yolo11s.pt")
pose = YOLO("yolo11s-pose.pt")

# DEPOIS
from ultralytics import YOLO
model = YOLO("yolo26s.pt")        # baixa automaticamente do mirror Ultralytics
pose = YOLO("yolo26s-pose.pt")
```

### Pré-requisitos:
- `pip install -U ultralytics` (versão pós-jan/2026 inclui YOLO26).
- **Pesos NÃO são compatíveis** entre YOLO11 e YOLO26 (arquitetura mudou). Você baixa novos `.pt` pré-treinados em COCO — para o LaudoAI isso é o que já é feito (uso COCO genérico, sem fine-tune próprio).
- **NMS-free implica:** `model.predict(..., agnostic_nms=False)` agora é no-op. Se o pipeline tem qualquer override de `iou_threshold` no NMS, isso não faz mais nada. **Verificar `pipeline_*.py` do LaudoAI para flags antigas.**
- Output `results[0].boxes` e `.keypoints` mantêm shape e API.

### Re-treino necessário?
**Não para o LaudoAI** — o uso é apenas detecção COCO genérica (pessoa, carro) + pose humana. Os pesos pré-treinados oficiais já cobrem isso melhor que YOLO11.

### Se houvesse fine-tune (não há hoje no LaudoAI):
- Dataset YOLO format é idêntico (`labels/*.txt` com `class x y w h`).
- Comando: `yolo train model=yolo26s.pt data=meu.yaml epochs=100`.
- MuSGD vira optimizer default — não precisa configurar.

---

## 4. Migration path Qwen — Qwen2.5-VL → Qwen3-VL

### API Hugging Face — diferenças concretas:

```python
# ANTES (Qwen2.5-VL)
from qwen_vl_utils import process_vision_info
image_inputs, video_inputs, video_kwargs = process_vision_info(
    messages, return_video_kwargs=True
)
# image_patch_size implícito: 14
# image resize: múltiplo de 28

# DEPOIS (Qwen3-VL)
from qwen_vl_utils import process_vision_info
image_inputs, video_inputs, video_kwargs, video_metadata = process_vision_info(
    messages,
    image_patch_size=16,           # mudou de 14 → 16
    return_video_kwargs=True,
    return_video_metadata=True,    # novo: timestamps explícitos por frame
)
# image resize: múltiplo de 32
```

### vLLM:
- Atualizar para `vllm>=0.11.0`.
- Considerar **migrar para SGLang** — 3× mais rápido em Qwen3-VL no H100.
- Cuidado com system prompts múltiplos: vLLM concatena com `\n\n` em vez de `\n`.

### Prompt format:
- Chat template idêntico (`<|im_start|>user`, etc.).
- **Novidade útil:** prompts especiais `qwenvl markdown` e `qwenvl html` para parsing de documentos — útil se o LaudoAI for parsear telas overlay como tabela.
- Variantes **Thinking** geram bloco `<thinking>...</thinking>` antes da resposta — para o "examinador-oráculo bayesiano" do LaudoAI, isso é ouro: pode-se extrair o LLR diretamente do raciocínio.

### Reranking de tokens:
Não há mudança fundamental. Os tokens visuais especiais (`<|vision_start|>`, `<|vision_end|>`, `<|image_pad|>`) mantêm IDs (apesar do vocabulary refresh). Validar com smoke test atômico antes de virar pipeline.

---

## 5. Recomendação final (maio/2026)

### Para o pipeline LaudoAI **hoje**:

| Slot atual | Substituir por | VRAM | Justificativa |
|---|---|---|---|
| Qwen2.5-VL-7B (Mac) | **Qwen3-VL-8B-Instruct** ou **-Thinking** | ~18 GB FP16 / ~8 GB AWQ-4 | Mesmo footprint, 32 idiomas OCR, 256K contexto, Thinking dá CoT pro examinador-oráculo |
| Qwen2.5-VL-72B (H100) | **Qwen3-VL-32B-Thinking-FP8** | ~32 GB FP8 em 1×H100 80GB | Substitui 72B com folga de VRAM, ~2× mais rápido, supera em OCR/MMMU. Em SGLang fica ainda mais rápido |
| Qwen2.5-Omni-7B | **Qwen3-Omni-30B-A3B-Instruct AWQ-4** | ~18 GB | SOTA áudio-visual, 234 ms latência, perfeito pra arquitetura v3.1 |
| YOLOv11s | **YOLO26s** | irrelevante | API igual, NMS-free, melhor recall em placas pequenas |
| YOLOv11s-pose | **YOLO26s-pose** | irrelevante | RLE pose head: melhor em mão-no-volante (oclusão parcial) |

### Trade-offs:
- **Latência:** Qwen3-VL-32B-FP8 é ~2× mais rápido que 72B-AWQ — ganho real em produção.
- **VRAM Mac:** Qwen3-VL-8B no Mac M-series via MLX/llama.cpp deve funcionar igual ao 2.5-VL-7B (apenas re-quantizar). Se quiser cortar latência no Mac, **Qwen3-VL-4B** é nova opção barata.
- **Risco:** Thinking models são mais lentos (~1.5–2× tokens gerados). Para o LaudoAI, onde a pergunta é atômica e o output é curto, vale a pena pelo CoT auditável.

### O que **NÃO** mudar agora:
- Continuar com filosofia "gráfico 2D simbólico + pergunta atômica" — modelo novo só amplifica isso.
- Manter biblioteca `sinalizacao/` few-shot crops — relevância continua.
- Manter detector clássico antes de VLM — não vale migrar pra YOLO-World ainda.

### Especulativo / não confirmado:
- **Qwen3.5-VL** ou **Qwen4-VL** — não há sinal de release até maio/2026. Qwen3.5-Omni saiu, mas a versão "VL pura" ficou em Qwen3-VL.
- **YOLOv14** — sem indicação. O ciclo Ultralytics próximo deve ser YOLO27 (2027).
- TensorRT-LLM com suporte first-class a Qwen3-VL multimodal: **status incerto** em maio/2026; vLLM e SGLang são as opções maduras.

---

## Fontes consultadas

- [Qwen3-VL GitHub (QwenLM)](https://github.com/QwenLM/Qwen3-VL)
- [Qwen3-VL Technical Report (arXiv 2511.21631)](https://arxiv.org/abs/2511.21631)
- [Qwen3-VL-8B-Instruct HuggingFace](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
- [Qwen3-VL-32B-Thinking-FP8 HuggingFace](https://huggingface.co/Qwen/Qwen3-VL-32B-Thinking-FP8)
- [Qwen3-Omni Technical Report (arXiv 2509.17765)](https://arxiv.org/abs/2509.17765)
- [Qwen3-Omni GitHub](https://github.com/QwenLM/Qwen3-Omni)
- [Qwen3.5-Omni anúncio (MarkTechPost, 2026-03-30)](https://www.marktechpost.com/2026/03/30/alibaba-qwen-team-releases-qwen3-5-omni-a-native-multimodal-model-for-text-audio-video-and-realtime-interaction/)
- [Ultralytics YOLO26 Docs](https://docs.ultralytics.com/models/yolo26/)
- [YOLO26 Key Architectural Enhancements (arXiv 2509.25164)](https://arxiv.org/pdf/2509.25164)
- [Ultralytics YOLO Evolution Overview (arXiv 2510.09653)](https://arxiv.org/abs/2510.09653)
- [YOLOv12 GitHub (NeurIPS 2025)](https://github.com/sunsmarterjie/yolov12)
- [YOLOv13 paper (arXiv 2506.17733)](https://arxiv.org/abs/2506.17733)
- [YOLOv13 GitHub (iMoonLab)](https://github.com/iMoonLab/yolov13)
- [YOLO-World GitHub (AILab-CVC)](https://github.com/AILab-CVC/YOLO-World)
- [RT-DETR GitHub (lyuwenyu)](https://github.com/lyuwenyu/RT-DETR)
- [Qwen3-VL vLLM Recipe](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3-VL.html)
- [vLLM 3x slower than SGLang em Qwen3-VL (issue #29869)](https://github.com/vllm-project/vllm/issues/29869)
- [vLLM vs TensorRT-LLM vs SGLang H100 Benchmarks 2026 (Spheron)](https://www.spheron.network/blog/vllm-vs-tensorrt-llm-vs-sglang-benchmarks/)
- [YOLO26 vs YOLO11 (Ultralytics Compare)](https://docs.ultralytics.com/compare/yolo26-vs-yolo11/)
- [YOLO26 Pose Estimation Tutorial (LearnOpenCV)](https://learnopencv.com/yolo26-pose-estimation-tutorial/)
- [Best Object Detection Models 2026 (Ultralytics blog)](https://www.ultralytics.com/blog/the-best-object-detection-models-of-2025)
- [Qwen3 Apache 2.0 License](https://qwenlm.github.io/blog/qwen3/)
- [Qwen 3 Hardware Guide (Compute Market)](https://www.compute-market.com/blog/qwen-3-local-hardware-guide-2026)
- [cyankiwi/Qwen3-Omni-30B-A3B-Instruct-AWQ-4bit HuggingFace](https://huggingface.co/cyankiwi/Qwen3-Omni-30B-A3B-Instruct-AWQ-4bit)
