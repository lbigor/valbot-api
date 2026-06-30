# Changelog de Prompts / Detectores Valbot

Versionamento semântico ([SemVer](https://semver.org)) dos prompts que decidem o
julgamento da IA. Trilhas independentes:
- **Diretrizes Val** (`backend/matriz/prompt_builder.py:_DIRETRIZES_VAL`) — camada de
  interpretação sobre a Matriz MBEDV.
- **Detector Art. 208** (`backend/detectors/art208/prompts.py:DETECTOR_208_VERSION`) —
  segundo passe dedicado, em 2 estágios.

Regra: alterar texto/critério = bump SemVer + entrada aqui, no mesmo PR.
**MINOR** = muda julgamento; **PATCH** = redação; **MAJOR** = remove/inverte critério.
A versão é carimbada por análise (rastreabilidade).

---

## Detector Art. 208 — `DETECTOR_208_VERSION`

### [1.0.0] — 2026-06-30 — detector de 2 estágios (localizar → janela fps alto)
Primeira versão, **dormente** (não acionada em prod; persiste como código + testes).
Motivação (diagnóstico): o Art. 208 tinha recall 40,6% / precisão 47,2% no pipeline
único — atenção diluída entre ~80 artigos e a parada de 1-2s perdida na amostragem
~1fps. Fundamentado na doc do Gemini 2.5 Pro (ver memória `reference-gemini-video-processamento`):
fps não é a alavanca (resolução temporal, não espacial); recortar a janela dá foco
(recall) e custa ~20× menos tokens.
- **Estágio 1** (`PROMPT_ESTAGIO1_LOCALIZAR`, fps=1, vídeo inteiro): localiza
  semáforos/placas PARE, sem julgar.
- **Estágio 2** (`PROMPT_ESTAGIO2_DECIDIR`, fps=5, janela ±5s recortada por
  `startOffset/endOffset`): decide 208 com critério rigoroso, **só evidência visual**
  (luz vermelha visível + cruzou / placa PARE + não imobilizou); proíbe áudio e suposição.
- Custo medido ~$0,03/exame (vs $0,25 do pipeline atual).
- Avaliado contra o gabarito `exams.training_annotations` via `backend/eval/` (harness
  detector-agnóstico). Testes unitários mockados no CI; avaliação real opt-in
  (`VALBOT_RUN_VERTEX=1`, marker `vertex`).
- **Gate antes de ativar:** calibrar recall × FP × custo na amostra de FN de 208 e só
  então ligar via flag `VALBOT_ART208_DETECTOR` (default off).
