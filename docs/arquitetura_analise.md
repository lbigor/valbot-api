# Arquitetura da análise — VALBOT

Especificação técnica do pipeline de análise de um vídeo de prova prática. Cobre o contrato de cada camada (input, processo, output), o que efetivamente chega no VLM, as regras aplicadas (rubrica), e as garantias de determinismo e rastreabilidade.

Versão: 2026-04-24 (draft para revisão humana antes da implementação fim-a-fim).
Base de código: `src/` do projeto VALBOT + herança de `valbot_old/v2/backend/app/workers/` (pipeline v2 do LaudoAI, que está produzindo 6 PDFs reais por dia).

---

## 1. Objetivo

Dado **um vídeo MP4** de exame de direção capturado por DVR VIP Intelbras em grid 2×2 (1280×720, 4 quadrantes de 640×360), produzir:

- Um **laudo determinístico** em JSON + PDF indicando `APTO` ou `INAPTO`, as infrações cometidas, suas evidências visuais e sua fundamentação legal (Res. CONTRAN 789/2020 ou 1.020/2025).
- Um **conjunto de artefatos auditáveis** (frames enviados ao VLM, prompts literais, respostas cruas, cache de inferência) que permitam reconstruir a decisão passo a passo e contestá-la.

Não faz parte do objetivo: substituir o examinador humano. O laudo é **assistência**, não veredito final.

---

## 2. Princípios invioláveis

| # | Princípio | Consequência no código |
|---|---|---|
| P1 | **Determinismo** | `temperature=0`, seed fixo, cache SHA-256 de `(frame + prompt + modelo)`. Rodar duas vezes → resultado idêntico. |
| P2 | **Rastreabilidade** | Toda decisão do VLM persiste: frame enviado (JPEG), prompt literal, resposta crua, model_name, timestamp. |
| P3 | **Event-windowing** | VLM só é acionado sobre **janelas temporais abertas por detector determinístico** — reduz custo em 7-10× e evita alucinação ambiente. |
| P4 | **Isolamento por câmera** | Cada prompt vê **apenas uma** das 4 câmeras (640×360). Nunca o grid 2×2 inteiro. Evita distração entre quadrantes. |
| P5 | **Saída estrita** | Todo prompt VLM tem JSON schema com 4 campos. Resposta que não parseia marca `needs_review=True`, não entra no laudo automaticamente. |
| P6 | **Cross-check obrigatório** | Detecção positiva só vira infração depois de confirmada por segunda fonte (outro frame, outra câmera, detector OpenCV). |
| P7 | **Ground truth do dataset vence** | Nos 4 vídeos atuais, todos estão com cinto. Qualquer positivo de cinto é falso positivo por construção. Pipeline precisa conseguir ser auditado contra esse fato. |

---

## 3. Visão macro — 10 camadas

```
┌──────────────────┐  MP4 1280×720 (grid 2×2 VIP Intelbras)
│ 1. INGESTÃO      │  → GridFrame × N (4 câmeras sincronizadas por timestamp)
├──────────────────┤
│ 2. PREPROCESS    │  → GridFrame × N (estabilizado, exposição normalizada)
├──────────────────┤
│ 3. KEYFRAMES     │  → Keyframe × K (K ≈ 20-40 em vídeo de 4min)
├──────────────────┤
│ 4. DETECTORES    │  → DetectionCandidate × D (PARE, crosswalk, semáforo,
│    DETERMINIST.  │                           parada do veículo)
├──────────────────┤
│ 5. DETECTORES    │  → {pose, depth, ocr, tracks} por frame relevante
│    MODELO        │
├──────────────────┤
│ 6. VLM           │  → FrameAnalysis × F (respostas JSON do VLM sobre eventos)
├──────────────────┤
│ 7. ÁUDIO         │  → AudioEvent × A (buzina, voz do examinador)
├──────────────────┤
│ 8. CROSS-CHECK   │  → ConfirmedInfraction × I (I ≤ F; purga alucinação)
├──────────────────┤
│ 9. SCORING       │  → LaudoCore (contagem, pontuação, aprovado, motivo)
├──────────────────┤
│ 10. LAUDO        │  → result.json + laudo.pdf + evidências em disco
└──────────────────┘
```

Cada camada é **pura** (mesmo input → mesmo output) exceto a 6 (VLM), que é determinística condicional ao modelo+temp=0+seed.

Vídeo de referência: 4 min @ 30 fps = 7.200 frames. Com `sample_fps=5`, varre 1.200 frames na camada 3. Dali saem ~30 keyframes e ~8-15 janelas de evento. O VLM é chamado em ~25-40 calls no total (não 1.200).

---

## 4. Camada 1 — Ingestão

**Código**: `src/ingestion/grid_slicer.py`

**Input**
| Campo | Tipo | Descrição |
|---|---|---|
| `video_path` | `Path` | Caminho absoluto do MP4 |
| `layout` | `dict[str,str]` | `{"TL":"frontal","TR":"lateral_direita","BL":"interna","BR":"traseira_esq"}` (VIP Intelbras) |
| `sample_fps` | `float` | Taxa de amostragem (default 1.0 hoje; pipeline novo vai usar 5.0) |

**Processo**
1. Abre vídeo com `cv2.VideoCapture`, lê `fps`, `width`, `height`, `total_frames`, `duration_s`.
2. Rejeita se dimensões não são lidas (vídeo corrompido).
3. Itera com passo `step = fps / sample_fps`, fatia cada frame em 4 quadrantes pela metade em cada eixo (`half_w`, `half_h`), mapeia quadrante → câmera pelo `layout`.
4. Emite `GridFrame` (4 câmeras sincronizadas no mesmo timestamp).

**Output**
```python
@dataclass
class GridFrame:
    timestamp_s: float           # tempo desde início do vídeo
    frame_idx: int               # índice absoluto no vídeo original
    frontal:         np.ndarray  # (360, 640, 3), BGR uint8 — TL
    lateral_direita: np.ndarray  # (360, 640, 3), BGR uint8 — TR
    interna:         np.ndarray  # (360, 640, 3), BGR uint8 — BL
    traseira_esq:    np.ndarray  # (360, 640, 3), BGR uint8 — BR
```

**Metadata também persistida** (`GridSlicer.metadata()`): path, fps, dimensões, total_frames, duration_s, layout, sample_fps. Vai pro `summary` do laudo.

**Falhas conhecidas**
- DVR que grava timestamp zerado (01-01-2000): 2 dos 4 vídeos. Não afeta análise, mas impossibilita correlação com hora real do exame.
- Layout não-VIP (outro DVR): `layout=` precisa ser passado manualmente.

---

## 5. Camada 2 — Preprocess

**Status**: **não implementado no Valbot novo**. Herdar de `valbot_old/v2/backend/app/workers/preprocess.py` (406 linhas).

**Responsabilidades esperadas**
- Estabilização de cada quadrante (compensa trepidação do veículo).
- Normalização de exposição (4 câmeras com ganhos diferentes → equaliza histograma).
- Correção de timestamp quando RTC do DVR está zerado.
- Detecção de frames corrompidos (full-black, full-white, artefatos de compressão).

**Input**: `Iterable[GridFrame]` da camada 1.
**Output**: `Iterable[GridFrame]` com mesmas dimensões, `image` processada.

**Por que é crítico**: cinto em câmera `interna` com exposição ruim é o cenário clássico de falso positivo — condutor aparece com o peito "lavado" e o VLM não vê a faixa diagonal.

---

## 6. Camada 3 — Keyframe Detection

**Código**: `src/ingestion/keyframe_detector.py`

**Input**: `list[GridFrame]` da camada 2.

**Processo** — roda **por câmera** (4 passes independentes):
1. Calcula histograma de cada frame (`cv2.calcHist`).
2. Compara com frame anterior (`cv2.compareHist`, correlação). Abaixo de `scene_threshold=0.35` → marca `SCENE_CHANGE`.
3. Calcula optical flow Farneback reduzido (160×90). Magnitude > `motion_threshold=2.5` → marca `HIGH_MOTION`.
4. Luminância delta > 60 → marca `LIGHTING_ANOMALY`.
5. Amostragem obrigatória a cada `scheduled_every_s=3.0` segundos (`SCHEDULED`) — garante que cenas estáticas não sumam do laudo.
6. Dedup: intervalo mínimo `min_interval_s=2.0` entre keyframes consecutivos.

**Output**
```python
@dataclass
class Keyframe:
    timestamp_s: float
    frame_idx: int
    score: float                 # 0..1, razão do maior trigger
    reasons: list[KeyframeReason]  # {SCENE_CHANGE, HIGH_MOTION, AUDIO_PEAK, LIGHTING_ANOMALY, SCHEDULED}
    camera_hint: str | None      # qual câmera disparou score máximo
```

**Volume esperado**: vídeo de 4min → 20-40 keyframes. Isso é o conjunto que **pode** ir pro VLM — mas ainda filtrado pela camada 4.

---

## 7. Camada 4 — Detectores determinísticos

**Código**: `src/detectors/*.py` + `src/detectors/orchestrator.py`

Cada detector é classe que herda `BaseDetector` e implementa `detect(frame, frame_idx, timestamp_s) -> DetectionCandidate`.

**Detectores existentes**

| Detector | Arquivo | O que vê | Câmera | Confiança |
|---|---|---|---|---|
| `TrafficLightDetector` | `traffic_light.py` | Círculos HSV vermelho/amarelo/verde via HoughCircles | frontal (TL) | 0.4-0.9 |
| `RoadTextDetector` | `road_text.py` | Letras brancas grandes no asfalto (PARE, 40, etc.) | frontal (TL) | 0.3-0.8 |
| `CrosswalkDetector` | `crosswalk.py` | Faixas brancas paralelas perpendiculares à direção | TL ou BR | 0.4-0.7 |
| `StopDetector` | `stop_detector.py` | Optical flow denso < limiar por ≥ 1s (veículo parado) | qualquer | 0.5-0.95 |

**Input**: `Iterable[GridFrame]` da camada 3 (ou direto da 2, ignorando keyframes).

**Processo — `EventOrchestrator.sweep(video)`**
1. Sweep rápido (5 fps) em todos os frames chamando os 4 detectores.
2. Para cada `DetectionCandidate.should_trigger_vlm` (detected=True && confidence ≥ 0.45):
3. Abre **EventWindow** segundo tabela:

```python
WINDOW_CONFIG = {
    PARE_SIGN:     {"before_s": 5.0, "after_s": 3.0, "prompts": ["pare_chao", "linha_retencao"]},
    CROSSWALK:     {"before_s": 3.0, "after_s": 4.0, "prompts": ["faixa_pedestre"]},
    TRAFFIC_LIGHT: {"before_s": 3.0, "after_s": 2.0, "prompts": ["semaforo_vermelho"]},
}
```
4. Cruza com `StopDetector` dentro da janela: houve parada efetiva? (crítico pra PARE e semáforo).
5. Cross-camera: crosswalk detectado em TL deve se repetir em BR com lag de ~3s (veículo passou por cima). Marca `cross_camera_confirmation=True` só quando casa.

**Output**
```python
@dataclass
class EventWindow:
    event_type: EventType           # PARE_SIGN | CROSSWALK | TRAFFIC_LIGHT | STOP_LINE | CURB | VEHICLE_STOPPED
    trigger_timestamp_s: float
    trigger_confidence: float
    camera: str                     # câmera que disparou
    window_start_s: float
    window_end_s: float
    prompts_to_run: list[str]       # quais prompts Tier 1 rodar dentro da janela
    stop_event: StopEvent | None
    cross_camera_confirmation: bool
    metadata: dict
```

**Volume esperado**: vídeo de 4min → 3-8 EventWindows. É o gatilho real do VLM (não os 20-40 keyframes).

**Detectores que faltam** (roadmap): `PareSignTextDetector` (específico pra detectar a palavra "PARE" no asfalto), detector de meio-fio lateral, detector de placa de PARE vertical.

---

## 8. Camada 5 — Detectores com modelo (pose, depth, ocr, tracking)

**Status**: **não implementado no Valbot novo**. Código fonte em `valbot_old/v2/backend/app/workers/{pose,depth,ocr,yolo_track}.py` (total ~700 linhas).

**Função** (por módulo)

| Módulo | Modelo | Input | Output | Impacto no laudo |
|---|---|---|---|---|
| `pose.py` | OpenPose/RTMPose | frames câmera **interna** | keypoints do torso do condutor | Cinto, mãos no volante, olhar retrovisor |
| `depth.py` | Depth Anything v2 | frame câmera **frontal** | mapa de profundidade | Distância até placa vertical (ataca limitação "placa >30m") |
| `ocr.py` | PaddleOCR ou Tesseract | recortes de RoadTextDetector e placas detectadas | texto reconhecido | Confirma que "PARE" é literalmente PARE e não borrão |
| `yolo_track.py` | YOLOv8 + BoT-SORT | frames câmeras externas | tracks de pedestres, carros, sinais | Falta sinalização semafórica, ultrapassagem perigosa |

**Por que isso importa pro cinto**: `pose.py` detecta o torso do condutor em coordenadas 2D. Se não conseguiu achar o torso com confiança ≥ 0.6, **não enviar pro VLM analisar cinto** — evita que o VLM invente "não vejo cinto" por oclusão. É gate pré-VLM.

---

## 9. Camada 6 — VLM (o coração)

**Código**: `src/analysis/vlm_engine.py` + `src/prompts/tier1.py` + `src/prompts/base.py`

Essa é a camada que o usuário explicitamente pediu para detalhar.

### 9.1 Entrada do VLM — frame por frame

Para cada `EventWindow` da camada 4, o orquestrador executa:

```python
for prompt_name in event_window.prompts_to_run:
    prompt_def = PROMPTS[prompt_name]        # PromptInfracao
    frames = _select_frames(
        grid_frames,
        camera=prompt_def.camera,            # só a câmera indicada pelo prompt!
        center_ts=event_window.trigger_timestamp_s,
        n_frames=prompt_def.frames_needed,   # 1, 3 ou 5
        spacing_s=prompt_def.frames_spacing_s # 0.0, 0.3, 0.5
    )
    for frame in frames:
        raw = backend.analyze(
            image_bgr=frame.image,           # np.ndarray (360, 640, 3) BGR
            user_prompt=prompt_def.user_prompt_template.format(
                timestamp_s=frame.timestamp_s,
                ...
            ),
            system_prompt=prompt_def.system_prompt,
        )
        result = engine._parse(raw, camera, ts, frame_idx, model_name, prompt_def.infracao_id)
```

**O que é enviado concretamente em UMA call** (backend Claude ou Qwen):

| Item | Valor |
|---|---|
| Imagem | **UM** JPEG 640×360 (qualidade 85), a câmera exata que o prompt pede — nunca o grid 2×2 |
| System prompt | Texto literal da `PromptInfracao.system_prompt` — específico da infração |
| User prompt | Template renderizado com o timestamp do frame |
| Temperature | `0.0` |
| Model | `claude-sonnet-4-5` (cloud) ou `qwen2.5-vl-{7B\|3B}` (local) |
| Max tokens | 1500 |

**NÃO é enviado**: histórico de conversação, outros frames do vídeo, resultado de outros prompts, áudio, resultado de detectores OpenCV. Cada call é **stateless** e isolada — se ela alucina, só contamina 1 infração em 1 frame.

### 9.2 Prompts Tier 1 — catálogo

Todos em `src/prompts/tier1.py`. Por infração:

| Infração | ID | Câmera | Frames | Espaçamento | Assertividade esperada |
|---|---|---|---|---|---|
| Cinto de segurança | `789_elim_03` | `INTERNA` (BL) | 1 | 0s | 95% |
| Avançar sobre meio-fio | `789_elim_02` | `TRASEIRA_ESQ` (BR) | 3 | 0.3s | 90% |
| Linha de retenção | `789_elim_01` (compartilhado) | `FRONTAL` (TL) | 5 | 0.5s | 90% |
| Semáforo vermelho | `789_elim_01` | `FRONTAL` (TL) | 3 | 0.5s | 88% |
| PARE no chão | `789_elim_01` | `FRONTAL` (TL) | 3 | 0.5s | 85% |
| Ultrapassagem / mudança de faixa | `789_grave_05` | `LATERAL_DIREITA` + `INTERNA` | 3 | 1.0s | 85% |
| Faixa de pedestres | *a criar* | `FRONTAL` + `TRASEIRA_ESQ` | 2+2 | 0.5s | — |

Regra: nenhum prompt Tier 1 entra em produção sem atingir a assertividade esperada em teste de regressão (ver seção 14). O prompt **CINTO** tem ajuste específico para layout VIP Intelbras: condutor à DIREITA, examinador à ESQUERDA. Documentado em `tier1.py:22-52`.

### 9.3 Saída do VLM — schema

**Todo prompt** deve responder **apenas** JSON neste schema (`BASE_SCHEMA` em `src/prompts/base.py:35-44`):

```json
{
  "detected": true | false | null,
  "confidence": 0.0,
  "evidence": "1-2 frases descrevendo o que foi observado (≤500 chars)",
  "timestamp_relative_s": null
}
```

| Campo | Tipo | Significado |
|---|---|---|
| `detected` | `bool \| null` | `true` = infração cometida; `false` = não cometida; `null` = impossível avaliar (oclusão, baixa visibilidade) |
| `confidence` | `float [0,1]` | Confiança do modelo na decisão |
| `evidence` | `str` | Texto curto, factual, descrevendo o que foi visto. Vai **direto pro laudo PDF** como evidência |
| `timestamp_relative_s` | `float \| null` | Dentro da sequência enviada, em qual frame o evento ocorre (pra prompts multi-frame) |

### 9.4 Parse defensivo

`HybridVLMEngine._parse` (`vlm_engine.py:139-161`):
1. Remove markdown fencing (`\`\`\`json`, `\`\`\``).
2. Tenta `json.loads`.
3. Se falhar → `FrameAnalysis(..., needs_review=True, raw_model_output=raw)`. **Não entra no laudo**. Cai pra revisão humana.
4. Se passar → valida tipos mínimos (`bool`, `float`, `str`). Erro → `needs_review=True`.

### 9.5 Determinismo e cache

`_cache_key(frame, prompt, model)` = SHA-256 truncado de `(JPEG(q=70) + prompt + model)`:
- Diretório: `.vlm_cache/{model}_{frame_hash}_{prompt_hash}.json`.
- Hit: devolve resposta cacheada sem chamar API.
- Miss: chama API, salva.

Consequência: **repetir análise custa R$ 0,00** se o vídeo não mudou. Também facilita o modo debug — se você abrir o arquivo de cache, vê exatamente o que o VLM respondeu.

### 9.6 Trilha híbrida local + cloud (opcional)

Design de `HybridVLMEngine` (`vlm_engine.py:115-127`):
1. Qwen2.5-VL local (7B ou 3B-4bit) analisa TODOS os frames das EventWindows (barato, ~100 ms/frame em Mac M2).
2. Se `confidence < escalation_threshold=0.7` → escala pro Claude API (cloud).
3. Merge: Claude ganha prioridade quando presente.

Decisão pra começar: **só Claude** (mais simples, mais rápido de validar, ~R$ 2-17 por vídeo). Qwen entra em fase 2 para cortar custo.

### 9.7 Saída final da camada 6

```python
@dataclass
class FrameAnalysis:
    timestamp_s: float
    frame_idx: int
    camera: str
    detections: list[DetectionResult]  # 1 item por prompt rodado
    needs_review: bool
    raw_model_output: str              # sempre preservado pra auditoria

@dataclass
class DetectionResult:
    infracao_id: str
    camera: str
    timestamp_s: float
    frame_idx: int
    detected: bool
    confidence: float
    evidence: str
    model_name: str
```

Todas as `FrameAnalysis` são persistidas em `storage/analyses/<video_hash>/vlm_raw.json` — input cru pra camada 8.

---

## 10. Camada 7 — Áudio

**Status**: **não implementado no Valbot novo**. Herdar de `valbot_old/v2/backend/app/workers/{audio,whisper_ct2}.py`.

**Input**: arquivo MP4 → extrai faixa de áudio (`ffmpeg -vn -ac 1 -ar 16000`).

**Processo**
1. **VAD** (Silero) → detecta trechos com fala.
2. **Whisper** (large-v3 com faster-whisper) → transcreve com timestamps.
3. **Detector de buzina**: pico de energia em 250-500 Hz acima de limiar, duração 100-800 ms.
4. **Quality flag**: `ok` / `degraded` / `hallucinated` / `no_speech` — já existe no schema (`types/laudo.ts:123`).

**Output**
```json
{
  "transcript": [{"ts": 12.3, "end": 14.8, "text": "atenção com o semáforo"}],
  "horns": [{"ts": 45.2, "duration_ms": 320, "energy_db": -12}],
  "quality": "ok"
}
```

**Uso no laudo**
- `789_grave_01` (buzina sem necessidade) depende disso.
- Voz do examinador pode indicar momentos críticos ("pare aqui", "cinto") — entra como `pontos_atencao` no laudo.

---

## 11. Camada 8 — Cross-check (anti-alucinação)

**Status**: **não implementado**. Esta é a camada que protege contra falso positivo — a mais importante depois do VLM.

**Input**: `FrameAnalysis[]` da camada 6 + `EventWindow[]` da camada 4 + `AudioEvent[]` da camada 7 + outputs da 5.

**Regras por infração** (a consolidar — proposta inicial):

| Infração | Detecção positiva só vale se... |
|---|---|
| Cinto (`789_elim_03`) | 1. `pose.py` achou torso com conf ≥ 0.6 **E** 2. VLM detectou sem cinto em ≥ 60% dos frames amostrados na janela **E** 3. Frames cobrem ≥ 15s do percurso **E** 4. Nenhum frame adjacente mostrou cinto visível (não é oclusão temporária) |
| Semáforo vermelho (`789_elim_01`) | 1. `TrafficLightDetector` marcou vermelho **E** 2. `StopDetector` confirma que **não** houve parada no intervalo **E** 3. VLM confirma que a faixa de retenção foi cruzada |
| Meio-fio (`789_elim_02`) | 1. VLM marca em ≥ 2 frames consecutivos **E** 2. `depth.py` indica variação de altura da roda esquerda |
| PARE no chão | 1. `RoadTextDetector` disparou **E** 2. OCR confirma "PARE" literal **E** 3. `StopDetector` indica que **não** parou na janela |

Infração que não passa em todas as regras → rebaixada pra `needs_review`, **não entra** em `scored.infracoes` automaticamente.

**Output**: `ConfirmedInfraction[]` — subset de `FrameAnalysis[]` com veredito humano-auditável.

**Por que essa camada existe**: foi aqui que os 6 PDFs do valbot_old conseguiram manter 0 falsos positivos de cinto. Sem ela, 1 frame com o braço do condutor na frente do peito vira `INAPTO eliminatória` — reprova candidato correto.

---

## 12. Camada 9 — Scoring (aplicação da rubrica)

**Código**: `src/rubrics/taxonomia.py` + `src/reporting/adapter.py` (já implementado).

**Input**: `ConfirmedInfraction[]` da camada 8 + `Rubrica` escolhida + `limite_pontuacao`.

**Processo** (ver `adapter.build_context`):
1. Para cada confirmed, busca `Infracao` no `CATALOGO` pelo `id`.
2. Conta por severidade: `{eliminatoria, gravissima, grave, media, leve}`.
3. Soma pontos: `sum(pontos por severidade conforme PONTOS[rubrica])`.
4. `aprovado = not tem_eliminatoria and pontuacao_total <= limite_pontuacao`.

**Tabela de pontos** (`taxonomia.py:31-44`)

| Severidade | Res. 789/2020 | Res. 1.020/2025 |
|---|---|---|
| ELIMINATORIA | `None` (reprovação automática) | — |
| GRAVISSIMA | — | 6 pts |
| GRAVE | 3 pts | 4 pts |
| MEDIA | 2 pts | 2 pts |
| LEVE | 1 pt | 1 pt |

**Limite default**: 3 pts para Res. 789/2020. Configurável via `metadata.limite_pontuacao`.

**Output**: `LaudoContext` (ver `src/reporting/schema.py`) — dict pronto pra ir pro template.

---

## 13. Camada 10 — Laudo (PDF + JSON)

**Código**: `src/reporting/pdf.py` + `src/reporting/templates/laudo.html` (implementado hoje).

**Input**: `LaudoContext` da camada 9.

**Processo**
1. `render_pdf(ctx, out_pdf)` — Jinja2 renderiza `laudo.html` com o contexto.
2. WeasyPrint converte HTML → PDF A4 print-optimized.
3. Salva `.pdf` + `.html` (debug) em `storage/pdfs/LAU-{video_hash[:8].upper()}.pdf`.
4. Persiste `result.json` canônico em `storage/analyses/<hash>/result.json`.

**Artefatos finais por análise** (diretório `storage/analyses/<video_hash>/`)

```
result.json                # LaudoContext completo (fonte da verdade)
vlm_raw.json               # FrameAnalysis[] — todas as respostas cruas do VLM
transcript.json            # saída camada 7 (áudio)
v2_pipeline.json           # metadata do pipeline (versões, elapsed)
training_annotations.json  # feedback humano (skill avaliador-detran)
frames/<ts>_<cam>.jpg      # JPEGs enviados ao VLM
clips/<infracao>.mp4       # clipes ±5s por infração
evidence_boards/<inf>.png  # mosaicos de frames por infração
pose/<ts>.json             # keypoints do condutor
depth/<ts>.png             # mapas de profundidade
ocr/<ts>.json              # reconhecimento de texto
tracks/<ts>.json           # bounding boxes + IDs YOLO
```

Essa estrutura é herdada do valbot_old e é o que viabiliza o **modo debug**: clicar numa infração no frontend → ler o JSON → mostrar o frame + prompt + resposta lado a lado.

---

## 14. Regras do catálogo

Fonte única: `src/rubrics/taxonomia.py:64-182`. Hoje 10 infrações.

| ID | Rubrica | Severidade | Descrição | Câmeras | Detectável v1 |
|---|---|---|---|---|---|
| `789_elim_01` | 789/2020 | ELIMINATORIA | Desobedecer sinalização semafórica/parada | frontal, traseira_esq | ✅ |
| `789_elim_02` | 789/2020 | ELIMINATORIA | Avançar sobre meio-fio | traseira_esq, lateral_direita | ✅ |
| `789_elim_03` | 789/2020 | ELIMINATORIA | Não colocar cinto | interna | ✅ |
| `789_grave_01` | 789/2020 | GRAVE | Buzina sem necessidade | áudio | ✅ |
| `789_grave_05` | 789/2020 | GRAVE | Regras de ultrapassagem/faixa | lateral_direita, interna, frontal | ✅ |
| `789_media_02` | 789/2020 | MEDIA | Veículo desregulado | áudio, interna | ✅ |
| `789_leve_01` | 789/2020 | LEVE | Movimentos irregulares | interna, traseira_esq | ✅ |
| `789_leve_04` | 789/2020 | LEVE | Pé na embreagem engrenado | — | ❌ (requer OBD) |
| `1020_gravissima_01` | 1020/2025 | GRAVISSIMA | Não utilizar cinto | interna | ✅ |
| `1020_grave_03` | 1020/2025 | GRAVE | Descumprir sinalização horizontal de parada | frontal | ✅ |

**Cobertura efetiva v1**: 9/10 = 90% (só `789_leve_04` precisa OBD).

Cada infração carrega `checklist_visual` — perguntas curtas que são usadas **como guia** do `system_prompt` do VLM. Exemplo (`789_elim_03`):
- "O cinto está visível cruzando o peito do candidato?"
- "O cinto permaneceu afivelado durante todo o percurso?"

---

## 15. Ground truth e regressão

Dataset atual: 4 vídeos fixos (`storage/videos/{1,2,3,4}.mp4`, 634 MB total).

**Ground truth conhecido** (fornecido pelo usuário 2026-04-24):
- **Cinto**: em **todos** os 4 vídeos, todos os candidatos usam cinto. `detected=True` para cinto em qualquer um desses vídeos = falso positivo automático.
- Outras infrações: *a catalogar em planilha de revisão humana*.

**Conjunto de regressão proposto**
1. Rodar o pipeline completo nos 4 vídeos.
2. Comparar output com ground truth.
3. Bloquear merge de qualquer alteração de prompt que regrida o ground truth (ex.: pipeline começa a marcar cinto).

---

## 16. Contra-falsificação — como contestar uma decisão

Para qualquer infração no laudo, o revisor consegue reconstruir a decisão:

1. **Abrir** `storage/analyses/<hash>/result.json` → achar a infração pelo `infracao_id` e `timestamp_inicio`.
2. **Consultar** `vlm_raw.json` no mesmo timestamp → ver resposta crua do VLM.
3. **Abrir** `frames/<ts>_<cam>.jpg` → ver exatamente o frame que o VLM analisou.
4. **Ler** `src/prompts/tier1.py` na definição do `infracao_id` → ver o prompt literal.
5. **Conferir** `.vlm_cache/<hash>.json` → cache de inferência (prova de determinismo).
6. **Comparar** com `ConfirmedInfraction` → ver por que passou (ou não) no cross-check da camada 8.

Esse fluxo é o que o **modo debug** no frontend vai expor: clicar na infração na tela `AnaliseExame` → painel lateral com frame + prompt + resposta + botão "refuto".

---

## 17. O que falta implementar (gap-list acionável)

Ordem de prioridade para destravar análise dos 4 vídeos:

1. **Instalar deps de processamento**: `opencv-python`, `numpy`, `httpx`, `anthropic` (cloud-only pra começar). 5 minutos.
2. **Completar `src/analyzer.py`**: substituir linha 46 (`"Aqui entraria o chamado ao VLM"`) por chamada real ao `EventOrchestrator` → `HybridVLMEngine(ClaudeBackend)` → `render_pdf`.
3. **Implementar camada 8 (cross-check)** — específico começando pelo cinto (a regra de ≥60% dos frames + ≥15s). Sem isso, não dá pra confiar em eliminatórias.
4. **Portar `pose.py`** de `valbot_old/v2/backend/app/workers/` — necessário pro gate do cinto.
5. **Portar `preprocess.py`** — estabilização.
6. **Watermark DEMO no template** quando `ctx["demo"]=True` — evita repetir o erro do PDF de teste sair parecendo oficial.
7. **Portar áudio** (`workers/audio.py` + `whisper_ct2.py`) — só depois do caminho visual fechado.
8. **Portar `depth`, `ocr`, `yolo_track`** — incremento de precisão, não bloqueante.

---

## 18. Resumo do que entra e sai do VLM (resposta curta)

Uma call típica:
- **Entra**: 1 imagem JPEG 640×360 (uma câmera) + system prompt literal (específico da infração) + user prompt com timestamp. Sem histórico, sem grid, sem áudio.
- **Sai**: JSON com `{detected, confidence, evidence, timestamp_relative_s}`.
- **Custo**: ~R$ 0,05-0,15 por call (Claude Sonnet 4.5). ~25-40 calls por vídeo → ~R$ 2-6.
- **Cache**: SHA-256 do par (frame, prompt) → rodar de novo custa R$ 0.
- **Onde persiste**: frame em `frames/`, resposta em `vlm_raw.json`, cache em `.vlm_cache/`.

Nenhuma call do VLM pode gerar uma infração sozinha — sempre passa por cross-check (camada 8) antes de entrar no laudo.
