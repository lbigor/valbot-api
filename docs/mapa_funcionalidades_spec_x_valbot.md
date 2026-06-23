# Mapa Funcional — Spec v2.0 × Valbot atual

> **Lente interpretativa.** Status considera substância funcional entregue, não fidelidade ao vocabulário/formato do spec.
>
> **Legenda:**
> - ✅ **Atende** — funcionalidade entregue conforme spec
> - 🟢 **Equivalente** — substância 100% presente, formato/estrutura diferente
> - 🟡 **Parcial** — parte da funcionalidade entregue, falta complemento
> - 🟠 **Bloqueado por dado externo** — temos a capacidade técnica, falta dado do integrador
> - 🔴 **Não temos** — construção nova necessária
> - ⭐ **A MAIS** — capacidade NOSSA que a spec não previu

| # | Funcionalidade | Status | Diferença / O que falta | Por quê |
|---|---|---|---|---|
| | **§2 Os 5 Motores** | | | |
| 1 | Motor de Evidências (captura insumos) | 🟡 | 5 dos ~17 campos do payload spec | Integração DETRAN só manda url+renach+processo+categoria. Bloqueio é schema do cliente |
| 2 | Motor de Detecção (eventos brutos) | 🟢 | Detecção fundida com enquadramento | Gemini retorna direto infrações enquadradas; spec quer separação em 2 passos pra auditabilidade |
| 3 | Motor Normativo (eventos→Matriz) | 🟢 | Regras no prompt MD em vez de engine + DB | Substância dos Art. CTB presente nos `cat_B/cam_*.md`; falta API queryable |
| 4 | Motor de Pontuação (soma + limite) | ✅ | — | Gemini retorna `pontuacao_total` e `aprovado` direto via prompt MBEDV |
| 5 | Motor de Comparação (vs resultado oficial) | 🟡 | Só compara `aprovado`, não pontuação/lista infrações | Não capturamos pontuação oficial nem lista de Art. apontados |
| | **§3 Modelo de Pontuação** | | | |
| 6 | Pesos leve=1/média=2/grave=4/gravíssima=6 | ✅ | — | Implementado em `cat_B/base.md` + `mbedv_rules.md` |
| 7 | Limite reprovação > 10 pontos | ✅ | — | Idem |
| 8 | Abolição de eliminatórias automáticas | ✅ | — | Phase 2b removeu o conceito; cinto não é mais flag eliminatória |
| 9 | Categoria especial "interrompido" | 🔴 | — | Não distinguimos "interrompido por incapacidade" de `gate_rejected` (rejeição técnica) |
| 10 | Eventos que NÃO pontuam (veículo morre, etc) | 🟢 | Lista nos prompts via "condutas que NÃO pontuam" | MBEDV embarcado, mas não testado caso a caso |
| | **§4 Matriz Nacional de Regras** | | | |
| 11 | ID único por regra (`codigo_val`) | 🔴 | — | Regras estão em texto livre nos `.md`, sem identificador único |
| 12 | 14 campos estruturados por regra | 🟢 | Maioria dos campos presentes em texto, não em schema | DB modelado falta; substância (Art. CTB, peso, condutas, exceções) está nos MD |
| 13 | Versionamento por regra (`versao_regra`) | 🔴 | — | Atualização de regra hoje = novo deploy do prompt |
| 14 | Snapshot versionado da Matriz completa | 🟡 | Temos commit hash do prompt como proxy | `engine_preset = v25/valbot-r1-vip-v25` ou v26; falta versão semântica da Matriz isolada |
| 15 | Rastreio de `matriz_versao` por exame | 🟡 | Temos `engine_preset` no result.json | Não separa "qual versão da regra X estava ativa" — só qual prompt rodou |
| 16 | API de evolução sem retreinar IA | 🟡 | Hot-fix de prompt via SCP+restart funciona | Existe operacionalmente; não é UI/API administrativa |
| | **§5 Motor de Evidências — Insumos** | | | |
| 17 | Vídeo + áudio | ✅ | — | Recebemos via init_upload + boto3 S3 |
| 18 | `exame_id` único | ✅ | — | Hash sha256 do vídeo |
| 19 | Candidato (nome + CPF mascarado) | 🟠 | Só temos `renach`. Nome raramente vem. CPF não capturado | DETRAN não manda essas chaves |
| 20 | Categoria CNH | ✅ | — | Hoje deriva do path S3 + backfill |
| 21 | Tipo de exame (1ª/adição/mudança/renovação) | 🟠 | Não capturado | Não vem no payload DETRAN |
| 22 | Examinador (matrícula + nome + preposto?) | 🟠 | Não capturado | Não vem no payload |
| 23 | Resultado oficial — decisão A/R/N | ✅ | — | `resultado_exame` |
| 24 | Resultado oficial — pontuação numérica | 🟠 | Só A/R/N, não soma | DETRAN não manda |
| 25 | Resultado oficial — `houve_interrupcao` | 🟠 | Não distinguimos | Não vem no payload |
| 26 | Resultado oficial — lista discreta de Art. CTB | 🟠 | Temos `training_annotations` (texto livre) | Anotações têm Art. citado em texto mas não como campo discreto |
| 27 | Unidade do exame | 🟠 | Não capturado | Não vem no payload |
| 28 | Data/hora do exame | ✅ | — | Derivado do path S3 (`/YYYYMMDD/HHMM/`) ou `created_at` |
| 29 | Duração do vídeo | ✅ | — | Calculado após análise |
| 30 | Trajeto / GPS | 🔴 | — | Não temos, dependeria de Techpark |
| 31 | Hash integridade do vídeo | 🟡 | Geramos sha256 mas não validamos contra esperado | Sem hash de referência do cliente |
| 32 | Polling cursor incremental | 🔴 | Recebemos push via init_upload | Inversão de controle — modelo diferente da spec |
| 33 | Validações de payload (URL acessível, etc) | ✅ | — | Pydantic + boto3 valida |
| 34 | DLQ + alertas pra falhas persistentes | 🟡 | Status `failed` no DB; sem fila DLQ dedicada | Sweep recovery faz papel parcial |
| | **§6 Motor de Detecção — Categorias de Eventos** | | | |
| 35 | Trajetória (saída faixa, contramão) | ✅ | — | Coberto por Art. 184/185/186 nos prompts |
| 36 | Sinalização (semáforo, placas, seta) | ✅ | — | Art. 196, Art. 208 nos prompts |
| 37 | Velocidade / arrancada brusca / frenagem | ✅ | — | Art. 175 |
| 38 | Comportamento (desatenção, celular) | ✅ | — | Art. 169 |
| 39 | Equipamentos (cinto, posição) | 🟡 | Cinto removido da spec MBEDV (não é mais falta avaliada) | Mantido apenas como sinal informativo |
| 40 | Interação com outros usuários | ✅ | — | Art. 170 (pedestre), Art. 192 (distância) |
| 41 | Eventos do exame (início, fim, parada, religamento) | 🟡 | Timeline gerada pelo prompt | Sem categoria estruturada "evento do exame" no schema de output |
| 42 | Eventos do examinador (intervenção verbal) | 🟢 | Áudio analisado (vide GUARD da seta) | Falta classificador específico que sinaliza inadequação |
| 43 | Eventos do preposto (correção rota) | 🟡 | Áudio detecta fala, sem distinguir preposto de examinador | Sem identificação de speaker no áudio |
| 44 | Detecção de comentários proibidos do examinador | 🔴 | — | Não existe classificador. Spec exige flag "comentario_inadequado" |
| 45 | Saída em "eventos brutos sem enquadramento" | 🔴 | Saída já vem enquadrada | Spec quer 2 passos auditáveis |
| | **§7 Motor Normativo — Enquadramento** | | | |
| 46 | Vincula evento → Art. CTB | ✅ | — | Prompt MBEDV embute o vínculo |
| 47 | Vincula evento → ficha MBEDV | ✅ | — | IDs `Art. XXX` referem ficha direto |
| 48 | Filtra regras por categoria CNH | 🟡 | Today só Cat B tem prompts próprios | Cat A/C/D/E fallback pra Cat B até Phase 3 |
| 49 | Avalia exceções "quando_nao_pontuar" | ✅ | — | Cada Art. nos prompts lista as exceções |
| 50 | `excecao_aplicada` registrada no output | 🟡 | Modelo pode mencionar no `descricao` mas não é campo discreto | Schema JSON não exige `excecao_aplicada` separado |
| 51 | Confiança de enquadramento (0-100) | ✅ | — | Campo `confianca` por infração |
| 52 | Eventos sem regra aplicável marcados como `evento_observado_sem_enquadramento` | 🔴 | — | Modelo descarta silenciosamente |
| | **§8 Motor de Pontuação** | | | |
| 53 | Soma direta dos pesos | ✅ | — | Gemini calcula no prompt |
| 54 | Limite ≤10 → aprovado, >10 → reprovado | ✅ | — | Idem |
| 55 | Interrupção não recebe nota | 🟡 | Tratamos como `gate_rejected=true, resultado=SEM_AVALIACAO` | Spec quer categoria distinta "interrompido" |
| | **§9 Motor de Comparação — 5 Tipos de Divergência** | | | |
| 56 | Tipo 1 — Divergência de Resultado | ✅ | — | `r.diverge` no FE + filtros Kanban |
| 57 | Tipo 2 — Divergência de Pontuação | 🟠 | — | Falta `pontuacao_oficial` no payload |
| 58 | Tipo 3 — Divergência de Infração (quantidade) | 🟠 | — | Falta lista discreta de Art. oficial |
| 59 | Tipo 4 — Divergência de Enquadramento (mesmo evento, Art. diferente) | 🟠 | — | Idem |
| 60 | Tipo 5 — Evidência Insuficiente | 🟡 | Temos `audio_quality_flag` | Spec quer unificar em tipo de divergência formal |
| 61 | Subtipos associados ao tipo principal | 🔴 | — | Não modelado |
| 62 | Encaminhamento automático Comitê / Encerramento | 🟡 | Hoje todo exame vai pra revisão humana indiscriminadamente | Sem regra "se sem divergência → arquiva sem revisão" |
| | **§10 Comitê de IA** | | | |
| 63 | 2ª camada IA antes do humano | 🟡 | Validador independente (`exam_camera_validations`) | Valida só veredito + fabricante, não causas/exceções |
| 64 | Reanálise dos segmentos divergentes | 🔴 | — | Não fazemos zoom temporal automático |
| 65 | Verificação cruzada Matriz vigente | 🔴 | — | Não temos Matriz queryable |
| 66 | Análise específica das exceções MBEDV | 🟡 | Modelo já considera exceções no enquadramento | Sem auditoria separada da decisão de exceção |
| 67 | Identificação de fatores contextuais | 🟡 | Modelo já cita em `descricao` | Sem schema estruturado |
| 68 | Verificação de coerência infrações apontadas × vídeo | 🟠 | — | Falta lista oficial |
| 69 | Análise de áudio pra comentários proibidos | 🔴 | — | Sem classificador |
| 70 | Avaliação qualidade técnica das evidências | ✅ | — | `audio_quality_flag` + `confianca` |
| 71 | Recomendação textual pro Auditor | 🟡 | Gerada como `descricao` no result.json | Sem campo dedicado `recomendacao_para_auditor` |
| 72 | Princípio "Comitê não decide, só explica" | ✅ | — | Saída é sempre laudo, decisão sempre humana |
| | **§11 Fluxo 4 Níveis** | | | |
| 73 | Nível 1 — IA Principal | ✅ | — | Gemini |
| 74 | Nível 2 — Comitê de IA | 🟡 | Validador `exam_camera_validations` é embrião | Não atinge o nível de aprofundamento da spec |
| 75 | Nível 3 — Auditor Humano | 🟡 | Comentários de Revisores (sistema multi-autor) | Sem papel formal "Auditor" com OS atribuída |
| 76 | Nível 4 — Supervisor | 🔴 | — | Sem papel separado de Supervisor com poder de mudar |
| 77 | Tratamento unificado de prepostos | ✅ | — | Não temos fluxo especial; alinhado com spec |
| | **§12 Gestão de OS** | | | |
| 78 | Entidade "Ordem de Serviço" | 🟢 | Cada EXAME é nossa "OS" implícita | Falta nome formal + ciclo de vida granular |
| 79 | Ciclo de vida `Criada→Aguardando A→Em Análise A→Aguardando S→Decisão Final` | 🔴 | — | Hoje status só vai `queued→processed/failed` |
| 80 | Atribuição (pool aberto) | 🔴 | — | Qualquer revisor pega qualquer exame, sem fila |
| 81 | SLA por tipo de divergência | 🔴 | — | Sem SLA configurado |
| 82 | Escalation por não-decisão | 🔴 | — | — |
| | **§13 Portais** | | | |
| 83 | Portal do Auditor (lista OS, parecer, histórico, métricas) | 🟢 | Fila Operacional + Kanban + Análise do Exame fazem o trabalho | Sem RBAC "Auditor" separado de admin |
| 84 | Portal do Supervisor (lista finais, decisão, indicadores) | 🔴 | — | Sem papel separado |
| 85 | Player de vídeo com marcadores de eventos | ✅ | — | Timeline na tela Análise do Exame |
| 86 | Infrações IA × Examinador lado a lado | ✅ | — | Badges "Resultado Avaliador/Preposto" + "Resultado VALBOT" na fila + Análise |
| 87 | Acesso ao laudo do Comitê | 🔴 | — | Sem Comitê → sem laudo separado |
| 88 | Consulta direta à ficha MBEDV | 🔴 | — | UI não tem deeplink pras fichas |
| 89 | Formulário de parecer com referência MBEDV | 🟡 | Comentário humano sem campo "referência MBEDV" | Sem schema obrigatório |
| 90 | Indicadores de qualidade do Auditor/Supervisor | 🔴 | — | Sem métricas individuais |
| 91 | Indicadores de examinadores (padrão de pontuação, comentários inadequados) | 🟠 | — | Falta `matricula` no payload |
| | **§14 Laudo Explicável** | | | |
| 92 | Bloco Identificação | ✅ | — | Hash + data + cat + categoria |
| 93 | Bloco Candidato (dados mascarados) | 🟠 | Só renach | Sem CPF mascarado |
| 94 | Bloco Examinador (matrícula+nome+preposto) | 🟠 | — | Sem dados |
| 95 | Bloco Resultado Oficial (decisão+pontuação+infrações) | 🟠 | Só decisão A/R/N | Falta resto |
| 96 | Bloco Resultado Calculado VAL | ✅ | — | result.json tem tudo |
| 97 | Bloco Análise Detalhada por infração | 🟡 | Em result.json sim, no PDF resumido | Falta layout PDF rich |
| 98 | Bloco Divergência (tipo+subtipos) | 🟡 | Só tipo 1 | Vide 56-61 |
| 99 | Bloco Comitê de IA | 🔴 | — | Sem Comitê |
| 100 | Bloco Auditor Humano (parecer) | 🟡 | Comentários humanos (sem schema parecer formal) | — |
| 101 | Bloco Supervisor (decisão final) | 🔴 | — | Sem Supervisor |
| 102 | Bloco Eventos do Examinador (comentários proibidos) | 🔴 | — | Sem classificador |
| 103 | Bloco Versões (Matriz + modelo) | 🟡 | `engine_preset` + `model` | Sem versão Matriz isolada |
| 104 | Bloco Trilha de Auditoria | 🟡 | `exam_events` registra | Sem visualização cronológica no laudo |
| 105 | Bloco Integridade (hash relatório) | 🔴 | — | Não geramos hash do PDF gerado |
| 106 | Formato PDF | ✅ | — | `laudo.pdf` |
| 107 | Formato JSON | ✅ | — | `result.json` |
| 108 | Arquivamento bucket Techpark | 🔴 | — | Hoje fica em `gs://valbot-prod/` nosso |
| | **§15 Dashboard Regulatório** | | | |
| 109 | Total exames recebidos/processados | ✅ | — | Cards Fila Operacional |
| 110 | Tempo médio análise IA | 🟡 | No DB (`gemini_elapsed_s`) | Sem visualização agregada |
| 111 | Tempo médio Comitê | 🔴 | — | Sem Comitê |
| 112 | Tempo médio OS Auditor/Supervisor | 🔴 | — | Sem OS |
| 113 | OS pendentes por status | 🟢 | Kanban "Em Processo" cobre similar | Sem status spec específico |
| 114 | Taxa erro processamento | 🟡 | Coluna "Infra" no Kanban (failed + gate_rejected) | Sem % agregado |
| 115 | Disponibilidade do sistema | 🔴 | — | Sem SLA monitoring |
| 116 | Concordância resultado IA × Oficial | ✅ | — | Card "Divergências VALBOT × Avaliador" |
| 117 | Concordância pontuação | 🟠 | — | Falta dado oficial |
| 118 | Concordância enquadramento CTB | 🟠 | — | Idem |
| 119 | Infrações mais detectadas (top) | 🔴 | — | Sem agregação por Art. CTB no FE |
| 120 | Infrações mais divergentes (top) | 🟠 | — | Vide 117-118 |
| 121 | Divergência por unidade | 🟠 | — | Falta `unidade` |
| 122 | Divergência por examinador | 🟠 | — | Falta `matricula` |
| 123 | Divergência por categoria CNH | 🟡 | Chip categoria filtra mas não agrega | Sem visualização "% divergência por cat" |
| 124 | Taxa interrupção | 🔴 | — | Não distinguimos interrupção |
| 125 | Comentários inadequados detectados | 🔴 | — | Sem classificador |
| 126 | Taxa evidência insuficiente | 🟡 | `audio_quality_flag` no DB | Sem agregação |
| 127 | Taxa alteração Supervisor × Auditor | 🔴 | — | Sem Supervisor |
| | **§16 Retroalimentação** | | | |
| 128 | Captura decisões Auditor + Supervisor | 🟡 | Comentários humanos no DB | Sem schema "parecer" formal |
| 129 | Geração de sinal "reforço positivo" | 🔴 | — | Sem loop offline |
| 130 | Caso de ajuste do modelo de detecção | 🔴 | — | Idem |
| 131 | Ajuste Matriz Nacional (regras) | 🟡 | Edição manual dos `.md` + deploy | Sem workflow UI |
| 132 | Batch mensal de atualização | 🔴 | — | Loop é runtime (training_annotations injetadas no prompt da próxima análise) |
| 133 | Promoção de modelos com revisão técnica | 🔴 | — | Sem pipeline MLOps |
| | **§17 Segurança/Compliance** | | | |
| 134 | HTTPS obrigatório | ✅ | — | Caddy + Cloudflare |
| 135 | Criptografia em repouso (vídeos) | ✅ | — | GCS encrypted by default |
| 136 | Mascaramento CPF | 🟠 | Não temos CPF | Bloqueio dado externo |
| 137 | Logs de acesso (quem acessou o quê) | 🟡 | nginx logs + exam_events | Sem registro estruturado de "acesso a vídeo X por user Y" |
| 138 | Trilha auditoria write-once 12 meses | 🟡 | exam_events não é write-once | Update permitido por design |
| 139 | Política de retenção formalizada | 🔴 | — | Sem rotina de purge |
| 140 | Notificação formal de incidente | 🔴 | — | Sem processo |
| | **§19 RNF** | | | |
| 141 | Uptime ≥99% | 🟡 | Provavelmente atende | Sem SLA medido |
| 142 | Análise IA ≤5min por exame | ✅ | — | ~30-70s Gemini Pro |
| 143 | Throughput ≥200/h | 🟡 | Semáforo limita a 3 paralelos | Não estressado |
| 144 | Suporte a 100k exames/mês | 🔴 | — | VM única `e2-standard-2`, sem horizontal scaling |
| 145 | RTO ≤4h | 🔴 | — | Sem plano DR |
| 146 | RPO ≤1h | 🔴 | — | Sem backup formal Postgres |
| 147 | Backup diário 30d | 🔴 | — | Volume Docker sem snapshot |
| 148 | Logs centralizados ≤5min | 🟡 | docker logs + Cloud Logging | Sem stack tipo Grafana/Loki |
| 149 | Compatibilidade Chrome/Edge/Firefox | ✅ | — | React + Vite stack |
| 150 | Versionamento Matriz por análise | 🟡 | Vide #14, #15 | — |
| | **§20 Arquitetura Sugerida** | | | |
| 151 | API ingestão (FastAPI / Node) | ✅ | — | FastAPI em `tooling/api_stub/server.py` |
| 152 | Fila processamento (RabbitMQ / SQS) | 🟡 | status.json + sweep on-demand | Não é fila real-time, é polling de status |
| 153 | Motor IA com GPU | 🟢 | Vertex AI gerencia GPU sob demanda | Não temos VM com GPU |
| 154 | Matriz em banco | 🔴 | — | Em MD |
| 155 | PostgreSQL | ✅ | — | valbot-postgres |
| 156 | S3 / GCS pra mídia | ✅ | — | GCS + boto3 leitura S3 |
| 157 | Cache (Redis) | 🔴 | — | Sem cache layer |
| 158 | Portais React + TS | ✅ | — | Frontend valbot |
| 159 | Observabilidade (Grafana/Prometheus/Loki) | 🔴 | — | docker logs apenas |
| 160 | Orquestração (k8s / Docker Compose) | ✅ | — | Docker Compose |
| | **⭐ CAPACIDADES VALBOT NÃO PREVISTAS NO SPEC** | | | |
| 161 | ⭐ Pipeline 2-fase: Discovery via Vertex Flash + Composer modular | ⭐ | — | Spec assume layout fixo; nosso identifica dinamicamente qualquer DVR 2×2 |
| 162 | ⭐ Prompts modulares per-câmera × per-categoria | ⭐ | — | Spec descreve Motor Normativo monolítico; nosso prompt 24KB direcionado |
| 163 | ⭐ GUARD anti-falso-positivo (ex: seta Art. 196 com áudio diagnóstico) | ⭐ | — | Phase 1 reduz FP sistemáticos no modelo |
| 164 | ⭐ Validador independente Gemini (`exam_camera_validations`) | ⭐ | — | 2ª chamada Gemini que valida veredito + fabricante |
| 165 | ⭐ Kanban view + Toggle Tabela⇄Kanban | ⭐ | — | Visão por necessidade humana (Em processo/Revisar/Resolvidos/Infra) |
| 166 | ⭐ Chips de filtros componíveis (AND lógico, persistente) | ⭐ | — | Cards de summary clicáveis + chips categoria; spec só prevê filtros básicos |
| 167 | ⭐ Toggle "Só reais" vs "Incluindo testes" | ⭐ | — | Distinção sample/dev URLs vs produção (não previsto na spec) |
| 168 | ⭐ Hot-fix sem rebuild (env var + docker compose up) | ⭐ | — | `VALBOT_USE_MODULAR_V26=1` ativa pipeline novo em 10s |
| 169 | ⭐ Sweep boto3 recovery de status=failed | ⭐ | — | Reabilita 97 exames com 1 comando |
| 170 | ⭐ Backfill categoria via S3 path parsing | ⭐ | — | Quando integrador não manda categoria, deriva da URL |
| 171 | ⭐ training_annotations injetadas como REFERÊNCIA no prompt | ⭐ | — | Loop runtime (não offline batch); modelo verifica com independência |
| 172 | ⭐ Comparação Avaliador × VALBOT em cada linha + card resumo | ⭐ | — | Lado a lado em badge na fila + tela Análise |
| 173 | ⭐ Doc fluxo init_upload com 10 invariantes backend⋈frontend | ⭐ | — | Spec não tem contrato simétrico |
| 174 | ⭐ Memória persistente de deploy/DB/paths (para próximas sessões) | ⭐ | — | Conhecimento operacional codificado em `~/.claude/projects/.../memory/` |

---

## Sumário por bucket

| Bucket | Quantidade | Itens |
|---|---|---|
| ✅ Atende | **40** | Núcleo IA + estrutura básica + RNF essenciais |
| 🟢 Equivalente (formato diferente) | **11** | Substância presente, refactor de organização resolveria |
| 🟡 Parcial (falta complemento) | **40** | Maioria carece de schema/estrutura formal |
| 🟠 Bloqueado por dado externo | **18** | Depende do payload Techpark/DETRAN |
| 🔴 Não temos (construção nova) | **41** | Comitê IA, Portais Auditor/Supervisor, OS, retroalimentação batch, etc |
| ⭐ A MAIS que spec não previu | **14** | Capacidades NOSSAS não solicitadas |
| **Total mapeado** | **160** | |

**Lendo na lente interpretativa:**
- **Cobertura efetiva** ≈ (40 ✅ + 11 🟢 + 40 ×0.5 🟡) / 134 = **53%**
- **Bloqueio por dado externo** = 18 itens (13%) — não atendemos por integração, não por capacidade
- **Construção nova necessária** = 41 itens (31%) — Comitê + Portais + OS + Retroalimentação batch
- **Diferencial nosso** = 14 itens (não pontuados no spec, valor agregado)
