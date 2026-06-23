# Estratégia de avaliação — sinalização → infração CONTRAN

**Objetivo:** transformar a biblioteca `sinalizacao/` + todas as anotações já existentes no projeto em sinal acionável dentro do pipeline LaudoAI: VLM consome crops como referência few-shot, decisões humanas como calibragem, detecções CV clássicas como triagem, e devolve decisão estruturada que vira evento no laudo.

**Dataset consolidado:** [`DATASET_MASTER.md`](DATASET_MASTER.md) — 760 amostras em 6 categorias, indexadas em `storage/training/dataset_master/INDEX.json` por `tooling/build_dataset_master.py`. Inclui:
- 13 few-shot crops da `sinalizacao/`
- 77 decisões humanas (`storage/training/examples.jsonl`)
- 670 detecções CV clássicas (`storage/analyses/<hash>/cv_detections.json`)
- 133 bboxes de partes internas (`storage/training/annotations_unified/`)
- 9 vereditos de análises completas
- 1 exemplo de saída VLM (`examples/laudo_vid1.json`)
- 2 PDFs CONTRAN/MBST (`configs/references/`)
- Schema de 20+ classes (`tooling/cvat_workflow/valbot_labels.json`)

## 1. Três tipos de imagem por slug

Cada entrada da biblioteca tem **três PNGs com finalidades distintas**:

| Arquivo | Conteúdo | Para quem |
|---|---|---|
| `<slug>_raw.png` | crop da câmera 640×360, sem anotação | auditoria humana, debug |
| `<slug>.png` | mesmo frame com bbox vermelha + label sobreposto | dashboard/laudo, dicionário visual humano |
| `<slug>_crop.png` | **só a sinalização**, padding 8 px, ampliação 4× | **modelo few-shot que vai pra VLM** |

Decisão: `_crop.png` é o que entra na chamada do VLM. Não tem distrações (sem céu, sem candidato, sem dashboard). VLM compara a sinalização sob suspeita com 2-3 crops da mesma categoria.

## 2. Fluxo de avaliação

```
Frame em análise (ts X do laudo)
        │
        ▼
┌──────────────────────────────┐
│ Detector clássico (Tier A)   │ ← src/detectors/{pare_sign,road_text,crosswalk}.py
│  - HSV vermelho octogonal    │   barato, deterministic, sem rede
│  - cluster branco inferior   │
│  - easyocr "PARE"            │
└──────────────────────────────┘
        │  hit (com bbox bruta)
        ▼
┌──────────────────────────────┐
│ Crop do hit (mesma rotina    │
│ tooling.build_sinalizacao_   │
│ library.crop_one)            │
└──────────────────────────────┘
        │  PNG ampliado 4×, padding 8px
        ▼
┌──────────────────────────────┐
│ VLM com few-shot             │  System: "Você é examinador DETRAN."
│  - 2-3 crops da categoria    │  User:
│  - README da categoria       │   {readme da categoria}
│  - crop suspeito             │   "Modelos de referência:" [crop1, crop2, crop3]
│                              │   "Imagem em análise:"   [crop_suspeito]
│                              │   "Devolva JSON: {detected, confidence, evidence}"
└──────────────────────────────┘
        │  resposta JSON
        ▼
DetectionResult → orchestrator → laudo
```

## 3. Inventário detalhado dos crops extraídos

### 3.1 `vertical/pare-r1` — placa R-1 octogonal vermelha

| Slug | Vídeo | TS | Tamanho crop | Ângulo / contexto | Padrão visual extraído |
|---|---|---|---|---|---|
| `12_vid4_t01-19_frontal` | `4.mp4` | 01:19 | 168×168 px (raw bbox 36×36) | placa **distante** (~80m), canto sup-direito do frame, atrás de poste de iluminação, vegetação verde de fundo | octógono vermelho saturado (R-G > 25, R-B > 25) com centro branco visível mesmo em 32px; padrão brasileiro = sempre direita do motorista; câmera frontal vê primeiro |
| `13_vid4_t04-29_frontal` | `4.mp4` | 04:29 | 208×208 px (raw bbox 36×36) | placa **muito distante** (~120m), parcialmente sobreposta pelo overlay de timestamp do gravador, contraste com céu claro | mesma placa do circuito (segunda volta); ensina VLM que placa em 32×32px com fundo de céu requer detector mais permissivo (RGB threshold 20 ao invés de 25) |

**Cenários onde mandar 12 e 13 como few-shot:**
- Detector HSV disparou crop pequeno (<60×60 px) → mandar **12+13** porque ambos são pequenos e o VLM aprende que "placa diminuta + cor vermelha + posição direita" = R-1 mesmo sem ler o texto "PARE".
- Detector pegou objeto vermelho grande (>120 px lado) → mandar 12+13 + perguntar "isto também é R-1 ou é outra coisa vermelha (semáforo, placa publicitária, pano)?". Crops pequenos forçam o VLM a procurar o padrão **forma+cor+posição**, não a palavra.

### 3.2 `horizontal/pare-chao` — inscrição "PARE" no asfalto

| Slug | Vídeo | TS | Tamanho crop | Estado da pintura | Padrão visual |
|---|---|---|---|---|---|
| `07_vid2_t02-05_frontal` | `2.mp4` | 02:05 | 1204×424 px | **NÍTIDO** — letras brancas grandes maiúsculas com perspectiva alongada (efeito legível pelo motorista), linha de retenção branca contínua transversal logo à frente das letras | tipografia: alongada no eixo da via, espessura uniforme; combinação canônica: PARE + linha retenção; contraste alto branco-asfalto |
| `10_vid2_t02-48_frontal` | `2.mp4` | 02:48 | 1724×364 px | **DESBOTADO** — tinta gasta, virou tom alaranjado-marrom, contorno das letras quase fundido com asfalto | mesmo PARE em circuito periférico mal mantido; ensina VLM a aceitar baixa saturação de branco como ainda válido |

**Cenários:**
- Detector easyocr leu "PARE" com confidence > 0.7 → mandar **só 07** (ground truth nítido). VLM confirma rápido.
- easyocr leu mas confidence 0.3-0.7 (texto degradado) → mandar **07+10**. O 10 explicitamente cobre o caso "letras quase apagadas".
- Cluster branco grande sem easyocr (texto não foi lido) → mandar **07+10** + perguntar "é PARE chão ou é outra inscrição (DEVAGAR/ESCOLA/ÔNIBUS)?". Crops mostram tipografia exata do PARE, evita FP em outras inscrições.

### 3.3 `horizontal/faixa-pedestre` — LFO travessia

**Mesma faixa** vista em 3 ângulos consecutivos no `1.mp4` (intervalo de 12s, 00:54 → 01:06):

| Slug | TS | Câmera | Estado da travessia |
|---|---|---|---|
| `01_vid1_t00-54_frontal` | 00:54 | frontal (TL) | veículo se aproximando, faixa zebrada cobre toda a largura da via à frente |
| `02_vid1_t01-06_lateral` | 01:06 | lateral_direita (TR) | veículo passando sobre a faixa, vista em perspectiva diagonal pela lente lateral |
| `03_vid1_t01-06_traseira` | 01:06 | traseira_esq (BR) | faixa fica atrás do veículo, vista em diagonal pela traseira, ocupando quadrante esquerdo do frame |

**Cenário canônico de uso:**
- Detector crosswalk (`src/detectors/crosswalk.py`) dispara em qualquer câmera → mandar **os 3 crops correspondentes ao mesmo ângulo do hit**: se hit na frontal mande 01, se na lateral mande 02, se na traseira mande 03.
- Pra **validar evento composto "veículo cruzou a faixa"** (regra de inferência da filosofia central): mandar 01→02→03 como sequência temporal; VLM confirma que é a mesma faixa vista em 3 fases (aproximação → passagem → afastamento).

### 3.4 `horizontal/seta-esquerda` — LMS direcional

| Slug | TS | Câmera | Geometria observada |
|---|---|---|---|
| `04_vid2_t01-41_frontal` | 01:41 | frontal | seta isolada, ponta apontando esquerda no eixo da via, alongada |
| `06_vid2_t02-03_frontal` | 02:03 | frontal | seta + inscrição "PARE" no mesmo frame (cluster combinado) |
| `05_vid2_t01-45_traseira` | 01:45 | traseira | seta após cruzar, em diagonal no quadrante inferior esquerdo |
| `08_vid2_t02-08_traseira` | 02:08 | traseira | mesma seta da 4, vista pela traseira segundos depois |

**Achado importante 06:** a sinalização brasileira combina seta + PARE no mesmo cluster quando a faixa requer parada antes de virar. VLM precisa ver isso pra não classificar como "duas categorias separadas".

**Cenários:**
- Hit em câmera frontal → mandar **04+06**: 06 cobre o caso composto, 04 cobre seta isolada.
- Hit em câmera traseira → mandar **05+08** + nota explícita "espelhada=true". 4 amostras é pouco; **adicionar mais quando o user fornecer**.

### 3.5 `horizontal/seta-reta` — LMS continuar reto

| Slug | TS | Câmera | Particularidade |
|---|---|---|---|
| `09_vid2_t02-45_frontal` | 02:45 | frontal | sol baixo, contra-luz, seta mantém alto contraste mesmo assim |
| `11_vid2_t03-05_traseira` | 03:05 | traseira | seta sobre **faixa amarela de retenção** (coexistência marca branca + pintura amarela) |

**Cenário:**
- Hit na frontal → **09**.
- Hit na traseira → **11** + nota: "marca branca pode aparecer adjacente a pintura amarela (LRE), não confundir as duas categorias".

## 4. Mapeamento categoria → infração CONTRAN

| Categoria | Crops | Infração CONTRAN 1.020/2025 | Severidade |
|---|---|---|---|
| `vertical/pare-r1` | 12, 13 | Não respeitar placa R-1 (avançar sem parada total) | **Eliminatória** |
| `horizontal/pare-chao` | 07 (nítido), 10 (desbotado) | Não respeitar inscrição PARE no chão | **Eliminatória** |
| `horizontal/faixa-pedestre` | 01, 02, 03 (3 ângulos da mesma faixa) | Avançar faixa com pedestre / não parar antes da linha | **Eliminatória** se houver pedestre |
| `horizontal/seta-esquerda` | 04, 06 (frontais), 05, 08 (traseiras) | Não obedecer regulamentação de movimento (faixa exclusiva) | Grave |
| `horizontal/seta-reta` | 09 (frontal), 11 (traseira) | Idem | Grave |

## 5. Few-shot no VLM — estrutura do prompt enriquecida com TODO o dataset

```python
import json
from pathlib import Path

INDEX = json.loads(Path("storage/training/dataset_master/INDEX.json").read_text())

def avaliar_categoria(crop_suspeito: bytes, categoria: str,
                      hash_video: str = None) -> DetectionResult:
    cat_data = INDEX["categorias_sinalizacao"][categoria]
    cat_dir = LIBRARY / categoria
    readme = (cat_dir / "README.md").read_text()

    # 1) Few-shot visual: 2-3 crops representativos da categoria
    fewshot_crops = cat_data["few_shot_crops"][:3]

    # 2) Few-shot textual: 2 decisões humanas approved + 1 refuted (calibragem)
    decisoes = cat_data["decisoes_humanas"]
    aprovadas = [d for d in decisoes if d["decisao"] == "approved"][:2]
    refutadas = [d for d in decisoes if d["decisao"] == "refuted"][:1]

    # 3) Prior do detector CV: quantos hits da mesma categoria nesse vídeo já foram
    #    aceitos pelo orchestrator? (sinaliza VLM se categoria é comum aqui)
    cv_hits_video = [
        h for h in cat_data["deteccoes_cv_classicas"]
        if hash_video and h["hash"] == hash_video
    ]

    system = (
        "Você é examinador DETRAN classificando sinalização de trânsito "
        "brasileira em vídeos de exame prático. Use Resolução CONTRAN 1.020/2025 "
        "e MBST Vol IV (sinalização horizontal). Schema oficial de classes em "
        "tooling/cvat_workflow/valbot_labels.json."
    )

    user_text = f"""
{readme}

== Modelos visuais (few-shot) — categoria {categoria} ==
{len(fewshot_crops)} crops conhecidos abaixo. Cada um é um exemplo POSITIVO.

== Decisões humanas anteriores (calibragem) ==
APROVADAS:
{chr(10).join(f"  - ts={d['ts']:.1f}s evidência: {d['evidencia']}" for d in aprovadas)}

REFUTADAS (NÃO eram esta categoria, eram FP):
{chr(10).join(f"  - ts={d['ts']:.1f}s motivo: {d['evidencia']}" for d in refutadas)}

== Detector CV clássico ==
{len(cv_hits_video)} hits da mesma categoria neste vídeo (hash {hash_video[:8] if hash_video else '?'}).
Confidence média: {sum(h['confidence'] for h in cv_hits_video)/max(1,len(cv_hits_video)):.2f}

== Imagem em análise ==
[última imagem abaixo]

Tarefa: a imagem em análise contém uma sinalização da categoria {categoria}?
Considere os modelos, as decisões humanas (aprovadas confirmam padrão; refutadas
mostram FPs comuns), e o prior do detector CV.

Devolva APENAS JSON:
{{
  "detected": bool,
  "confidence": 0.0..1.0,
  "evidence": "explicação curta (máx 30 palavras) citando padrão visual",
  "alternativa": "se não for {categoria}, qual outra categoria é mais provável (ou null)",
  "concorda_com_humano": bool   // se sua decisão bate com o que humanos aprovaram em casos similares
}}
"""
    images = [
        *[load_image(c["crop_png"]) for c in fewshot_crops],
        crop_suspeito,
    ]
    return claude.messages.create(
        model="claude-sonnet-4-5",
        system=system,
        messages=[{"role": "user", "content": [
            *[{"type": "image", "source": {...}} for img in images],
            {"type": "text", "text": user_text},
        ]}],
        temperature=0.0,
    )
```

**Por que few-shot enriquecido e não retreino:**
- Crops visuais são poucos (13) — retreino exige ordem de magnitude maior.
- Decisões humanas (77 votos) são heterogêneas em formato textual — caberem como exemplos in-context é direto, retreino exigiria padronizar.
- Detecções CV (670) servem como **prior estatístico** ("placa PARE chão geralmente aparece 2-3× por vídeo neste circuito") — mete no system prompt como contexto, não treina.
- Custo: 1 chamada Claude API ≈ $0.003 vs retreino MLX de $50-200.

## 5. Calibragem de confiança

VLM devolve `confidence` ∈ [0,1]. Política sugerida:

| Confidence | Ação |
|---|---|
| ≥ 0.85 | aceita evento direto, vai pro laudo |
| 0.50–0.85 | marca `needs_review=true`, humano decide |
| < 0.50 | descarta como FP do detector clássico |

Calibrar contra ground truth (`storage/training/examples.jsonl` se houver) e ajustar thresholds por categoria (R-1 pode tolerar threshold mais baixo porque consequência é eliminatória — falso negativo é pior que falso positivo).

## 6. Cache

Hashes (SHA-256 do crop + nome da categoria + versão do prompt) → resultado JSON em `.vlm_cache/`. Reuso dentro de uma rodada de revisão de laudo evita chamadas repetidas. `HybridVLMEngine._cache_key` em `src/analysis/vlm_engine.py` já implementa esse padrão.

## 7. Onde plugar no pipeline existente

1. **`src/analysis/vlm_engine.py`** — adicionar método `analyze_with_fewshot(crop_bytes, category)` que carrega README + amostra 3 crops e monta o prompt da seção 4.
2. **`src/detectors/orchestrator.py`** — quando detector clássico dispara (PareSignDetector, road_text, crosswalk), em vez de aceitar direto, chamar `vlm_engine.analyze_with_fewshot` pra confirmar.
3. **`src/reporting/pdf.py`** — incluir `<slug>.png` (com bbox) no laudo PDF como evidência visual quando o evento sobe pro laudo final.

## 8. Manutenção da biblioteca + dataset

Sempre que humano (você ou /avaliador-detran) discordar de uma decisão do VLM, o feedback alimenta o dataset master:

1. **Decisão humana** vai pra `storage/training/examples.jsonl` (formato canônico: `{hash, infracao_id, ts, decisao: approved|refuted, vote: S|N, evidencia}`). A skill `/avaliador-detran` já faz isso; aproveita.
2. **Se erro = FN (sinalização não reconhecida):** adicionar novo `FrameSpec` em `tooling/build_sinalizacao_library.py`, rodar `--extract --annotate --crop-all`. Isso aumenta o pool de few-shot crops da categoria.
3. **Se erro = FP (sinalização confundida com outra coisa):** adicionar crop **negativo** em pasta `negativos/<categoria>/` com label "NÃO É {categoria} — é {alternativa}". Usado no prompt como contraexemplo.
4. **Re-rodar consolidação:** `tooling/build_dataset_master.py`. INDEX.json atualizado já reflete a nova amostra na próxima chamada do VLM.

Negativos ficam fora do few-shot por padrão mas ativam quando categoria sob suspeita tem alta taxa de FP histórica (ex.: `seta-esquerda` confundida com mancha de sombra).

## 9. Limitações conhecidas

- Crops vêm de 4 vídeos do mesmo gravador (VIP Intelbras 640×360). Se o veículo de exame mudar resolução/lente, recalibrar.
- Setas espelhadas (câmera traseira) têm só 4 amostras — VLM pode confundir com setas direita reais. Ampliar com mais exemplos de outros vídeos.
- Frame 13 (R-1 distante) tem só 32×32px. Distância máxima de detecção confiável ≈ 50m. Acima disso, aceitar `confidence` baixo e esperar o veículo chegar mais perto.
