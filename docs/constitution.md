<!--
Sync Impact Report
- Version: 1.0.0 → 1.1.0 (MINOR, 2026-06-16)
- Emenda 1.1.0: §III ganha MUST "Códigos Exclusivos da Matriz" (IA só emite código existente
  na Matriz vigente; proibido código inventado). §V expande o tratamento de eventos não-pontuáveis:
  eventos §3.5 / condutas sem ficha viram comentário de compliance / observação de conduta —
  nunca pontuam NEM são descartados silenciosamente.
  Motivação: 2026-06-16 a IA havia emitido códigos fora da Matriz (MBEDV-MEC-*, R1020-*) pontuando
  indevidamente eventos como "motor morre" (§3.5); a limpeza removeu os pontos, mas a regra precisava
  ser explícita para evitar tanto a reintrodução de pontos quanto o descarte silencioso do sinal.
- Principios (1.0.0): I. Decisão Humana Soberana; II. Fluxo de 4 Níveis Sem Atalhos;
  III. Explicabilidade e Fundamentação Normativa; IV. Matriz Nacional Versionada e Rastreável;
  V. Pontuação Fiel à Norma; VI. Privacidade e Trilha de Auditoria (LGPD); VII. Integridade dos Dados de Negócio
- Seções: Padrões de Qualidade; Restrições de Arquitetura; Governança
- Fonte: docs/01-briefing-discovery/briefing.md + Especificação Funcional v2.0 (Res. CONTRAN 1.020/2025 + MBEDV)
  + docs/mapa_infracoes_r1020_mbedv.md (lista COMPLIANCE — condutas sem ficha pontuável)
- Artefatos a atualizar quando existirem: CLAUDE.md (refletir princípios), docs/specs/*/plan.md (Constitution Check),
  docs/specs/*/tasks.md (quality gates)
- TODOs pendentes: nenhum (constraints de entrega/SLA registrados como pendência no briefing, não na constitution)
-->

# Constituição do Projeto — Val Auditor Exames

Princípios imutáveis que governam arquitetura, qualidade e processo. Base normativa do produto:
**Resolução CONTRAN nº 1.020/2025 + MBEDV** (Senatran, 01/02/2026). A conformidade com estes
princípios é pré-requisito de qualquer spec, plan ou PR.

## Princípios Fundamentais

### I. Decisão Humana Soberana (NÃO-NEGOCIÁVEL)
A IA **apoia, audita, evidencia e recomenda — nunca decide nem reverte a decisão do exame**.
MUST: nenhum fluxo automatizado emite veredito formal; o resultado da IA é "calculado", nunca "oficial".
MUST: o Comitê de IA **explica** a divergência (laudo fundamentado) e **nunca a reverte ou encerra**.
*Why:* defensabilidade jurídica e aderência ao MBEDV — a competência de decidir é da Comissão/instância humana.

### II. Fluxo de 4 Níveis Sem Atalhos (NÃO-NEGOCIÁVEL)
Toda divergência percorre obrigatoriamente IA Principal → Comitê de IA → Auditor → Supervisor.
MUST: o Supervisor analisa **toda** divergência, mesmo quando o Auditor concorda com a IA.
MUST: não existe caminho que pule um nível; cada transição de OS é registrada na trilha.
*Why:* validação independente reduz viés (inclusive entre colegas/prepostos) e padroniza o rigor.

### III. Explicabilidade e Fundamentação Normativa (NÃO-NEGOCIÁVEL)
MUST: todo evento pontuado é fundamentado em norma vinculante — **artigo do CTB + ficha do MBEDV** — com timestamp, evidência e nível de confiança.
MUST: o laudo é emitido em **PDF + JSON com hash de integridade** e é inteligível por técnico, DETRAN, jurídico, candidato e órgão de controle.
MUST (Códigos Exclusivos da Matriz): a IA emite **somente** códigos existentes na **Matriz vigente** (`exam_rules`) — o `id` de cada infração é um artigo CTB/ficha MBEDV da Matriz, no formato canônico. É **proibido** inventar ou emitir códigos fora da Matriz (ex.: `MBEDV-MEC-*`, `R1020-*`); detecção que não casa um código válido **não pontua** e segue a regra de compliance do §V.
*Why:* sem fundamentação rastreável o laudo não sobrevive a recurso administrativo/ação judicial; código fora da Matriz infla pontuação e quebra a rastreabilidade normativa.

### IV. Matriz Nacional Versionada e Rastreável (NÃO-NEGOCIÁVEL)
A Matriz CTB/MBEDV é o ativo central e é **versionada**.
MUST: todo exame processado registra a `matriz_versao` utilizada.
MUST: evolução normativa gera **nova versão da Matriz**, sem necessidade de retreinar a IA; histórico de versões é preservado para auditoria.
*Why:* rastreabilidade regulatória e evolução independente da norma.

### V. Pontuação Fiel à Norma (NÃO-NEGOCIÁVEL)
MUST: pontuação acumulativa **leve=1 / média=2 / grave=4 / gravíssima=6**, aprovação com total **≤ 10**.
MUST: **não** existem faltas eliminatórias automáticas; exame **interrompido** = categoria especial **sem pontuação calculada**; eventos do MBEDV que "não pontuam" (motor morre, baliza isolada, exceção/orientação do preposto, conduta induzida por comentário inadequado) **não** geram pontos.
MUST (Não-pontuável vira compliance, não vira lixo): eventos §3.5 e condutas sem ficha pontuável (motor morre, baliza isolada, freio de mão, imperícia, e demais da lista COMPLIANCE de `docs/mapa_infracoes_r1020_mbedv.md`) **viram comentário de compliance / observação de conduta** — sinalizados para revisão humana —, **nunca somam pontos** e **nunca são descartados silenciosamente**. Remapear um evento não-pontuável para um artigo pontuável só para alterar o resultado é **violação** deste princípio.
*Why:* o cálculo deve ser idêntico à Resolução 1.020/2025 — é critério de Go/No-Go; e o sinal de conduta é insumo da decisão humana (§I/§II), não pode se perder.

### VI. Privacidade e Trilha de Auditoria — LGPD (NÃO-NEGOCIÁVEL)
MUST: CPF mascarado em logs e PDF; criptografia em trânsito (HTTPS) e em repouso para mídia/dados sensíveis.
MUST: trilha de auditoria **write-once**, retenção ≥ 12 meses; logs de acesso ≥ 6 meses; todo acesso a vídeo registrado.
*Why:* Valma é operadora de dados (Art. 39 LGPD); imutabilidade é exigência regulatória.

### VII. Integridade dos Dados de Negócio
MUST: motores Normativo, Pontuação e Comparação são **determinísticos** e cobertos por testes.
MUST: nenhum CRUD de registro de negócio por SQL direto — passa pelas camadas/regras; ingestão valida payload, idempotência por `exame_id` e integridade (hash do vídeo) antes de processar.
*Why:* consistência, anti-adulteração e reprodutibilidade do laudo.

## Padrões de Qualidade
- SHOULD: **rigor acima de velocidade** no Comitê de IA (SLA do Comitê pode exceder o da IA Principal).
- SHOULD: piloto com **Matriz mínima viável** (top ~30 condutas), expandindo com dataset real.
- MUST (Go/No-Go do piloto): ≥95% exames processados sem falha; cálculo de pontuação idêntico à Resolução; ≥90% enquadramentos validados como corretos.
- SHOULD (NFR): uptime ≥99%; análise IA ≤5 min/exame; throughput ≥200 exames/h; escala 100k/mês; RTO ≤4h, RPO ≤1h.
- MUST: mudança em motor determinístico acompanha teste; observabilidade (logs centralizados acessíveis ≤5 min).

## Restrições de Arquitetura
- MUST: decisão IA é "resultado calculado", dissociado do "resultado oficial" da Comissão; comparação produz **1 de 5 tipos de divergência** (resultado, pontuação, infração, enquadramento, evidência).
- SHOULD: separação em 5 motores especializados (Evidências, Detecção, Normativo, Pontuação, Comparação); portais hospedados pela Valma; PDF+JSON para o laudo.
- MUST: integração com a Techpark sem efeito colateral destrutivo — ingestão idempotente, falhas persistentes vão para DLQ (retenção 7 dias).

## Governança
- Esta constituição prevalece sobre conveniência de implementação. Specs (`/specify`), planos (`/plan`) e PRs DEVEM passar por Constitution Check; violação de princípio MUST bloqueia o merge.
- Exceções a um MUST exigem justificativa explícita registrada no PR e aprovação humana; são temporárias e rastreadas.
- Emendas seguem SemVer: **MAJOR** remove/redefine princípio incompatível; **MINOR** adiciona princípio ou expande seção; **PATCH** clarifica sem mudar semântica. Toda emenda atualiza o Sync Impact Report e a data.
- Constraints de entrega (prazo, equipe, budget, SLAs) vivem no briefing/pendências, não aqui — a constituição governa princípios, não cronograma.

**Version:** 1.1.0 | **Ratified:** 2026-06-14 | **Last Amended:** 2026-06-16
