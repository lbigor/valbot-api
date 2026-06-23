# Requisitos do Laudo v2.0 — Tabela de Gap (doc Valma × código atual)

> Ponte rápida entre a **Especificação do Laudo Técnico v2.0** (`Val_Auditor_Especificacao_Laudo_v2.docx`, Valma, jun/2026) e o código do Valbot.
> Legenda: ✅ atende · 🟡 parcial · ❌ falta · `[DIFERIDO]` depende de infra/terceiros (fora da fila P0/P1).
> Âncora de código relativa ao repo. Spec completa em `spec.md`; desenho em `plan.md`; backlog em `tasks.md`.

## Resumo executivo
| Métrica | Valor |
|---|---|
| Blocos do laudo | 12 |
| ✅ Atende | 4 (blocos 5, 6, 11 e parte do 12) |
| 🟡 Parcial | 5 (blocos 1, 3, 4, 7, 9) |
| ❌ Falta | 2 (blocos 8, 10) |
| Itens `[DIFERIDO]` | ICP-Brasil, carimbo de tempo, PDF/A-2, biometria 1:1 base DETRAN, telemetria URE |
| Restrição | Implementação pertence às tarefas paralelas `feat/relatorios-laudo-paginacao` e `feat/marcos-cobertura-integral` |

## Gap por bloco
| # | Bloco | Status | Âncora no código | O que falta | FR |
|---|---|---|---|---|---|
| 1 | Cabeçalho + hashes | 🟡 | `backend/reporting/laudo.py` (`integridade`, `hash_relatorio()`, `versoes`) | hash da Matriz; fichas MBEDV usadas; código único do laudo; assinatura ICP-Brasil `[DIFERIDO]` | FR-LAU-01, T4 |
| 2 | Sumário Executivo | 🟡 | espalhado no laudo JSON | bloco dedicado; semáforo 5 cores (§5.3); 3–5 indicadores-chave; recomendação | FR-LAU-02 |
| 3 | Identificação Completa | 🟡 | `laudo.py` (`identificacao`, `candidato`, `examinador`) | comissão (composição); veículo (duplo-comando); CFC; unidade; trajeto/URL; tentativa nº; máscara LGPD versão controlada | FR-LAU-03, T1 |
| 4 | Resultado Oficial | 🟡 | `laudo.py` (`resultado_oficial`) | anotações TPA cronológicas; registrador por anotação; motivo de interrupção + art. MBEDV; integrador envia poucos campos | FR-LAU-04 |
| 5 | Resultado Calculado ValBot | ✅ | `laudo.py` (`resultado_calculado`) + `engines/pontuacao.py` + §8.3 evidência insuf. | formalizar confiança agregada | FR-LAU-05 |
| 6 | Análise de Divergência (5 tipos) | ✅ | `laudo.py` (`divergencia`) + `engines/comparacao.py` | cores/severidade no laudo; casos especiais §9.4; justificativa 2–3 parágrafos | FR-LAU-06 |
| 7 | Detalhamento de Infrações | 🟡 | `laudo.py` (`analise_detalhada`) | numeração INF-NNN; cor de severidade; links internos timeline/vídeo; recomendação técnica Confirmar/Revisar/Descartar | FR-LAU-07 |
| 8 | Linha do Tempo | ❌ | — (eventos brutos em `exam_eventos`, migration 011) | bloco cronológico integrando os 8 tipos de evento (telemetria+áudio+TPA+decisões IA); cor por tipo; link de vídeo | FR-LAU-08 |
| 9 | Conduta do Examinador | 🟡 | `laudo.py` (`eventos_examinador`) — só inadequado | classificação tripla adequado/atenção/inadequado; % conformidade; fundamentação MBEDV; recomendação de apuração | FR-LAU-09 |
| 10 | Checklist 12 itens Anexo K | ❌ | — | 12 validações binárias automáticas; itens críticos (1,2,8,9,10) escalam; indicador "X de 12"; biometria 1:1 `[DIFERIDO]` | FR-LAU-10 |
| 11 | Encaminhamento 4 níveis | ✅ | `backend/workflow/ordens.py` + `laudo.py` (`ordem_servico`) | campos de parecer/decisão dentro do laudo; estados §14.3 (parcial) | FR-LAU-11 |
| 12 | Trilha de Auditoria | ✅/🟡 | `backend/workflow/ordens.py` (`os_eventos` append-only) + `laudo.py` (`versoes`) | log de acesso por usuário; carimbo de tempo `[DIFERIDO]`; replicação em metadados do PDF | FR-LAU-12, T2 |

## Transversais
| Requisito | Status | Âncora | Falta | FR |
|---|---|---|---|---|
| LGPD / máscara | 🟡 | `laudo.py` `_mascarar_cpf()` | versão controlada (nome/foto) vs. externa | FR-LAU-T1 |
| Versões do laudo (PRELIM/INTER/FINAL/CONSOLID) | ❌ | — | máquina de emissão por momento (§16.1) | FR-LAU-T2 |
| Formatos (JSON/HTML/PDF-A2/assinado) | 🟡 | `src/reporting/pdf.py` (WeasyPrint best-effort) | HTML interativo; PDF/A-2 e assinado `[DIFERIDO]` | FR-LAU-T3 |
| Integridade (hashes vídeo/laudo/Matriz) | 🟡 | `hash_relatorio()` | hash da Matriz no cabeçalho | FR-LAU-T4 |
| IA consultiva / não-substituição | ✅ | `backend/committee/comite.py` (read-only) + constitution §I | — | FR-LAU-T5 |
| Não-pontuáveis → compliance | ✅ | `backend/engines/excecoes.py` + `exam_comentarios_compliance` (migration 016) + constitution §V | — | FR-LAU-T6 |

## Itens diferidos (Pendências §18 do doc)
| Item | Responsável | Dependência |
|---|---|---|
| Assinatura ICP-Brasil | Rodrigo | certificado A1/A3 da Valma |
| Carimbo de tempo qualificado | Rodrigo | autoridade de carimbo (pós-piloto) |
| Biometria 1:1 (checklist item 1) | Igor + integração | acesso à base biométrica DETRAN |
| PDF/A-2 conforme | Igor | template + validador PDF/A |
| Telemetria URE (linha do tempo) | integrador | feed de sensores URE |
