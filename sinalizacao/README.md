# Biblioteca de modelos visuais de sinalização

Referência few-shot pra VLM (Qwen2.5-VL / Claude Sonnet) e dicionário visual humano. Cada PNG é o crop da câmera onde a sinalização aparece, com bounding box vermelha + label sobreposto.

## Estrutura

```
sinalizacao/
├── vertical/pare-r1/         # placa R-1 (octogonal vermelha PARE)
├── horizontal/pare-chao/     # LMS — palavra PARE pintada no asfalto
├── horizontal/seta-esquerda/ # LMS — seta direcional esquerda
├── horizontal/seta-reta/     # LMS — seta direcional frente
├── horizontal/faixa-pedestre/# LFO — faixa zebrada de travessia
└── circuitos/circuito-vid2-vid3/  # mapa temporal das sinalizações no circuito
```

## Convenção de nomenclatura

`NN_vidX_tMM-SS_camera.png` → `04_vid2_t01-41_frontal.png` = entrada #4, vídeo `2.mp4`, timestamp 01:41, câmera frontal.

Pra cada slug existem 4 arquivos:
- `<slug>_crop.png` — **só a sinalização**, padding 8px, ampliado 4× → modelo few-shot pra VLM
- `<slug>.png` — frame com bbox vermelha + label sobreposto → dicionário humano / dashboard
- `<slug>_raw.png` — recorte cru da câmera 640×360 (sem anotação) → debug / re-anotação
- `<slug>.json` — metadata (vídeo, ts, bbox, tipo CONTRAN, espelhada, paths, etc)

**Estratégia de avaliação completa em [ESTRATEGIA_AVALIACAO.md](ESTRATEGIA_AVALIACAO.md)** — fluxo detector clássico → crop → VLM few-shot → laudo, mapeamento crop→infração CONTRAN, política de confiança, integração com `vlm_engine.py` / `orchestrator.py`.

**Dataset master consolidado em [DATASET_MASTER.md](DATASET_MASTER.md)** — 760 amostras de TODAS as fontes do projeto (few-shot + decisões humanas + detecções CV + bboxes manuais + vereditos + referências CONTRAN). Índice em `storage/training/dataset_master/INDEX.json`.

## Convenção quad-view (VIP Intelbras)

```
+----------+-----------------+
| frontal  | lateral_direita |
+----------+-----------------+
| interna  | traseira_esq    |
+----------+-----------------+
```

Hikvision usa layout diferente (interna em TL, frontal em TR) — `GridSlicer.detect_layout` decide via OCR da marca d'água.

## Câmera traseira ≠ espelho horizontal

Sinalização vista pela câmera traseira **NÃO** é espelhada como num retrovisor. A traseira aponta pra trás do veículo, então uma seta esquerda no chão aparece apontando esquerda também — só vista de outro ângulo (atrás-pra-frente). Quando o frame mostra a seta após o veículo cruzar por cima, a forma fica em diagonal e parcialmente recortada pelo limite inferior.

JSON marca `"espelhada": true` em frames de câmera traseira pra deixar essa nuance explícita pro VLM.

## Como o VLM consome

Em vez de mandar frame cru + pergunta, o prompt vai enriquecido:

```python
prompt = f"""
{categoria_readme}                    # ex.: README de horizontal/pare-chao
Compare a imagem do exame abaixo com os {N} exemplos anotados.
Devolva JSON: {{"detected": bool, "confidence": float, "evidence": str}}
"""
images = [<frame do exame>] + [<2-3 PNGs anotados da categoria>]
```

Plug em `src/analysis/vlm_engine.py` — adicionar método `analyze_with_fewshot(infracao_id, frame, category)` que carrega o README + amostra 2 PNGs da `sinalizacao/{category}/` e injeta como `image_url`.

## Circuitos repetidos

`circuitos/circuito-vid2-vid3/` documenta sinalizações que aparecem em ordem nos vídeos `2.mp4` e `3.mp4` (mesmo trajeto de exame). Útil pra calibrar matching temporal e validar varredura automática.

## Status atual (2026-04-28)

13/14 entradas concluídas. Vídeo `3.mp4` pendente — varredura via `pare_sign.py` + easyocr "PARE" + detector de seta horizontal a ser executada (task #5 do plano).
