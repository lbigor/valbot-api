# VALBOT Analyzer — Sistema de Análise Automatizada de Provas Práticas do Detran

Pipeline para análise de vídeos 2×2 de provas práticas (VIP Intelbras) e geração de laudos estruturados das infrações detectadas.

---

## Status atual (2026-04-24)

- ✅ Pipeline de ingestão (grid 2×2 → 4 câmeras sincronizadas)
- ✅ Detector de keyframes (optical flow + histograma)
- ✅ Taxonomia completa de 10 infrações Res. 789/2020 e 1020/2025
- ✅ Catálogo de sinalização vertical (23 placas CONTRAN)
- ✅ Catálogo de sinalização horizontal (18 marcas viárias MBST Vol IV)
- ✅ 7 prompts Tier 1 (≥85% assertividade) para Claude API / Qwen2.5-VL
- ✅ Detectores OpenCV event-windowing (PARE texto, crosswalk, semáforo, parada)
- ✅ Orquestrador com janelas temporais adaptativas
- ✅ Integração CVAT (YOLO-NAS pré-anotação + labels VALBOT)
- ✅ Relatório PDF (WeasyPrint + Jinja, template adaptado para `taxonomia.py`)
- 🟡 Frontend React/Vite (portado de `valbot_old`, aguarda backend API)
- 🟡 Transcrição áudio Whisper (planejado)
- ⚠️ Pipeline end-to-end precisa integração OBD-II para Tier 4

---

## Estrutura do repositório

```
valbot-analyzer/
├── src/
│   ├── ingestion/
│   │   ├── grid_slicer.py          # Fatia grid 2×2 em 4 streams
│   │   └── keyframe_detector.py    # Seleciona frames relevantes
│   ├── rubrics/
│   │   ├── taxonomia.py            # 10 infrações Res. 789/1020
│   │   ├── sinalizacao_vertical.py # 23 placas CONTRAN
│   │   └── sinalizacao_horizontal.py # 18 marcas MBST
│   ├── prompts/
│   │   ├── base.py                 # Estrutura de prompt
│   │   └── tier1.py                # 7 prompts ≥85% assertividade
│   ├── analysis/
│   │   └── vlm_engine.py           # Claude API + Qwen local
│   ├── detectors/
│   │   ├── base.py                 # Interface BaseDetector
│   │   ├── traffic_light.py        # HSV + HoughCircles
│   │   ├── road_text.py            # Contornos brancos agrupados
│   │   ├── crosswalk.py            # Faixas perpendiculares paralelas
│   │   ├── stop_detector.py        # Optical flow denso
│   │   └── orchestrator.py         # Event-windowing completo
│   ├── reporting/
│   │   ├── pdf.py                  # render_pdf() — WeasyPrint + Jinja2
│   │   ├── adapter.py              # build_context() — detecções → LaudoContext
│   │   ├── schema.py               # TypedDict LaudoContext
│   │   └── templates/laudo.html    # Template A4 print-optimized
│   └── analyzer.py                 # CLI pipeline principal
│
├── frontend/                       # React 19 + Vite + TS (aguarda backend)
│   └── artifacts/valbot/            # app principal (pnpm monorepo)
│
├── docs/
│   ├── mapa_assertividade.md       # 22 infrações por % confidence
│   ├── prompts_tier1.md            # Especificação dos 7 prompts
│   └── relatorio_execucao_tier1.md # Resultados da execução real
│
├── tooling/cvat_workflow/
│   ├── README.md                   # Guia CVAT Docker no Mac M2
│   ├── valbot_labels.json           # 35 labels para Project CVAT
│   ├── generate_preannotations.py  # YOLO-NAS → .txt importável
│   └── consume_cvat_export.py      # CVAT export → dataset YOLO + laudo
│
├── configs/
│   └── references/
│       ├── contran_anexo_ii_placas.pdf          # Fonte oficial placas
│       └── mbst_vol_iv_sinalizacao_horizontal.pdf # Fonte oficial MBST
│
├── examples/
│   └── laudo_vid1.json             # Laudo de exemplo (execução real)
│
└── requirements.txt
```

---

## Quick start

### 1. Rodar ingestão básica

```bash
pip install opencv-python numpy
python -m src.analyzer video.mp4 --rubrica 789_2020 --output laudo.json
```

### 2. Usar detectores OpenCV (sem VLM)

```python
from pathlib import Path
from src.detectors.orchestrator import EventOrchestrator

orch = EventOrchestrator(sample_fps=2.0)
detections = orch.sweep(Path("video.mp4"))
# ~38s por vídeo de 4min no Mac M2 Pro
```

### 3. Fluxo CVAT (rotulação híbrida)

Ver `tooling/cvat_workflow/README.md`. Resumo:
1. Instalar CVAT local via Docker
2. Rodar `generate_preannotations.py` para gerar `.txt` YOLO
3. Criar Task no CVAT, importar pré-anotações
4. Anotar manualmente o que faltou
5. Export → usar `consume_cvat_export.py` para gerar laudo VALBOT ou dataset YOLO

### 4. Gerar laudo PDF

```python
from src.reporting import build_context, render_pdf

ctx = build_context(
    infracoes_detectadas=[
        {"id": "789_elim_03", "timestamp_inicio": 45.3, "duracao_s": 12.1,
         "evidencia": "Cinto não visível no quadrante interno"},
    ],
    candidato={"nome": "João Teste", "cpf": "000.000.000-00",
               "renach": "X123", "categoria": "B"},
    metadata={"laudo_id": "LAU-001", "rubrica": "789_2020",
              "modelo_versao": "qwen2.5-vl-7b", "duracao_seg": 240},
)
render_pdf(ctx, "/tmp/laudo.pdf")
```

Template em `src/reporting/templates/laudo.html`. Saída: PDF A4 com status APTO/INAPTO, tabela de infrações, linha do tempo, matriz de cobertura calculada a partir do `CATALOGO` em `src/rubrics/taxonomia.py`.

### 5. Rodar frontend

```bash
cd frontend
pnpm install
pnpm --filter @workspace/valbot dev    # http://localhost:5173
```

O app espera uma API FastAPI em `http://localhost:8000`. Enquanto o backend novo não existe, as telas renderizam mas as chamadas fetch falham. Ver `frontend/README.md`.

### 6. Usar prompts VLM (com Claude API)

```python
import os
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."

from src.prompts.tier1 import get_prompt
from src.analysis.vlm_engine import ClaudeBackend, HybridVLMEngine

prompt = get_prompt("cinto")
backend = ClaudeBackend()
engine = HybridVLMEngine(cloud_backend=backend)

# para cada frame relevante:
result_raw = backend.analyze(
    frame_bgr,
    prompt.user_prompt_template.format(timestamp_s=45.3),
    prompt.system_prompt,
)
```

---

## Decisões técnicas importantes

### Layout das câmeras (VIP Intelbras, validado com 4 vídeos reais)

| Quadrante | Câmera | Uso |
|---|---|---|
| TL | Frontal | Sinalização horizontal/vertical, semáforos |
| TR | Lateral direita | Ultrapassagens, meio-fio direito |
| BL | Interna | Cinto, mãos no volante, olhar retrovisor |
| BR | Traseira-esq baixa | Subida meio-fio esquerdo, baliza |

### Modelo VLM recomendado

Com resolução efetiva de 640×360 por câmera (após fatiar o grid 1280×720):
- **Produção cloud:** Claude Sonnet 4 (R$ 1,75-17 por vídeo)
- **Produção local:** Qwen2.5-VL 7B (não 3B — 3B tropeça em 640×360)
- **Custo-benefício:** event-windowing reduz calls em 7-10x

### Limitações conhecidas

- **Resolução:** 640×360 perde placas verticais a >30m
- **Áudio:** clipping detectado nos vídeos requer `whisper-large-v3` + pré-processamento
- **Layout:** 2 dos 4 vídeos têm timestamps zerados (01-01-2000) — usar RTC no DVR real
- **Cobertura:** 70-75% dos itens v1 detectáveis (ideal era 79%)

### Provedores LLM (Gemini)

A chave AI Studio (`GOOGLE_API_KEY`) usada hoje em `vlm_engine.py` está em projeto sem billing — só funciona para Flash. Para `gemini-2.5-pro` e `gemini-3.1-pro-preview` o caminho é **Vertex AI** com os créditos GCP do projeto `project-308f1fa8-a301-49e6-a69` (R$ 1.703 Free Trial até 24/jul/2026). Setup completo, IDs de modelos validados e templates de chamada em [`docs/gemini_vertex_setup.md`](docs/gemini_vertex_setup.md). `gemini-3-pro-preview` foi descontinuado pelo Google em 26/mar/2026 — usar 3.1.

---

## Próximos passos

1. Calibrar falso positivo do `CrosswalkDetector` no pátio do Detran
2. Rotular 10-20 vídeos no CVAT para ground truth
3. Medir precision/recall real dos prompts Tier 1
4. Escalar para Qwen local no Runpod ou MLX no Mac
5. Implementar relatório PDF WeasyPrint
6. Adicionar transcrição áudio (buzina, comentários examinador)

---

## Referências

- Res. CONTRAN 789/2020 — regulamenta provas práticas
- Res. CONTRAN 1.020/2025 — nova rubrica
- Anexo II do CTB — placas de sinalização
- MBST Vol. IV — sinalização horizontal

Documentos oficiais em `configs/references/`.
