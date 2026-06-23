# Feature Spec — Laudo Técnico v2.0 (12 blocos)

**Short name:** laudo-v2 · **Status:** Draft · Base: `Val_Auditor_Especificacao_Laudo_v2.docx` (Valma, jun/2026) + `docs/constitution.md` + Resolução CONTRAN 1.020/2025 + MBEDV + Anexo K (TR DETRAN-SE).

> Esta spec converte a **Especificação do Laudo Técnico v2.0** em requisitos versionados. A implementação de código pertence às tarefas de laudo em andamento (`feat/relatorios-laudo-paginacao`, `feat/marcos-cobertura-integral`) — esta feature é a **fonte de requisitos** que as alimenta. Mapa gap→arquivo em `requisitos_laudo_v2.md`; desenho técnico em `plan.md`.

## Resumo
O laudo é o **entregável final** da análise da plataforma: um documento técnico-jurídico que reúne, num só artefato, a comparação entre o resultado oficial da Comissão Examinadora e a análise automatizada da IA (ValBot), fundamentada na Resolução 1.020/2025 e no MBEDV. A v2.0 expande o laudo de uma comparação numérica para **12 blocos nomeados**, atende ao **checklist do Anexo K** do TR DETRAN-SE e estabelece **trilha de auditoria, versões e hashes**. O laudo é gerado para **todos** os exames: curto e de arquivamento direto quando não há divergência; completo e acionando o **fluxo de 4 níveis** (IA → Comitê → Auditor → Supervisor) quando há.

Princípio diferenciador (doc §2.2): o laudo audita **candidato + examinador + infraestrutura de exame** — não só o resultado do candidato.

## User Scenarios & Testing

### US1 — Laudo de exame sem divergência (arquivamento direto) (P1, MVP)
Concluída a análise da IA e havendo concordância com o resultado oficial, a plataforma gera um laudo curto (blocos 1, 3, 4, 5, 7, 8, 10, 12) e o encaminha a arquivamento sem ação humana. **Testável:** exame concordante produz laudo com semáforo verde no Sumário, sem bloco 6/11, e estado `ARQUIVADO_SEM_ACAO`.

### US2 — Laudo de exame com divergência aciona 4 níveis (P1, MVP)
Detectada divergência, o laudo classifica o tipo (1 dos 5), adiciona os blocos 2/6/9/11 e abre Ordem de Serviço encaminhando ao Comitê → Auditor → Supervisor. **Testável:** exame divergente produz laudo com `divergencia.tipo` ∈ {1_resultado…5_evidencia}, semáforo de cor correspondente e OS em `AGUARDANDO_COMITE`.

### US3 — Linha do tempo integrada do exame (P1)
O laudo apresenta a cronologia do exame integrando telemetria, áudio do candidato/examinador, anotações TPA e decisões da IA, com timestamps. **Testável:** o bloco 8 lista eventos ordenados por tempo, cada um com tipo (8 tipos), origem e timestamp; cada evento é vinculável ao trecho de vídeo no portal.

### US4 — Auditoria da conduta do examinador (P1)
O laudo classifica cada comentário do examinador como adequado / atenção / inadequado-vedado conforme o MBEDV, com transcrição literal e timestamp, e calcula a % de conformidade. **Testável:** comentário "Olha, pelo amor de Deus…" é classificado `inadequado` com fundamentação MBEDV; comentários inadequados **não** entram na pontuação do candidato (constitution §V) e geram recomendação de apuração contra o examinador.

### US5 — Checklist técnico do Anexo K (12 itens) automatizado (P1)
O laudo preenche automaticamente os 12 itens binários do Anexo K (biometria, continuidade da gravação, qualidade de câmera/áudio, tom, etc.) com SIM/NÃO/N-A/REQUER-VERIFICAÇÃO-HUMANA. **Testável:** o bloco 10 mostra 12 itens com veredito; itens críticos (1, 2, 8, 9, 10) que falham escalam automaticamente ao Auditor; indicador agregado "passou em X de 12".

### US6 — Sumário executivo legível em 30 segundos (P1)
Qualquer leitor (Comissão, DETRAN, jurídico) entende o caso em 1 página: resultado oficial × calculado em destaque, semáforo de concordância/divergência, tipo de divergência, 3–5 indicadores-chave e recomendação de encaminhamento. **Testável:** o bloco 2 contém todos esses campos e a cor do semáforo segue a regra §5.3 (verde/vermelho/laranja/cinza/roxo).

### US7 — Identificação completa do exame (P2)
O laudo reúne identificação de candidato (mascarado por LGPD), examinador, comissão, veículo (duplo-comando cat. B), unidade, CFC, tempo e trajeto. **Testável:** o bloco 3 traz todas as categorias; CPF/RG mascarados; nome completo e foto biométrica só em versão controlada (acesso restrito).

### US8 — Detalhamento auditável por infração (P2)
Cada infração (da Comissão, da IA ou de ambos) tem cabeçalho (origem, código VAL, CTB, MBEDV), conduta observada, natureza/peso, evidência (câmera, vídeo, áudio, telemetria), confiança, exceções analisadas e descartadas, fundamentação normativa e recomendação técnica. **Testável:** cada item do bloco 7 tem número sequencial (INF-001…), cor de severidade e link interno para a linha do tempo no timestamp.

### US9 — Versões, formatos e trilha de auditoria (P2)
O laudo é emitido em momentos definidos (PRELIMINAR/INTERMEDIÁRIO/FINAL/CONSOLIDADO) e formatos (JSON, HTML interativo, PDF/A-2, PDF assinado). A trilha registra versões (spec, Matriz, modelos), timestamps de cada etapa, log de acesso e hashes. **Testável:** o bloco 12 é imutável após emissão, replicado nos metadados do PDF; o bloco 1 carrega hashes do vídeo, do laudo e da Matriz.

### Edge cases
- **Evidência insuficiente** (corte/ângulo/áudio): bloco 5 §8.3 explicita trechos não analisados, motivo, impacto na pontuação e recomendação ao Auditor; divergência classificada como Tipo 5 (Cinza).
- **Interrupção pela Comissão sem condição detectada pela IA**: divergência específica "interrupção indevida" (doc §9.4); semáforo roxo.
- **APROVADO calculado + gravíssima detectada**: sinaliza possível bug ou ficha MBEDV não aplicada (doc §9.4) — requer revisão.
- **Dados oficiais ausentes** (sem pontuação/infrações da Comissão): não passa batido — vira divergência Tipo 5 e o bloco 4 marca campos ausentes.
- **Concordância por caminhos diferentes** (ambos reprovam por infrações distintas): classificar Tipo 3 ou 4.
- **Versão controlada / auditoria externa**: nome de candidato/examinador e foto biométrica omitidos/mascarados.

## Requirements (Functional)

### Por bloco (1 FR por bloco do doc)
- **FR-LAU-01 (Bloco 1 — Cabeçalho e Identificação):** código único do laudo, data de emissão, versão da spec, versão da Matriz Nacional, modelo de IA principal e do Comitê, resolução vigente, fichas MBEDV utilizadas, hash do vídeo, hash do laudo. Assinatura digital ICP-Brasil — **[DIFERIDO — Pendências §18, resp. Rodrigo, dep. cert A1/A3]**.
- **FR-LAU-02 (Bloco 2 — Sumário Executivo):** resultado oficial e calculado em destaque com pontuação; semáforo de concordância/divergência (regra §5.3: verde=concordância, vermelho=div. resultado, laranja=div. silenciosa, cinza=evidência insuf., roxo=interrupção); tipo de divergência; 3–5 indicadores-chave (duração, infrações, qualidade técnica, conduta do examinador); recomendação de encaminhamento.
- **FR-LAU-03 (Bloco 3 — Identificação Completa):** candidato, examinador, comissão (composição + designação), veículo (placa/modelo/ano/categoria/duplo-comando), unidade (CTR/CIRETRAN), CFC, tempo (início/fim/duração/fuso), trajeto (tipo + URL de rota se houver).
- **FR-LAU-04 (Bloco 4 — Resultado Oficial):** decisão oficial (APROVADO/REPROVADO/INTERROMPIDO), pontuação oficial, motivo de interrupção (texto + art. MBEDV), lista de infrações apontadas (timestamp, CTB, ficha MBEDV, natureza, peso, observação textual TPA), anotações TPA cronológicas e identificação do registrador.
- **FR-LAU-05 (Bloco 5 — Resultado Calculado ValBot):** decisão calculada (incl. EVIDÊNCIA_INSUFICIENTE), pontuação calculada, limite normativo (≤10), infrações detectadas (mesma estrutura do bloco 4), eventos sem enquadramento (contextual, não pontua), confiança agregada (alta/média/baixa) e tratamento de evidência insuficiente (§8.3).
- **FR-LAU-06 (Bloco 6 — Análise de Divergência):** classificação em 1 dos 5 tipos com cor/severidade, subtipos associados, justificativa técnica (2–3 parágrafos), referência a fichas MBEDV/CTB, hipóteses de causa e confiança da própria análise. Tratamento dos casos especiais §9.4. **Obrigatório só quando há divergência.**
- **FR-LAU-07 (Bloco 7 — Detalhamento das Infrações):** por infração — origem (Comissão/IA/Ambos), código VAL sequencial (INF-NNN), CTB, ficha MBEDV, conduta observada, natureza/peso (leve 1/média 2/grave 4/gravíssima 6), evidência (câmera, vídeo, áudio, telemetria), confiança + explicação, exceções analisadas e descartadas com motivo, fundamentação normativa integral, recomendação técnica (Confirmar/Revisar/Descartar). Vinculação visual: cor de severidade + link para a linha do tempo + link para o trecho de vídeo.
- **FR-LAU-08 (Bloco 8 — Linha do Tempo):** cronologia integrando os 8 tipos de evento — telemetria (URE), comportamento (visão computacional), áudio do candidato, áudio do examinador, anotação TPA, início/fim de etapa, decisão da IA, interrupção. Cada evento: tipo, origem, timestamp, descrição; cor por tipo; clicável para o trecho de vídeo no portal.
- **FR-LAU-09 (Bloco 9 — Conduta do Examinador):** lista cronológica de comentários (transcrição literal + timestamp), classificação automática (adequado / atenção / inadequado-vedado) conforme vedações MBEDV, fundamentação quando inadequado, indicador agregado de conformidade (% adequado), recomendação ao DETRAN para apuração quando houver inadequado. Comentários inadequados **não pontuam o candidato** (constitution §V); examinador omitido em uso externo ao DETRAN.
- **FR-LAU-10 (Bloco 10 — Checklist Técnico Anexo K):** 12 itens binários com validação automática (biometria 1:1 — **[DIFERIDO, dep. base biométrica DETRAN]**; continuidade da gravação; candidato no veículo até o fim; examinador identificado; faltas informadas; resultado INAPTO comunicado; tom respeitoso; câmeras reguladas; câmeras nítidas/sincronizadas; áudio sem interrupção/delay; sem queixa mecânica; comportamento adequado). Cada item: SIM ✅/NÃO ❌/N-A ➖/REQUER-VERIFICAÇÃO-HUMANA ⚠ + timestamp quando NÃO; itens críticos (1,2,8,9,10) que falham escalam ao Auditor; indicador "passou em X de 12".
- **FR-LAU-11 (Bloco 11 — Encaminhamento e Pareceres):** encaminhamento sugerido pela IA; laudo do Comitê de IA (read-only — constitution §I); campos de parecer do Auditor (decisão + justificativa + ref. MBEDV + assinatura) e decisão do Supervisor (decisão final + concordância + justificativa + assinatura); máquina de estados §14.3 (AGUARDANDO_COMITE … CONCLUIDO_*/ARQUIVADO_SEM_ACAO); editável no portal web, espaço de registro no PDF. **Obrigatório só quando há divergência.**
- **FR-LAU-12 (Bloco 12 — Trilha de Auditoria):** versão da spec, da Matriz, dos modelos (IA principal + Comitê); timestamp de cada etapa (ingestão, fim análise, fim Comitê, fim Auditor, fim Supervisor); identificação de cada usuário que acessou/alterou; hash do vídeo original e do PDF final; assinatura ICP-Brasil e carimbo de tempo qualificado — **[DIFERIDO]**. Bloco imutável após emissão, replicado nos metadados do PDF.

### Transversais
- **FR-LAU-T1 (LGPD):** CPF/RG e documentos sempre mascarados; nome completo e foto biométrica apenas em versão controlada (acesso restrito); dados do CFC podem aparecer integralmente. (doc §6.2)
- **FR-LAU-T2 (Versões do laudo):** emissão em 4 momentos — PRELIMINAR (pós-IA: blocos 1,3,4,5,7,8,10,12), INTERMEDIÁRIO (pós-Comitê: +2,6,9,11), FINAL (pós-Supervisor: todos + assinaturas), CONSOLIDADO (snapshot imutável a qualquer momento). Versões anteriores arquivadas; FINAL é a oficial. (doc §16.1–16.2)
- **FR-LAU-T3 (Formatos de saída):** JSON estruturado (canônico, integração), HTML interativo (portal), PDF/A-2 **[DIFERIDO]**, PDF assinado ICP-Brasil **[DIFERIDO]**. Distribuição: PDF/A ao bucket Techpark via API; JSON via REST autenticada; HTML no portal. (doc §16.3–16.4)
- **FR-LAU-T4 (Integridade):** hashes SHA-256 do vídeo, do laudo e da Matriz garantem inviolabilidade do conjunto; o hash do laudo ignora o próprio campo de hash (reúso de `hash_relatorio()`). (doc §2.1, §15.2)
- **FR-LAU-T5 (Não-substituição / IA consultiva):** toda saída da IA é recomendação técnica ao decisor humano; o Comitê explica e fundamenta, nunca decide (constitution §I). (doc §2.1)
- **FR-LAU-T6 (Não-pontuáveis viram compliance):** motor que morre, baliza isolada e exceção do preposto **não** pontuam — viram sinais de compliance, separados das infrações (constitution §V; emenda 1.1.0). (doc §8.2 / §9.4)

## Clarificações (resolvidas)
Etapa `/clarify` do SDD — 3 ambiguidades finas resolvidas com defaults fundamentados (decisão pode ser revista pela implementação):

- **CL-01 — Granularidade da linha do tempo (FR-LAU-08):** cada `EventoDetectado` com timestamp vira **um ponto** na linha do tempo (sem downsampling/amostragem), agrupado visualmente por etapa do exame. Critério: o laudo é peça de auditoria — perder eventos esconde evidência. Se o volume de pontos prejudicar a leitura, o agrupamento por etapa colapsa visualmente (decisão de UI), **mas o JSON mantém todos**.
- **CL-02 — Fonte da telemetria (FR-LAU-08):** a única fonte hoje é `payload.telemetria` (dict opcional). Quando ausente/vazia, o bloco 8 marca **"telemetria indisponível"** e segue com áudio + visão + TPA + decisões IA. O feed de sensores **URE** é `[DIFERIDO]` (integrador) — quando chegar, alimenta o mesmo contrato `EventoLinhaTempo` com `tipo=telemetria`.
- **CL-03 — Automatização dos 12 itens do Anexo K (FR-LAU-10):** _revisado conforme a implementação do PR #58 (`backend/reporting/checklist_anexo_k.py`) — princípio: **nunca emitir `SIM` sem sinal automático confiável**; na ausência de sinal o item fica `REQUER_VERIFICACAO_HUMANA`._
  - **Automatizado hoje (6):** item 2 (continuidade — via `validator_veredito`/duração), 7 (tom respeitoso — reúsa bloco 9/conduta), 8 e 9 (câmeras reguladas/nítidas — `layout_confianca ≥ 0.7`), 10 (áudio sem delay — `evidencia_suficiente`), 12 (comportamento — conduta inadequada).
  - **`REQUER_VERIFICACAO_HUMANA` por ora (6):** item 1 (biometria 1:1) e item 4 (examinador identificado) — `[DIFERIDO]`/baixa confiança; itens 3 (candidato no veículo), 5 (faltas informadas), 6 (INAPTO comunicado) e 11 (queixa mecânica) — **sem sinal automático confiável ainda**. Follow-up (`tasks.md` FASE 3): detecção de áudio (palavras-chave) para 5/6/11 e visão para 3 promovem esses itens a automáticos.

## Reconciliação com a implementação (PR #58)
O PR #58 (`feat(laudo): laudo PDF oficial v2.0`) implementa esta spec, condensando os 12 blocos canônicos em **8 blocos visuais de PDF**. Coberto fielmente: blocos 1–10 (`backend/reporting/laudo_pdf_view.py`, `regras_laudo.py`, `checklist_anexo_k.py`, `textos_laudo.py`). Notas de fronteira:
- **Bloco 8 (Linha do Tempo):** o `_linha_do_tempo` funde infrações + anotações TPA + observações + marcos de início/fim. **Telemetria URE** não entra como tipo distinto (coerente com **CL-02 `[DIFERIDO]`**) e **início/fim de etapa** (ex.: baliza) ainda não é tipo próprio — gap conhecido para quando o feed URE/etapas chegar.
- **Blocos 11 (Encaminhamento) e 12 (Trilha):** o PDF traz apenas o `encaminhamento` sugerido e hashes/versões/timestamps; **pareceres do Auditor/Supervisor, estados §14.3 e log de acesso por usuário vivem no fluxo de OS** (`backend/workflow/ordens.py` + `docs/specs/fila-auditor`), não no PDF. O **log de acesso por usuário (FR-LAU-12)** é o item de software residual a implementar após o merge do #58.

## Key Entities
- **Laudo**: versão (PRELIMINAR/INTERMEDIÁRIO/FINAL/CONSOLIDADO), código único, momento de geração, hashes, formato.
- **Bloco**: 1 dos 12; obrigatoriedade condicional (sempre vs. quando há divergência).
- **Infração (INF-NNN)**: origem, CTB, ficha MBEDV, natureza/peso, evidência, confiança, exceções, recomendação técnica.
- **Evento de linha do tempo**: tipo (1 dos 8), origem, timestamp, descrição, link de vídeo.
- **Comentário do examinador**: transcrição, timestamp, classificação (adequado/atenção/inadequado).
- **Item de checklist (Anexo K)**: nº (1–12), veredito (SIM/NÃO/N-A/REQUER-HUMANA), criticidade, timestamp.
- **Divergência**: tipo principal (1–5) + subtipos, cor/severidade, justificativa, confiança.
- **Encaminhamento/OS**: estado (§14.3), pareceres do Auditor e do Supervisor.
- **Trilha de auditoria**: versões, timestamps por etapa, log de acesso, hashes, assinatura.

## Success Criteria
- **SC-01:** Laudo é gerado para **todos** os exames; sem divergência → curto + arquivamento; com divergência → completo + 4 níveis. (doc §1.3)
- **SC-02:** Os 12 blocos estão especificados, cada um rastreável a uma seção do documento da Valma e a um FR-LAU.
- **SC-03:** Toda infração exibida tem artigo CTB + ficha MBEDV + nível de confiança + exceções analisadas (explicabilidade — constitution §III).
- **SC-04:** Os 12 itens do Anexo K têm regra de validação automática definida; os 5 críticos têm escalonamento ao Auditor especificado.
- **SC-05:** O semáforo do Sumário cobre os 5 estados (verde/vermelho/laranja/cinza/roxo) com regra determinística.
- **SC-06:** Itens dependentes de infraestrutura/terceiros estão isolados como `[DIFERIDO]` com responsável, fora da fila P0/P1.
- **SC-07:** Comentário inadequado do examinador nunca altera a pontuação do candidato (constitution §V) — validável no backlog.

## Fora de escopo
- **Implementação de código** dos blocos — pertence às tarefas de laudo em paralelo (`feat/relatorios-laudo-paginacao`, `feat/marcos-cobertura-integral`); esta feature entrega a spec.
- **Assinatura digital ICP-Brasil, carimbo de tempo qualificado, PDF/A-2 conforme, biometria 1:1 contra base DETRAN, telemetria URE** — diferidos (FRs documentados, sem implementação nesta entrega).
- **Decisão final do Supervisor** e portais Auditor/Supervisor — cobertos por `docs/specs/fila-auditor` e pelo gap funcional `docs/gap_analysis_spec_v2.md`.
- **Retreino do modelo de IA** — a Matriz versionada altera o prompt sem retreinar (fora deste laudo).
