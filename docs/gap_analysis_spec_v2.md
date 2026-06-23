# Gap Analysis — Spec "Val Auditor Exames v2.0" × Valbot atual

> Documento de referência: `Val_Auditor_Exames_Especificacao_Funcional_v2 (v250526) (1).docx`
> (Valma + Techpark, junho/2026, baseado em CONTRAN 1.020/2025 + MBEDV)
>
> Sistema atual sob análise: Valbot em produção (`valbot.com.br`) — tag `a27bee5` em 28/05/2026.

## Resumo executivo

| Camada | Status | Observação |
|---|---|---|
| Lógica MBEDV (pontuação ≤10, sem eliminatórias, pesos 1/2/4/6) | ✅ **Atende** | Implementada em `tooling/bench_demo/presets/v26/cat_B/base.md` + `mbedv_rules.md` |
| 5 Motores (Evidências, Detecção, Normativo, Pontuação, Comparação) | 🟡 **Parcial** | 4 dos 5 fundidos no analyzer Gemini. Detalhe abaixo. |
| Matriz Nacional de Regras versionada | 🟡 **Parcial** | Temos catálogo MD (`mbedv_rules.md`), falta DB + versionamento + API |
| 5 tipos de divergência | 🟡 **1 de 5** | Só "Divergência de Resultado". Faltam Pontuação/Infração/Enquadramento/Evidência |
| 4 níveis decisão humana | ❌ **2 de 4** | Temos IA + revisão humana (revisores). Faltam Auditor e Supervisor dedicados |
| Comitê de IA (segunda análise antes do humano) | ❌ **Não existe** | Aprofundamento de divergência não implementado |
| Portais Auditor/Supervisor | ❌ **Não existe** | Frontend atual é admin/operador genérico, não tem fluxo OS |
| Dashboard regulatório | 🟡 **Operacional sim, regulatório não** | KPIs spec-específicos (concordância por unidade, infrações top, etc) faltam |
| Retroalimentação modelo | ❌ **Não automatizada** | `training_annotations` + `human_review` ficam no DB mas não voltam ao treino |

**Total estimado:** atende ~40% literal da spec. **Mas oferece 7 capacidades NÃO previstas** que vale destacar (vide §B).

---

## A. Gap por seção da spec

### §2 Visão Geral — 5 Motores Funcionais

| Motor da spec | Status Valbot | Implementação atual |
|---|---|---|
| 1. **Motor de Evidências** (captura insumos) | 🟡 **Parcial** | `init_upload` recebe `url`, `renach`, `processo`, `categoria` (na URL S3), `training_annotations`, `resultado_exame`. **FALTA** todos os campos do payload da spec §5.4: examinador/matrícula, candidato_nome formalizado, infrações apontadas oficialmente como lista discreta, telemetria/GPS, trajeto, tipo de exame (1ª/adição/etc.) |
| 2. **Motor de Detecção** (eventos brutos sem julgamento) | ❌ **Não separado** | Hoje VALBOT/Gemini gera direto o JSON de infrações enquadradas. Não temos camada de "eventos brutos" antes do enquadramento. Risco: dificulta debug + revisão por especialista |
| 3. **Motor Normativo** (eventos → regras CTB+MBEDV) | 🟡 **Parcial** | A Matriz vive no prompt (`presets/v26/cat_B/cam_*.md`) ≠ banco de dados queryável. Não temos `versao_regra`, `vigencia_inicio/fim`, `confiabilidade_deteccao` por regra |
| 4. **Motor de Pontuação** (soma + limite 10) | ✅ **Atende** | O Gemini já calcula `pontuacao_total` e o `aprovado` via prompt MBEDV |
| 5. **Motor de Comparação** (5 tipos) | 🟡 **1 dos 5 tipos** | Hoje só "Resultado": `r.diverge = (avaliador="A") !== (valbot=APROVADO)`. Faltam pontuação/infração/enquadramento/evidência |

### §3 Modelo de Pontuação

| Requisito spec | Status |
|---|---|
| Pesos: leve=1, média=2, grave=4, gravíssima=6 | ✅ Atende (em `cat_B/base.md`) |
| Limite reprovação > 10 pontos | ✅ Atende |
| Sem eliminatórias automáticas | ✅ Atende (Phase 2b removeu) |
| Categoria especial "interrompido" | ❌ **Não temos**. Sistema hoje tem `gate_rejected` (rejeição técnica) mas não "interrupção por incapacidade técnica/imperícia/instabilidade emocional" |
| Eventos que NÃO pontuam (veículo morre, baliza isolada, etc.) | 🟡 **Parcial via "condutas que NÃO pontuam"** dos fragments — mas falta verificar caso a caso |

### §4 Matriz Nacional de Regras

| Requisito spec | Status |
|---|---|
| `codigo_val` único por regra | ❌ **Não temos**. IDs ficam dentro dos fragments Markdown |
| Estrutura com 14 campos (artigo_ctb, ficha_mbedv, peso, evidencia_necessaria, etc.) | ❌ **Não modelado**. Está em texto livre nos prompts |
| Versionamento por regra + matriz completa | ❌ **Não temos** |
| Cada análise registra `matriz_versao` usada | ❌ **Não temos**. Temos `engine_preset` mas é o nome do prompt, não versão da Matriz |
| Banco relacional pra Matriz | ❌ **Não temos**. Markdown é fonte única |
| **Vínculo Normativo** explícito por evento | 🟡 Tem no prompt mas não estruturado no output |

> **Implicação:** sem Matriz em banco, fica impossível atender §15 (Dashboard "Infrações mais detectadas (top)") e §16 (Retroalimentação).

### §5 Motor de Evidências — Insumos Capturados

Comparativo do payload de `init_upload` (atual) × spec §5.4:

| Campo spec | Atual? |
|---|---|
| `exame_id` | ✅ (hash) |
| `url_video` | ✅ (`url`) |
| `hash_video` | 🟡 (geramos, mas não validamos contra um esperado) |
| `duracao_video_seg` | ✅ (depois da análise) |
| `unidade` | ❌ **NÃO captura** |
| `data_hora_exame` | 🟡 (deriva de S3 path se não vier) |
| `tipo_exame` | ❌ **NÃO captura** |
| `candidato.cpf_mascarado` | ❌ **NÃO captura** |
| `candidato.nome` | 🟡 (opcional, raramente vem) |
| `candidato.categoria_pretendida` | 🟡 (deriva de S3 path/upload metadata) |
| `examinador.matricula` | ❌ **NÃO captura** |
| `examinador.eh_preposto` | ❌ **NÃO captura** |
| `resultado_oficial.decisao` | ✅ (`resultado_exame=A/R/N`) |
| `resultado_oficial.pontuacao` | ❌ **NÃO captura** (só A/R/N, não a soma) |
| `resultado_oficial.houve_interrupcao` | ❌ **NÃO captura** |
| `resultado_oficial.infracoes` (lista de Art. CTB) | ❌ **NÃO captura como lista discreta** — só temos `training_annotations` (não é equivalente) |
| `trajeto_definido` | ❌ **NÃO captura** |
| `telemetria/GPS` | ❌ **NÃO captura** |
| Polling/cursor incremental | ❌ Não fazemos polling — recebemos push via init_upload |

> **Implicação:** sem `resultado_oficial.infracoes` como lista discreta, é impossível detectar as 5 divergências da spec §9 (precisamos saber QUAIS Art. CTB o examinador apontou).

### §6 Motor de Detecção — Eventos Brutos

Hoje VALBOT pula essa camada — Gemini retorna direto `infracoes_detectadas` já enquadradas em Art. CTB. **Para atender a spec precisaria:**

- Prompt do Gemini retornar **2 listas**: `eventos_detectados` (brutos) + `enquadramentos` (após Matriz)
- OU separar em 2 chamadas Gemini (detecção pura → enquadramento normativo) — mais caro, mas mais auditável

### §7 Motor Normativo

Hoje fundido no mesmo prompt do Gemini. Pra ter "Motor Normativo" puro precisaria:
- Modelo de Matriz em DB (`exam_rules` table com schema da §4.2)
- Engine de regras Python que recebe lista de eventos do Detecção e consulta Matriz
- API pra evoluir Matriz sem retreinar IA (CRUD de regras versionado)

### §8 Motor de Pontuação

✅ **Atende** (já está no prompt MBEDV + Gemini retorna `pontuacao_total` e `aprovado`).

### §9 Motor de Comparação — 5 Tipos de Divergência

| Tipo spec | Status |
|---|---|
| 1. **Resultado** (aprova × reprova) | ✅ Atende — `r.diverge` no FE |
| 2. **Pontuação** (mesmo resultado, pts diferentes) | ❌ — não capturamos pontuação oficial pra comparar |
| 3. **Infração** (mesmo resultado, qtd infrações diferente) | ❌ — não capturamos lista oficial |
| 4. **Enquadramento** (mesma conduta, Art. CTB diferente) | ❌ — não capturamos quais Art. o examinador apontou |
| 5. **Evidência insuficiente** | 🟡 Parcial — temos `audio_quality_flag` mas não unificado como tipo de divergência |

### §10 Comitê de IA

❌ **Não existe.** Hoje a saída do Gemini vai direto pro humano (Comentários de Revisores). Spec exige uma segunda camada de IA que aprofunda divergências ANTES de chegar ao humano.

### §11 Fluxo 4 Níveis

| Nível spec | Status |
|---|---|
| 1. IA Principal | ✅ Gemini |
| 2. Comitê de IA | ❌ |
| 3. Auditor Humano | 🟡 Comentários de Revisores (genérico, não estruturado como "Auditor com OS") |
| 4. Supervisor | ❌ |

### §12 Gestão de OS

❌ **Não temos.** Hoje não há conceito de "Ordem de Serviço" — exame é objeto direto. Sem OS, não há ciclo de vida `Criada → Aguardando Auditor → Em Análise → Concluída → Aguardando Supervisor → Decisão Final`.

### §13 Portais Auditor/Supervisor

❌ **Não temos** os portais dedicados. Frontend atual tem:
- Fila Operacional (genérica)
- Tela Análise do Exame (genérica)
- Comentários humanos (sem fluxo OS)

Spec exige portais separados com filtros por OS, formulário de parecer, indicadores de qualidade do próprio Auditor/Supervisor.

### §14 Laudo Explicável

| Bloco spec | Status |
|---|---|
| Identificação | ✅ |
| Candidato | 🟡 (parcial) |
| Examinador | 🟡 (só nome, sem matrícula/preposto) |
| Resultado Oficial | 🟡 (só A/R, sem pontuação/infrações) |
| Resultado Calculado | ✅ |
| Análise Detalhada (por infração: art_ctb, ficha_mbedv, timestamp, evidência, confiança) | 🟡 (temos em `result.json`, falta no PDF visual) |
| Divergência (tipo) | 🟡 (só tipo 1) |
| Comitê de IA | ❌ |
| Auditor + Supervisor | ❌ |
| Eventos do Examinador (comentários proibidos) | ❌ |
| Versões (Matriz, modelo) | 🟡 (engine_preset sim, Matriz não) |
| Trilha de Auditoria | 🟡 (exam_events) |
| Integridade (hash relatório) | ❌ |

### §15 Dashboard Regulatório

| Indicador spec | Status |
|---|---|
| Total exames recebidos/processados | ✅ Kanban + contadores |
| Tempo médio análise IA | 🟡 (no DB mas não dashboard visual) |
| Concordância de **resultado** IA × Oficial | ✅ Card "Divergências VALBOT × Avaliador" |
| Concordância de **pontuação** | ❌ |
| Concordância de **enquadramento CTB** | ❌ |
| Infrações mais detectadas (top) | ❌ |
| Divergência por unidade | ❌ (não temos unidade no payload) |
| Divergência por examinador | ❌ (não temos matrícula) |
| Divergência por categoria CNH | 🟡 (temos chip filtro, falta agregação) |
| Taxa de interrupção | ❌ |
| Comentários inadequados | ❌ |
| Taxa de evidência insuficiente | ❌ |

### §16 Retroalimentação

❌ **Não automatizada.** `training_annotations` ficam só pra atenção do prompt (Phase 1) — não viram dataset, não geram batch de re-treino, não atualizam Matriz.

### §17 Segurança/Compliance

| Requisito | Status |
|---|---|
| HTTPS | ✅ Caddy |
| Criptografia em repouso (vídeos) | 🟡 GCS encrypted at rest by default |
| Mascaramento CPF | ❌ (não capturamos CPF formalmente, baixo risco) |
| Logs de acesso (quem acessou o quê) | 🟡 (logs nginx + exam_events) |
| Retenção write-once 12 meses | ❌ |
| Hash do relatório | ❌ |

### §19 Requisitos Não Funcionais

| Requisito | Meta spec | Atual |
|---|---|---|
| Uptime | ≥99% | ✅ provavelmente sim, sem SLA medido |
| Tempo análise IA | ≤5 min/exame | ✅ ~30-70s Gemini |
| Throughput pico | ≥200/h | ⚠️ semáforo `MAX_CONCURRENT_DOWNLOADS=3` limita |
| Escalabilidade 100k/mês | — | ❌ VM única `e2-standard-2`, não escala horizontalmente |
| RTO/RPO | ≤4h/≤1h | ❌ não temos plano DR formal |
| Backup diário | ≥30 dias | ❌ não temos rotina |
| Versionamento Matriz | rastreável | ❌ |

---

## B. O que temos A MAIS que o spec NÃO previu

| Capacidade Valbot | Valor agregado vs spec |
|---|---|
| **Pipeline 2-fase com discovery via Vertex Flash** | Spec assume layout fixo. Nosso `discover_layout` identifica dinamicamente quem está em cada quadrante 2×2 — funciona com qualquer fabricante de DVR. Custo extra ~$0.0006/exame |
| **Prompts modulares per-câmera × per-categoria** | Spec descreve "Motor Normativo" monolítico. Nosso `compose_system_prompt` injeta CONTEXTO específico do que esperar em cada câmera (24KB direcionado vs 74KB monolítico) — modelo erra menos por excesso de contexto irrelevante |
| **GUARD anti-falso-positivo** (ex: seta Art. 196) | Spec não trata robustez contra erros sistemáticos. Phase 1 nossa adiciona instruções explícitas pro modelo desqualificar detecção quando faltam pistas auditivas — reduz falso positivo da R1020-GR-e (caso `024e83…`) |
| **Validador independente (`exam_camera_validations`)** | 2ª chamada Gemini que valida só `veredito` + `fabricante`. Funciona como ground-truth pra detectar quando o analyzer principal tá em desacordo consigo mesmo |
| **Kanban view com 4 colunas + Toggle Tabela⇄Kanban** | Spec só prevê "Lista de OS pendentes". Nosso Kanban dá visão de fluxo por necessidade humana (Em processo / Revisar / Resolvidos / Infra) — operador vê gargalos imediatamente |
| **Chips de filtros componíveis** (cards summary + chips de categoria + toggle "Só reais") | Spec descreve filtros básicos. Nosso header tem AND lógico entre múltiplos filtros com persistência em localStorage |
| **Sistema de hot-fix sem rebuild** (env var + docker compose up) | Spec assume deploy padrão. Nosso `VALBOT_USE_MODULAR_V26=1` permite ativar/desativar pipeline novo em 10s |
| **Sweep de recovery `process_pending_s3.py`** | Spec não trata recuperação de exames falhados. Nosso script reabilita 97 status=failed→queued em batch + boto3 autenticado |
| **Cache de discovery por hash** (a implementar) | Spec faz polling sem cache. Nosso plano: reusar layout de exames anteriores da mesma DVR — economiza ~$0.0006 × N |
| **Comentários do Examinador como REFERÊNCIA** | Spec só usa pra dashboard. Phase 1 nossa injeta `training_annotations` no prompt como âncoras de atenção (modelo verifica com independência, não copia) |

---

## C. Roadmap pra fechar gaps prioritários

Ordenado por **impacto regulatório**:

| Prioridade | Item | Esforço | Bloqueio? |
|---|---|---|---|
| **P0** | Capturar `resultado_oficial.pontuacao` e `resultado_oficial.infracoes` no init_upload | 1 dia BE + 1 dia integração DETRAN | ❌ Blocker pras divergências 2/3/4 da §9 |
| **P0** | Modelar Matriz Nacional em DB (`exam_rules` + `exam_rule_versions`) | 3 dias | ❌ Blocker pra §15 dashboard regulatório + retroalimentação |
| **P1** | Implementar 5 tipos de divergência (Motor de Comparação completo) | 2 dias após P0 | — |
| **P1** | Conceito de "Ordem de Serviço" + ciclo de vida (estado machine) | 4 dias | — |
| **P1** | Portais Auditor + Supervisor separados (RBAC + UIs) | 1 semana | — |
| **P2** | Comitê de IA (segunda análise antes do humano) | 1 semana | — |
| **P2** | Detecção de comentários inadequados do examinador (áudio) | 3 dias (prompt + classifier) | — |
| **P2** | Dashboard regulatório com top infrações, divergência por unidade/examinador | 4 dias após P0 | — |
| **P3** | Retroalimentação automatizada (batch mensal) | 2 semanas | — |
| **P3** | Polling API Techpark (substitui push do init_upload) | 3 dias | depende do cliente |

---

## D. Atende quando go-live?

Pela spec §18.3 (critérios go/no-go), atendemos hoje:

| Critério Go/No-Go | Atende? |
|---|---|
| Cobertura ≥95% sem falha | 🟡 Após Phase 2c estabilizar, deve atender |
| Uptime ≥99% | ✅ Provavelmente |
| Análise IA ≤duração do vídeo | ✅ Gemini é ~30-70s |
| Aderência MBEDV ≥90% | 🟡 Phase 2b traz Matriz alinhada mas falta validar em pilotagem |
| Cálculo idêntico à 1.020/2025 | ✅ Lógica prompt: `pontuacao_total ≤ 10 → aprovado` |
| Aprovação Techpark | ❌ Pendente piloto |
| Auditor/Supervisor capazes de decidir | ❌ Falta portal dedicado |
| Nenhum incidente crítico | 🟡 — |

**Veredito honesto pra apresentação:** o **núcleo de análise da IA** atende. O **fluxo operacional regulatório (OS, 4 níveis, Comitê)** não atende. Pra piloto com 6k exames/mês, podemos rodar como POC mostrando potência da IA, mas o fluxo Auditor/Supervisor precisa ser construído antes de virar produto.

---

*Documento gerado em 28/05/2026. Para atualizar: regerar deste arquivo após implementar cada item do roadmap §C.*
