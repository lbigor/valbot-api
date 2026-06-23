# Dataset Master — todo material de treino consolidado

**Índice unificado:** [`storage/training/dataset_master/INDEX.json`](../storage/training/dataset_master/INDEX.json)

Construído por: `tooling/build_dataset_master.py` (re-rodar quando adicionar amostras).

## Total: 760 amostras em 6 categorias

| Categoria | Few-shot crops | Decisões humanas | Detecções CV | Total |
|---|---:|---:|---:|---:|
| `vertical/pare-r1` | 2 | 72 | 0 | 74 |
| `horizontal/pare-chao` | 2 | 0 | 424 | 426 |
| `horizontal/faixa-pedestre` | 3 | 0 | 246 | 249 |
| `horizontal/seta-esquerda` | 4 | 0 | 0 | 4 |
| `horizontal/seta-reta` | 2 | 0 | 0 | 2 |
| `interno/cinto` | 0 | 5 | 0 | 5 |

## Os 4 tipos de amostra

### 1. Few-shot crops (13 totais) — `sinalizacao/`
Crops ampliados 4× com bbox+label, prontos pra entrar como `image_url` no prompt do VLM.
Cada um tem `_raw.png` + `.png` (anotado) + `_crop.png` (modelo) + `.json` (metadata).

### 2. Decisões humanas (77 votos) — `storage/training/examples.jsonl`
Cada linha: `{hash, infracao_id, ts, decisao: approved|refuted, vote: S|N, evidencia: str}`. Sem bbox, mas é **ground truth de classificação**: o que o examinador humano decidiu vs o que o pipeline detectou. Usa pra:
- Validar precisão do VLM (se VLM aceitar com conf>0.85 mas humano refutou → recalibrar threshold).
- Few-shot textual: incluir 2-3 evidências humanas no prompt como "exemplos de raciocínio aceito".

Distribuição: **72 sobre R1020-G-a (sinal vertical/PARE), 5 sobre R1020-GR-f (cinto)**.

### 3. Detecções CV clássicas (670 hits) — `storage/analyses/<hash>/cv_detections.json`
Bbox + confidence de detectores determinísticos rodados em 9 análises. Por categoria:
- `crosswalk`: 246 hits
- `road_text` (PARE chão): 424 hits
- `stop_sign` (R-1 vertical): 0 (detector ainda não rodou em produção)

Usa como **candidatos pra triagem VLM**: VLM recebe o crop do hit + crops few-shot da categoria → decide se é TP ou FP.

### 4. Partes internas do carro (133 bboxes) — `storage/training/annotations_unified/`
Bboxes manuais em 4 vídeos (vid1-vid4) das partes que importam pra exame:
- VOLANTE, CAMBIO, FREIO_MAO, CHAVE_IGNICAO, PAINEL_RADIO, BAIXO_FRAME, JANELA_LATERAL, etc.

Usa pra **detector composto "carro morre no início"** (Parte 2 do plano): mão sai do volante → mão na chave/câmbio/freio_mao → mão volta volante. Bboxes definem as zonas de cada parte.

## Como o VLM consome o dataset master

```python
import json
from pathlib import Path
INDEX = json.loads(Path("storage/training/dataset_master/INDEX.json").read_text())

# 1) Pegar few-shot da categoria
crops = INDEX["categorias_sinalizacao"]["vertical/pare-r1"]["few_shot_crops"]
# → lista de 2 dicts com crop_png, raw_png, bbox_xyxy, ts, etc.

# 2) Recuperar decisões humanas pra calibrar prompt
decisoes = INDEX["categorias_sinalizacao"]["vertical/pare-r1"]["decisoes_humanas"]
# → 72 votos. Filtrar approved vs refuted, montar exemplos no prompt:
#    "Em casos como este (evidencia: 'placa visível, candidato parou'), a decisão correta é approved."

# 3) Comparar com detecções CV existentes pra estimar prior
cv_hits = INDEX["categorias_sinalizacao"]["horizontal/pare-chao"]["deteccoes_cv_classicas"]
# → 424 hits, agrupados por hash de vídeo. Usa pra dedupe temporal antes de chamar VLM.

# 4) Validar contra vereditos do orchestrator
verdicts = INDEX["vereditos_orchestrator"]["lista"]
# → 9 análises completas com veredito por infração.
```

## Schema de labels (CVAT) — `tooling/cvat_workflow/valbot_labels.json`

20+ classes formalizadas pra anotação manual. Usar como **vocabulário canônico** quando criar novas categorias:

- Sinalização vertical: `sign-pare`, `sign-speed-r19`, etc.
- Sinalização horizontal: `road-pare-text`, faixa, seta.
- Pessoas/objetos: `person-driver`, `traffic-light`.
- Partes do veículo: `volante`, `cambio`, `freio-mao`, `chave-ignicao`.

Ao adicionar amostra nova: usar o nome de classe que existe no schema. Se precisar de classe nova, adicionar primeiro no `valbot_labels.json` pra manter consistência.

## Documentos de referência

`configs/references/`:
- `contran_anexo_ii_placas.pdf` (739 KB) — placas regulamentação/advertência CONTRAN.
- `mbst_vol_iv_sinalizacao_horizontal.pdf` (2.7 MB) — sinalização horizontal CONTRAN/MBST.

Use no system prompt do VLM como contexto de regulamentação.

## Pendências detectadas pelo consolidador

1. **`vertical/pare-r1` sem hits CV** — rodar `pare_sign.py` em produção nos 4 vídeos pra preencher (gap, tem só few-shot).
2. **`seta-esquerda/seta-reta` sem decisões humanas** — nunca apareceram no examples.jsonl porque `R1020-G-a` agrega "qualquer sinal vertical/horizontal não respeitado". Refinar `infracao_id` pra distinguir setas.
3. **`interno/cinto` sem few-shot crops** — adicionar entrada nova em `sinalizacao/interno/cinto/` com 2-3 frames de cinto visível vs ausente.
4. **`storage/audio/` vazio** — Whisper não rodou ainda; áudio do beep do freio-mão é sinal complementar (filosofia central § detector composto).

## Re-rodar consolidação

```bash
.venv/bin/python -m tooling.build_dataset_master
```

Sempre que adicionar:
- Novo crop few-shot (`tooling.build_sinalizacao_library --extract --annotate --crop-all`)
- Nova decisão humana (sessão de revisão DETRAN salva em `examples.jsonl`)
- Nova análise (`storage/analyses/<hash>/`)
- Novo PDF em `configs/references/`

→ rodar `build_dataset_master` pra atualizar `INDEX.json`.
