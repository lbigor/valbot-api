# Tasks — laudo-v2

> Criticidade: 🔴 bloqueante · 🟡 importante · 🟢 incremental. Prioridade: **P0** software essencial · **P1** software completa o bloco · **P2** infra-diferido.
> A execução de código pertence às tarefas de laudo paralelas. Este backlog é o roteiro que as orienta. `[x]` = já existe no código atual.
>
> **📌 Estado (PR #58 — `feat(laudo): laudo PDF oficial v2.0`):** implementa a maior parte deste backlog — **FASE 0 (regras puras) + FASE 1 (blocos 8/9/10/2) + FASE 2 (blocos 1/3/4/5/6/7)** em `backend/reporting/{laudo_pdf_view,regras_laudo,checklist_anexo_k,textos_laudo}.py`. As regras determinísticas batem 1:1 com `plan.md §3`. **Residual de software após o merge do #58:** (a) log de acesso por usuário (bloco 12 — T2.7); (b) sinais faltantes do checklist (itens 3/5/6/11 — ver CL-03 revisado); (c) pareceres/estados §14.3 do bloco 11 vêm do fluxo de OS (`fila-auditor`), fora do PDF. Não reimplementar o que o #58 já entrega.

## FASE 0 — Fundação (modelos + regras puras)
- [ ] T0.1 🔴 P0 `backend/models.py`: novos contratos `EventoLinhaTempo`, `CondutaExaminador`+`ClassificacaoConduta`, `ItemChecklistAnexoK`+`ChecklistAnexoK`, `SumarioExecutivo`, `VersaoLaudo` (sem alterar os existentes). (FR-LAU-08/09/10/02, FR-LAU-T2)
- [ ] T0.2 🔴 P0 Funções puras determinísticas: `cor_semaforo()`, `item_critico()`, `pct_conformidade()`, `numerar_infracoes()` (INF-NNN). Testáveis isoladamente (constitution §VII). (FR-LAU-02/07/09/10)
- [x] T0.3 🔴 — Reúso `hash_relatorio()` e `_mascarar_cpf()` (`backend/reporting/laudo.py`). (FR-LAU-T1, FR-LAU-T4)

## FASE 1 — Blocos que faltam (❌ → software puro)
- [ ] T1.1 🔴 P0 **Bloco 8 — Linha do Tempo**: `linha_do_tempo` agregando `exam_eventos` + `comentarios_examinador` + anotações TPA + decisões IA; 8 tipos, ordenado por timestamp, cor por tipo, link de vídeo. (FR-LAU-08)
- [ ] T1.2 🔴 P0 **Bloco 10 — Checklist Anexo K**: `checklist_anexo_k` com 12 itens, validação automática (item 1 biometria → `requer_verificacao_humana` por ora), escalonamento dos críticos (1,2,8,9,10), indicador "X de 12". (FR-LAU-10)
- [ ] T1.3 🟡 P0 **Bloco 9 — Conduta Examinador**: estender `eventos_examinador` → `conduta_examinador` com classificação tripla adequado/atenção/inadequado, % conformidade, fundamentação MBEDV, recomendação de apuração. Garantir que inadequado **não** pontua o candidato. (FR-LAU-09, FR-LAU-T6)
- [ ] T1.4 🟡 P0 **Bloco 2 — Sumário Executivo**: `sumario_executivo` derivado, com semáforo 5 cores, tipo de divergência, 3–5 indicadores-chave, recomendação. (FR-LAU-02)

## FASE 2 — Completar blocos parciais (🟡)
- [ ] T2.1 🟡 P1 **Bloco 1**: adicionar `codigo_laudo` único, `fichas_mbedv` usadas, `integridade.matriz_hash`. (FR-LAU-01, FR-LAU-T4)
- [ ] T2.2 🟡 P1 **Bloco 3**: expandir identificação — `comissao`, `veiculo` (duplo-comando), `cfc`, `unidade`, `trajeto`, `tentativa_nro`; máscara LGPD versão controlada vs. externa. (FR-LAU-03, FR-LAU-T1)
- [ ] T2.3 🟡 P1 **Bloco 4**: `anotacoes_tpa` cronológicas, `registrador` por anotação, `motivo_interrupcao` + art. MBEDV. (FR-LAU-04)
- [ ] T2.4 🟡 P1 **Bloco 7**: `inf_id` (INF-NNN), `cor` de severidade, links internos (timeline/vídeo), `recomendacao_tecnica` (Confirmar/Revisar/Descartar). (FR-LAU-07)
- [ ] T2.5 🟡 P1 **Bloco 6**: `cor_severidade`, `justificativa_tecnica` (2–3 parágrafos), `hipoteses_causa`, casos especiais §9.4. (FR-LAU-06)
- [ ] T2.6 🟢 P1 **Bloco 11**: campos de parecer (Auditor) e decisão (Supervisor) dentro do laudo + estados §14.3. (FR-LAU-11) — coordenar com `docs/specs/fila-auditor`.
- [ ] T2.7 🟢 P1 **Bloco 12**: `trilha_auditoria.log_acesso` por usuário; replicar trilha nos metadados do PDF. (FR-LAU-12)

## FASE 3 — Transversais
- [ ] T3.1 🟡 P1 Versões do laudo (PRELIMINAR/INTERMEDIÁRIO/FINAL/CONSOLIDADO): parâmetro `VersaoLaudo` em `montar_laudo_json()` + seleção de blocos por momento (§16.1). (FR-LAU-T2)
- [ ] T3.2 🟢 P1 Formato HTML interativo no portal (estender `templates/laudo.html`); frontend `laudo.ts` recebe novos blocos (aditivo). (FR-LAU-T3)
- [ ] T3.3 🟡 P0 Testes determinísticos (cenários do `plan.md` §7): semáforo, checklist crítico, conduta-não-pontua, ordenação da timeline, parse aditivo, hash estável.

## FASE 4 — Diferidos (P2 — NÃO nesta entrega)
- [ ] T4.1 🟢 P2 Assinatura ICP-Brasil (resp. Rodrigo, dep. cert A1/A3). (FR-LAU-01/12)
- [ ] T4.2 🟢 P2 Carimbo de tempo qualificado (resp. Rodrigo, pós-piloto). (FR-LAU-12)
- [ ] T4.3 🟢 P2 PDF/A-2 conforme + validador. (FR-LAU-T3)
- [ ] T4.4 🟢 P2 Biometria 1:1 contra base DETRAN (checklist item 1). (FR-LAU-10)
- [ ] T4.5 🟢 P2 Telemetria URE no bloco 8 (dep. feed de sensores). (FR-LAU-08)

## Já atendidos no código atual (sem tarefa de implementação)
- ✅ **FR-LAU-05** (Bloco 5 — Resultado ValBot): `resultado_calculado` + `engines/pontuacao.py` + §8.3 evidência insuficiente. Só falta formalizar `confianca_agregada` (coberto em T0.1).
- ✅ **FR-LAU-T5** (IA consultiva / não-substituição): `backend/committee/comite.py` read-only + constitution §I. Invariante a preservar — sem código novo.

## FASE 5 — Esta tarefa (SDD — docs)
- [x] T5.1 🔴 `spec.md` — US + FR-LAU-01..12 + transversais + SC + fora de escopo.
- [x] T5.2 🔴 `requisitos_laudo_v2.md` — tabela de gap 12 blocos × status × arquivo × FR.
- [x] T5.3 🔴 `plan.md` — mapa 12-blocos→JSON, contratos, recomendação aditiva, reúso.
- [x] T5.4 🔴 `tasks.md` — este backlog.
- [ ] T5.5 🔴 Commit + PR (base `main`, `env -u GH_TOKEN gh`). Sem deploy (só doc).
