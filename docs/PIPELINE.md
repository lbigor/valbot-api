# Pipeline LaudoAI — fluxo de uma infração ponta a ponta

Documento de referência para qualquer um (humano ou LLM) que precise tocar
o pipeline sem precisar reconstruir a arquitetura a partir de 5 arquivos.

## Visão de 30 segundos

A "aplicação" de uma infração no laudo final atravessa **6 camadas**, em
ordem. Não há um único `if` global que diga "aplique agora" — cada camada
tem responsabilidade isolada e troca dados via JSON em disco.

```
┌────────────────────────────────────────────────────────────────────────┐
│ [1] INGESTÃO — extrai áudio, frames, layout das 4 câmeras               │
│     src/ingestion/grid_slicer.py, src/ingestion/keyframe_detector.py    │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [2] DETECTORES — produzem candidatos brutos por infração                │
│     src/detectors/cinto_heuristica.py        → cinto_trail.json         │
│     tooling/yolo_explore.py                  → yolo_explore/*.json      │
│     tooling/cv_detectors_runner.py           → cv_detections.json       │
│     tooling/scan_all_videos.py               → sinalizacao_scan.json    │
│     tooling/template_match_all_videos.py     → yolo_custom_detections   │
│                                                .json (NCC vs biblioteca)│
└─────────────────────────────────┬──────────────────────────────────────┘
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [3] TRIAGEM (Tier A pipeline)                                           │
│     src/tier_a_pipeline.py                                              │
│       _avaliar_cinto()         → veredito por amostra                  │
│       _avaliar_sinal_vertical()→ candidatos_para_revisao | sem_evidência│
│       _avaliar_mao_volante()   → não implementado ainda                 │
│     escreve em result.json#infracoes_avaliadas[*].status                │
│       = pendente_revisao_humana | aprovado | inconclusivo               │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [4] AVALIADOR (skill avaliador-detran OU revisor humano via UI)         │
│     ~/.claude/skills/avaliador-detran/                                  │
│     papel: lê candidatos pendentes, aplica checklist da taxonomia,      │
│            decide approved | refuted | inconclusive                     │
│     POST /api/analyses/<hash>/training-example                          │
│       → tooling/dev_backend_stub.py:1282                                │
│       → grava append em storage/training/examples.jsonl                 │
│                                                                         │
│     Caminhos paralelos que escrevem o MESMO examples.jsonl:             │
│       a) skill avaliador-detran rodando em loop autônomo                │
│       b) botão "✗ FP" no painel "Detecções IA" (frontend)               │
│       c) ingestão manual de prints (tooling/ingest_training_prints.py)  │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [5] CONFIRMAÇÃO POR VOTO (gate de promoção)                             │
│     src/tier_a_pipeline.py:_infracoes_confirmadas_por_voto (linha 360)  │
│     lê examples.jsonl, agrupa por (hash, infracao_id, frame_idx)        │
│     promove decisao=approved + vote=S → result.json#infracoes_detectadas│
│     este array é AUTORITATIVO pra o laudo final                         │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [6] LAUDO + EXIBIÇÃO                                                    │
│     src/reporting/adapter.py:120 → soma pontos, gera summary do laudo   │
│     tooling/dev_backend_stub.py:_laudo_from_result_json → painel        │
│       (mescla 6 fontes pra UI; ver "Bridge: 6 Fontes do painel" abaixo) │
│     src/reporting/pdf.py → renderiza PDF final                          │
└────────────────────────────────────────────────────────────────────────┘
```

## Taxonomia: gate estrutural Tier A/B/C

`src/rubrics/taxonomia.py` define o catálogo de infrações da Resolução
CONTRAN 1.020/2025. Cada `Infracao` tem:

- `tier` (`A` = automatizada hoje, `B` = passiva, `C` = pendente_infraestrutura)
- `cameras_relevantes` — quais câmeras o pipeline precisa olhar
- `checklist_visual` — perguntas que o avaliador (humano ou skill) responde
- `infra_faltante` — quando vazio, infração é avaliável; quando preenchido,
  cai como `pendente_infraestrutura` (ex.: `R1020-M-c` precisa de "áudio motor
  limpo" + "OBD RPM")

Mudança no escopo Tier A → mexer em `taxonomia.py` E em `_avaliar_*` do
`tier_a_pipeline.py`. Sem isso, a triagem não cobre.

## Bridge: 6 Fontes do painel "Detecções IA"

`tooling/dev_backend_stub.py:_laudo_from_result_json` mescla 6 fontes em
`scored.infracoes` (consumido pelo frontend AnaliseExame.tsx):

| Fonte | Origem | O que injeta |
|-------|--------|--------------|
| 1 | `result.json#infracoes_detectadas` | Já promovido pelo gate de voto. `veredito="detectado"` |
| 2 | `result.json#infracoes_avaliadas[*].candidatos_*` | Candidatos pendentes da triagem. Veredito do voto cruzado por (id, ts) ±1s |
| 3 | `examples.jsonl` (votos órfãos) | Voto que não casou com candidato — ex.: print ingerido manualmente |
| 4 | `storage/analyses/<h>/sinalizacao_panel.json` | Biblioteca anotada pelo usuário (`sinalizacao/<cat>/*.json`), validada por NCC |
| 5 | `storage/analyses/<h>/yolo_custom_detections.json` | Template-match denso contra biblioteca. **NÃO atravessa gate de voto** — não vira `infracoes_detectadas` automaticamente |
| 6 | Virtual fixo | `R1020-M-c` "motor morreu" sempre presente em `00:00→01:00`, todo vídeo |

**Pós-merge:** sort por ts + dedupe rolante de 60s por `id` (regra do
usuário: mesma infração só repete após 1 min).

## Caminho exato — `R1020-G-a` "Desobedecer à sinalização semafórica"

1. `tooling/cv_detectors_runner.py` detecta texto na pista (cv:road_text),
   `tooling/yolo_explore.py` detecta classe COCO `stop sign`. Ambos gravam
   em `storage/analyses/<hash>/{cv_detections,yolo_explore}.json`.
2. `tier_a_pipeline.py:_avaliar_sinal_vertical()` (linha 294) carrega
   essas detecções, filtra (overlay UI, persistência ≥3 frames, isolada-grande),
   monta `candidatos_suspeito` e `candidatos_confiavel`. Status = `pendente_revisao_humana`.
3. Bridge Fonte 2 emite no painel cada candidato com veredito derivado do status.
4. Avaliador-detran (skill) ou revisor (botão FP) vota. Vai pra `examples.jsonl`.
5. Próxima execução de `tier_a_pipeline.run()`: `_infracoes_confirmadas_por_voto()`
   (linha 360) varre `examples.jsonl`, promove `approved+S` → `infracoes_detectadas`.
6. `adapter.py:build_context()` (linha 120) soma pontos de `infracoes_detectadas`,
   monta `summary` do laudo.
7. `pdf.py` renderiza PDF.

## Caminho do "✗ FP" (botão no painel)

1. Usuário clica `✗ FP` numa linha do painel (`AnaliseExame.tsx:renderInfracaoItem`).
2. `fetch POST /api/analyses/<hash>/training-example` com `decisao=refuted`.
3. Backend (`dev_backend_stub.py:training_example`) faz append em `examples.jsonl`.
4. Frontend marca `ocultos` local (Set) — item some na hora.
5. Próximo refresh do laudo (15s ou reload), bridge Fonte 2/5 cruza voto refuted
   por (id, ts) ±1s, emite com `veredito="refutado"`. Frontend filtra refutados
   por padrão → item permanece sumido.

## Gap conhecidos (não cobertos hoje)

- **Fonte 5 (yolo_custom) não atravessa gate [5]**. Detecção `YOLOC-PARE_R1-frontal`
  marcada `detectado` no painel **não vira pontuação no laudo**. Pra contar,
  estender `_infracoes_confirmadas_por_voto` para reconhecer `infracao_id` do
  formato `YOLOC-*` e mapear de volta para `R1020-*`.
- **R1020-M-c (motor morreu)** — entrada virtual (Fonte 6) só serve pra dar
  ao avaliador um candidato pra votar. Triagem real precisa de `áudio motor`
  + detector RMS/VAD; hoje é placeholder.
- **R1020-MV-* (mão volante)** — taxonomia tem `R1020-MV-a` mas
  `_avaliar_mao_volante()` não existe no pipeline.

## Onde aplicar refutações em massa (Fase 2)

`tooling/aplicar_refutacoes.py`:
- Lê `examples.jsonl`, agrupa votos `decisao=refuted` por hash.
- Pra cada hash, abre `yolo_custom_detections.json` e filtra entradas
  que casam (mesma classe, mesma câmera, ±3s do ts refutado).
- Restart do backend faz painel refletir.

Comando:
```
.venv/bin/python tooling/aplicar_refutacoes.py
pkill -9 -f tooling.dev_backend_stub && \
  nohup .venv/bin/python -m tooling.dev_backend_stub > /tmp/valbot_backend.log 2>&1 &
```

## Memória do projeto que afeta este pipeline

`~/.claude/projects/-Users-igorlima-Documents-Valbot/memory/MEMORY.md`:

- `project_escopo_tier_a.md` — escopo Tier A (cinto, sinal vertical, mão volante)
- `project_motor_inicio_video.md` — entrada R1020-M-c sempre nos primeiros 60s
- `project_biblioteca_sinalizacao.md` — biblioteca de templates anotados
- `feedback_dedupe_janela_60s.md` — dedupe rolante 60s no painel
- `feedback_filosofia_central.md` — VLM consome gráfico simbólico, não imagem crua

## Storage — onde mora cada coisa

| Path | O que tem |
|------|-----------|
| `storage/videos/*.mp4` | Vídeos brutos do exame (4-câmera mosaic 1280×720) |
| `storage/analyses/<hash>/result.json` | Resultado do tier_a_pipeline (autoritativo) |
| `storage/analyses/<hash>/yolo_explore/` | Saída crua do YOLO COCO |
| `storage/analyses/<hash>/cv_detections.json` | Detectores OpenCV clássicos |
| `storage/analyses/<hash>/sinalizacao_scan.json` | Scan da biblioteca |
| `storage/analyses/<hash>/sinalizacao_panel.json` | Validações da biblioteca pro painel |
| `storage/analyses/<hash>/yolo_custom_detections.json` | Template-match denso |
| `storage/analyses/<hash>/cinto/` + `cinto_trail.json` | Frames + veredito cinto |
| `storage/training/examples.jsonl` | **Append-only**: todos os votos do avaliador |
| `storage/training/dataset_master/` | Dataset consolidado para retro-treino |
| `storage/training/yolo_runs_sinalizacao/` | Pesos do YOLO custom treinado |
| `sinalizacao/<categoria>/*_crop.png` | Templates anotados manualmente (13 hoje) |
