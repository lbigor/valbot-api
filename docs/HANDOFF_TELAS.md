# Valbot — Handoff das Telas (Frontend)

> Documento para **recriar/iterar o frontend no claude.ai/design**. Catálogo de todas as telas com layout visual, dados, contratos de API, estados e gotchas. Gerado em 2026-06-15.

## Como usar este handoff

- **Repositório:** `lbigor/valbot`, branch **`v2`** (default) — também espelhada em `main`. Frontend em `frontend/artifacts/valbot/`.
- **Stack:** React 19 + Vite + **wouter** (rotas) + **Tailwind** + Recharts (gráficos) + lucide-react (ícones) + @tanstack/react-query (dados). Backend stub: `tooling/api_stub/server.py` (FastAPI) + Postgres.
- **Fidelidade visual:** o tema "vivo" hoje é um **dark "cyber/navy"** hardcoded no shell (ver Design System). Há um design-system de tokens (`design-tokens.css`) tri-tema que o shell **ainda não consome** — para recriar fiel ao que está em produção, parta da **paleta hardcoded**.
- **Acesso (papéis):** `auditor` vê só a Fila; `admin` vê tudo; `supervisor` vê o Painel do Supervisor. `is_admin = role in ("admin","auditor")`.

## Matriz de telas

| Tela | Rota | Acesso | Função |
|---|---|---|---|
| Login | `/admin` (raiz sem sessão) | público | Entrada com email+senha |
| Fila do Auditor | `/fila-auditor` | auditor + admin | Revisão humana do exame (player+timeline+laudo) |
| Dashboard | `/dashboard` | admin | Painel executivo (KPIs, gráficos) |
| Regras | `/regras` | admin | Rubrica CTB/MBEDV + parâmetros do VLM |
| Custos | `/custos` | admin | Gasto de IA por período (cobrança) |
| Supervisor | `/supervisor` | supervisor + admin | Kanban de decisão final (Homologar/Reformar) |
| Usuários | `/admin/usuarios` | admin | CRUD de contas |
| Relatórios | `/relatorios` | admin | Resultado oficial × calculado + laudo §14.2 |
| Medição | `/medicao` | admin | Assistidos × resultados, concordância |
| Agendamento | `/agendamento` | admin | Scheduler de batch Gemini (cron) |

---

## Design System

**Tema:** O shell real (`AppLayout.tsx`, `AdminLogin.tsx`) usa um tema dark "cyber/navy" hardcoded em Tailwind (fundo `#060D1A`, marca ciano `#06B6D4`). O `design-tokens.css` define um sistema tri-tema (claro/grafite/cobalto, marca índigo `#4338CA`) ainda **não fiado no shell** — é a fundação teórica. **Para fidelidade ao que roda hoje, use a paleta hardcoded abaixo.**

**Cores — Tema APLICADO (hardcoded):**

| Uso | Hex |
|---|---|
| Fundo app / conteúdo | `#060D1A` |
| Fundo login (mais escuro) | `#040814` |
| Sidebar / header / cards | `#0B1120` |
| Superfície (inputs, hover) | `#111827` |
| Bordas | `#1F2937` |
| Marca / acento (ciano) | `#06B6D4` |
| Acento secundário (azul) | `#1D4ED8` |
| Texto principal | `#F9FAFB` |
| Texto muted | `#9CA3AF` |
| Sucesso / VLM ativo | `#10B981` |
| Aviso / badge fila / Crown | `#F59E0B` |
| Erro / alertas / logout hover | `#EF4444` |
| Gradiente login (botão/ícone) | `from-blue-600 to-cyan-500` |

**Severidades do painel** (eliminatória/grave/média/leve): `#FF3B30` / `#FF9500` / `#007AFF` / `#8E8E93`.

**Tipografia:**
- Sans: **Hanken Grotesk** (fallback ui-sans-serif, system-ui). Pesos 500–700. Tracking negativo em títulos; uppercase + tracking largo em labels.
- Mono: **JetBrains Mono** (números, RENACH, timecodes, chip VLM).

**Raios/sombras:** `rounded-md` (nav/inputs), `rounded-xl` (cards/botões login), `rounded-full` (badges). Sombras `shadow-sm`/`shadow-lg`; login com `shadow-2xl` + glow ciano. Sidebar 240px fixa; conteúdo `max-width ~1560px`.

## Shell (AppLayout)

**Estrutura:** flex full-screen. Sidebar fixa **240px** (`#0B1120`, borda `#1F2937`): logo (64px) → nav scrollável → chip status VLM → rodapé usuário. Conteúdo à direita: **header 56px** sticky + `<main>` scrollável (`#060D1A`, padding 24px).

**Itens do menu (`SIDEBAR_ITEMS`)** — filtrados por `isAdmin || !adminOnly`:

| Rótulo | Rota | Ícone (lucide) | Acesso |
|---|---|---|---|
| Fila do Auditor | `/fila-auditor` | `ListFilter` | todos |
| Dashboard | `/dashboard` | `LayoutDashboard` | admin |
| Regras | `/regras` | `BookOpen` | admin |
| Custos | `/custos` | `DollarSign` | admin |
| Supervisor | `/supervisor` | `ShieldCheck` | admin |
| Usuários | `/admin/usuarios` | `Users` | admin |
| Relatórios | `/relatorios` | `FileText` | admin |
| Medição | `/medicao` | `Activity` | admin |
| Agendamento | `/agendamento` | `Clock` | admin |

Item ativo: `location.startsWith(item.path)` → fundo `#1D4ED8/10`, texto+ícone ciano, borda `#06B6D4/20`.

**Logo da sidebar:** "VALBOT" bold 2xl ciano + "Auditoria Inteligente" uppercase 10px muted (texto puro).

**Badge da fila:** pílula âmbar `#F59E0B` com `filaCount` (vídeos `status !== "processed"`, poll 30s `/api/videos`).

**Chip VLM:** mono 10px — verde "VLM ativo (Haiku)" ou cinza "VLM off · só heurística" (`/api/vlm-status`, poll 60s).

**Header (56px):** breadcrumb "VALBOT › {página}" (esq) + busca (`Search`, 256px) + sino `Bell` com badge vermelho `alertasCount` (dir).

**Rodapé usuário:** avatar (iniciais do email) + email + papel ("Admin" com `Crown` âmbar / "Revisor") + botão `LogOut` (hover vermelho) → `logout()`.

## Login (AdminLogin)

**Rota:** `/admin` (e tela raiz quando sem sessão). Com sessão, App redireciona para `/dashboard` (admin/auditor) ou `/fila-auditor`.

**Layout:** full-screen centralizado, fundo `#040814`. Decoração: 2 "neon glows" radiais (azul top-left, ciano bottom-right) + grade cyber (linhas ciano 40×40px, opacidade 0.03). Card central `GlassCard` (max-w-md, `bg-slate-900/40`, `backdrop-blur-2xl`, `shadow-2xl`, linha-glow ciano no topo). Branding: ícone `ShieldCheck` em quadrado gradiente azul→ciano; título **"Acesse o VALBOT"**; subtítulo "Acesso seguro — VALBOT" com ícone `Cpu`. Rodapé: "Segurança GOV.BR • Termos de Uso".

**Campos:**
- Email (`type=email`, ícone `Mail`, placeholder `nome@valbot.ai`).
- Senha (ícone `Lock`, toggle `Eye`/`EyeOff`).
- Inputs `h-11`, `bg-slate-950/65`, `rounded-xl`, foco ring ciano.
- Botão "Entrar" full-width gradiente azul→ciano (ícone `ArrowRight`; loading `Loader2`); desabilitado se vazio/carregando.
- Banner de erro vermelho (`AlertCircle`) com a mensagem.

**Contrato:** `POST /api/auth/login {email, password}` → `{email, role, is_admin}`. Sucesso seta sessão (cookie httpOnly) e redireciona; falha mostra o banner.

---

## Telas — detalhe

### Dashboard — `/dashboard`
**Acesso:** admin / auditor.
**Propósito:** Painel executivo em tempo real do pipeline — volume, severidade, performance e casos críticos num só olhar.
**Layout:** fundo escuro `#060D1A` com 3 "ambient glows" radiais (cyan/azul/esmeralda). Coluna única empilhada:
- **Header:** eyebrow "Operações · Tempo real" + título "Painel executivo"; à direita pulso verde animado + "Pipeline ativo · atualiza a cada 15s".
- **Grade de KPIs** 3×2 (6 cards glass, ícone em chip colorido). "Casos críticos" tem variante crítica (borda esquerda vermelha em gradiente).
- **Gráficos** (3 col): AreaChart "Tendência semanal" (col-span 2: áreas Recebidos azul + Processados cyan, linha Com indício âmbar) + donut PieChart "Distribuição por severidade" (total no centro, legenda 2-col).
- **Inferior** (2 col): BarChart horizontal "Volume por unidade" + tabela "Casos críticos · SLA ameaçado" (Top 5, link "Ver todos →").

**Elementos:** 6 KpiCards; AreaChart+Line; donut com total central; BarChart horizontal gradiente; tabela prioritários com Badge de score por faixa (≥90 vermelho, ≥80 laranja, senão âmbar).
**Dados:** `totals` (`recebidos_hoje`, `processados`, `indicio`, `criticos`, `tempo_medio`, `sla` + cada `*_sub`); `weekly[]` (`name`, `recebidos`, `processados`, `indicio`); `severity[]` (`name`, `value`, `color`); `units[]` (`name`, `value`); `priority_cases[]` (`id`, `name`, `unit`, `score`, `sev`, `sla`).
**Contrato:** `GET /api/dashboard/kpis?demo=<bool>` → `{ weekly[], severity[], units[], priority_cases[], totals{}, insights[] }`. Lê `unit ?? units` e `priority ?? priority_cases`. `demo` aceito mas ignorado.
**Estados:** sem `data` → **MOCK fallback** `MOCK_DASHBOARD_KPIS` (`kpis = data ?? MOCK_DASHBOARD_KPIS`); ausentes em `totals` viram "—"; refetch 15s. Backend nunca 500 (DB off → estrutura zerada).
**Observações:** usa Tailwind + GlassCard/shadcn. `insights[]` vem no payload mas não é renderizado hoje. ⚠️ Em produção o endpoint `/api/dashboard/kpis` ainda não está deployado → a tela está em MOCK.

### Custos — `/custos`
**Acesso:** admin / auditor.
**Propósito:** Gasto de IA (vídeo/tokens) por período — base para cobrança.
**Layout:** container centralizado (max 1200px). Usa **inline styles + CSS vars** (`--panel`, `--line`, `--muted`, `--accent`). Título "Custos de Processamento" + subtítulo "...últimos {dias} dias". Grade de 4 KPIs. Card "Custo por dia" (AreaChart 220px). 2 cards lado a lado: tabelas "Por unidade" e "Por categoria".
**Elementos:** 4 KPIs (DollarSign/FileCheck/TrendingUp/Cpu); AreaChart diário; 2 tabelas (Rótulo/Custo/Exames). Período fixo 30 dias no código (sem filtro na UI).
**Dados:** `custo_total_usd`, `num_exames_cobrados`, `custo_medio_por_exame_usd`, `tokens_in_total`/`tokens_out_total`; `serie_diaria[]` (`dia`, `custo_usd`, `num_exames`); `por_unidade[]`/`por_categoria[]` (`rotulo`, `custo_usd`, `num_exames`).
**Contrato:** `GET /api/dashboard/custos?dias=30` → `{ periodo_dias, custo_total_usd, num_exames_cobrados, custo_medio_por_exame_usd, tokens_in_total, tokens_out_total, serie_diaria[], por_unidade[], por_categoria[] }`.
**Estados:** loading "Carregando…"; vazio "Sem dados no período."; sem branch de erro; sem mock.
**Observações:** estética mais "crua" (inline styles + CSS vars globais). Período não configurável pela UI hoje.

### Regras — `/regras`
**Acesso:** admin / auditor (edição de parâmetros só admin; não-admin vê "Somente leitura").
**Propósito:** Manual normativo CONTRAN — infrações com gravidade/pontos e, por infração, edição dos parâmetros mensuráveis + prompt-hint do VLM.
**Layout:** glass/Tailwind (glows cyan/azul/violeta). Header (eyebrow "Manual normativo · CONTRAN" + título + resumo "{N} infrações · limite {pts}"). **Split master-detail:**
- **Esquerda (58%):** busca + Select de versão da rubrica; contagem por gravidade (bolinhas) + "Filtradas: N"; tabela (Código/Descrição/Severidade/Pontos/Ativo) header sticky, linha selecionada com barra cyan, Switch "Ativo" disabled.
- **Direita:** detalhe com glow por severidade. Header (badges id/severidade/label/Ativo) + descrição; seções: **Definição** (4 ParamStat: Pontos/Gravidade/Câmeras/Base Legal), **Condição de disparo** (pseudo-código IF/AND/THEN colorido), **Parâmetros mensuráveis** (sliders + textarea de prompt hint + "Adicionar parâmetro" / "Sugerir via IA" / "Salvar"), **Base legal**.

**Dados:** `infracoes[]` (`id` ex "R1020-G-a", `descricao`, `gravidade`, `gravidade_label`, `pontos`, `cameras[]`, `base_legal`, `parametros{}`, `vlm_prompt_hint`). Severidade: eliminatoria/gravissima→Crítico, grave→Alto, media→Médio, demais→Baixo.
**Contratos:**
- `GET /api/rubricas/{slug}` → `{ slug, nome, limite_pontuacao, infracoes[], total_infracoes, contagem_por_gravidade }`.
- `PUT /v2/rubricas/{slug}/infracao/{id}/parametros` body `{ parametros, vlm_prompt_hint }`.
- `POST /v2/rubricas/{slug}/infracao/{id}/suggest-params` → `{ suggestion: { parametros, vlm_prompt_hint } }` (IA Qwen, 30s–1min).
**Estados:** loading "Carregando rubrica…"; erro "Falha ao carregar rubrica."; filtro vazio "Nenhuma infração corresponde à busca."; detalhe vazio "Selecione uma infração à esquerda."
**Observações:** mutações usam prefixo **`/v2/`** (não `/api/`). Switch "Ativo" é visual (sempre on, disabled). Selects de rubrica: `789/2020`, `1020/2025`.

---

### Relatórios (Relatório de resultado) — `/relatorios`
**Acesso:** admin.
**Propósito:** Confronta o resultado oficial (DETRAN) × o calculado pelo Val, com filtros e laudo §14.2.
**Layout:** conteúdo único (max 1320px). Título + subtítulo dinâmico; painel de filtros horizontal; barra de resumo + ações; tabela (card scroll, header sticky); paginação no rodapé. Modal de laudo centralizado (até 920px, 88vh).
**Elementos:**
- Filtros: Período (7/15/30/60/90), Unidade (input), Examinador (input), Resultado (Todos/Apto/Reprovado/Não realizado), Categoria (A/B/AB/C/D/E), botão "Aplicar".
- Resumo: total + página; contador de divergências (âmbar); selecionados.
- Ações: "PDF consolidado" (FileStack, exige seleção), "Exportar CSV" (Download).
- Tabela: checkbox por linha + selecionar todos; linhas divergentes realçadas em âmbar; botões "Ver laudo" (modal) e "PDF" (nova aba).
- **Modal de laudo:** header nome/RENACH/hash/fonte; **toggle "JSON ↔ Formatado"** (JSON cru de retorno OU os 14 blocos renderizados); botão PDF; fechar. Render genérica: objeto→tabela rótulo/valor, lista→tabelas empilhadas, escalar→texto.
- Paginação: Anterior/Próxima, "Página X de Y · N exame(s)", select por página (25/50/100/200).
**Dados (colunas):** RENACH, Candidato, Data, Unidade, Examinador, Cat., Oficial (badge+pontuação), Val (badge+pontuação), Divergência (tag âmbar `tipo_divergencia` ou "OK" verde), Ações.
**Contratos:**
- `GET /api/relatorios/resultados?dias=&unidade=&examinador=&resultado=&categoria=&page=&page_size=` → `{ count, total, page, page_size, pages, items[], filtros, source }`. Item: `hash, candidato_nome, candidato(cpf mascarado), renach, unidade, examinador, categoria, status, resultado, resultado_exame, aprovado, pontuacao_total, num_infracoes, cost_usd, duration_s, created_at, updated_at, laudo_enviado_em, laudo_envio_status`.
- `GET /api/exams/{hash}/laudo-json` → §14.2: `{ exame_hash, laudo_versao, fonte, blocos:{...14 chaves...} }`. Chaves: `1_identificacao, 2_candidato, 3_examinador, 4_resultado_oficial, 5_resultado_calculado, 6_cobertura, 7_analise_detalhada[], 8_divergencia, 9_comite_ia, 10_parecer_auditor, 11_decisao_supervisor, 12_eventos_os[], 13_envio_unidade_gestora, 14_integridade`.
- `GET /api/exams/{hash}/laudo-pdf` → PDF (ou HTML fallback se WeasyPrint ausente).
- `GET /api/relatorios/consolidado?hashes=h1,h2` → PDF multi-página (até 100).
- `GET /api/relatorios/export.csv?...` → CSV.
**Estados:** loading; erro "Não foi possível carregar os resultados."; vazio "Nenhum exame no período/filtros."; modal com loading/erro próprios.
**Observações:** o laudo PDF é gerado **a partir do JSON** dos 14 blocos. "Ver laudo" mostra esse JSON (toggle cru/formatado). Paginação via `page`/`page_size`/`total`/`pages`.

### Usuários (Cadastro de usuário) — `/admin/usuarios`
**Acesso:** admin.
**Propósito:** CRUD de contas (admin/auditor/supervisor): criar, editar papel, revogar/reativar, resetar senha.
**Layout:** conteúdo único (max 1200px). Header título + botão "Criar usuário" (UserPlus). Toast de feedback. Card com a tabela. 3 modais (criação, edição de papel, senha temporária).
**Elementos:**
- "Criar usuário" → modal Email + Papel (select, default auditor) + Senha (mín. 6); validação inline.
- Ações por linha: Editar papel (Pencil), Reset senha (KeyRound → modal de senha temp), Revogar (Ban vermelho) / Reativar (RotateCcw verde).
- Modal senha temp: senha em `<code>` mono + botão copiar; aviso "não será exibida novamente".
- Badges: RoleBadge (admin com ShieldCheck) + StatusBadge (Ativo/Revogado).
**Dados (colunas):** Email, Papel, Criado em, Último login, Status, Ações.
**Contratos:**
- `GET /api/admin/users` → `{ count, items[], source }`. Item: `{ id, email, role, created_at, last_login_at, revoked_at }`.
- `POST /api/admin/users` `{ email, role, password }`.
- `PATCH /api/admin/users/{id}` `{ role?, revoked? }` (editar papel + revogar/reativar).
- `DELETE /api/admin/users/{id}` (soft-delete; idempotente — definido mas hoje a revogação usa PATCH).
- `POST /api/admin/users/{id}/reset-password` → senha temporária (1x).
**Estados:** loading; erro "Não foi possível carregar os usuários."; vazio "Nenhum usuário cadastrado."; botões com "Criando…"/"Salvando…".
**Observações:** ⚠️ contrato reset-password: frontend espera `temp_password`, backend devolve `senha_temporaria` — alinhar. admin_users é separado da tabela `users` (login).

### Medição (assistidos × resultados) — `/medicao`
**Acesso:** admin.
**Propósito:** Produtividade/qualidade da auditoria — exames assistidos × resultados e concordância auditor × IA, por auditor e no tempo.
**Layout:** header + filtros (Auditor, Período) à direita; faixa de 4 KPIs; 3 cards: barras "Por auditor", linha "Série temporal", tabela "Detalhe por auditor". Recharts.
**Elementos:** filtros Auditor (select) + Período (7/30/90/180); 4 KPIs (Eye/Gauge/CheckCircle2/Scale); BarChart 3 séries (Assistidos/Aprovados verde/Reprovados vermelho); LineChart (Assistidos × Divergências âmbar); tabela detalhe.
**Dados:** `por_auditor[]` (`auditor`, `exames_assistidos`, `pct_assistido_medio`, `aprovados`, `reprovados`, `concordancia_ia_pct`, `tempo_medio_s`); `totais{}`; série diária.
**Contrato:** `GET /api/dashboard/auditor-metrics?auditor=&dias=` → `{ periodo_dias, filtro_auditor, por_auditor[], serie_diaria[], totais{}, source }`. (Alimentado por `POST /api/telemetria` nas sessões do Auditor.)
**Estados:** loading; vazio por card "Sem dados no período."; totais com fallback zero.
**Observações:** ⚠️ frontend lê `d.serie` mas backend manda `serie_diaria` — alinhar (gráfico de linha pode vir vazio). Telemetria ainda zerada até o Auditor gerar uso.

### Agendamento (scheduler batch Gemini) — `/agendamento`
**Acesso:** admin.
**Propósito:** Configura a cron que dispara o envio de vídeos pendentes ao Gemini em lote; disparo manual; histórico de execuções.
**Layout:** título + subtítulo; toast; grid 2 col: esquerda card "Configuração do batch" (form + toggle Ativo/Inativo), direita 2 cards ("Próxima execução", "Resumo"). Abaixo card full-width "Histórico de execuções" (tabela + "Atualizar").
**Elementos:**
- Toggle Ativo/Inativo; campo Nome.
- Frequência: segmented (Diário / A cada N horas / Semanal / Expressão cron) com campo condicional (`time`, number 1-23, ou texto cron) + preview "cron resultante".
- Vídeos por batch (number), Retry (number), Escopo (Pendentes queued / Reprocessar failed).
- Ações: "Salvar configuração" (Save) + "Disparar agora" (Zap, exige job salvo).
- Cards: "Próxima execução" (Calendar) + "Resumo" (Escopo/Vídeos por batch/Tentativas/Status).
- Tabela runs: Início, Fim, Processados, Falhas, Custo USD, Status (badge ok/err/run).
**Contratos:**
- `GET /api/admin/cron-jobs` → `{ count, items[], runs[], source, scheduler:{disponivel, rodando, jobs_registrados} }`.
- `POST /api/admin/cron-jobs` (cria), `PATCH /api/admin/cron-jobs/{id}` (atualiza).
- `POST /api/admin/cron-jobs/{id}/trigger` → dispara batch em background.
- `GET /api/admin/cron-jobs/{id}/runs` → `[{ iniciado_em, finalizado_em, n_processados, n_falhas, custo_usd, status }]`.
**Estados:** loading; histórico vazio "Nenhuma execução registrada."; hint "Nenhum agendamento configurado ainda…"; toast ok/err.
**Observações:** ⚠️ enums frontend (`schedule_kind: diario|cada_n_horas|semanal|cron`, `escopo: queued|failed`) divergem do stub (`daily|hourly|cron|interval`, `pending|queued|failed|all`) — alinhar. Scheduler real (APScheduler) é opcional; sem ele só o trigger manual funciona.

---

### Painel do Supervisor — `/supervisor`
**Acesso:** supervisor / admin (4º e último nível: IA ValBot → Examinador → Comitê → Auditor → **Supervisor**).
**Propósito:** Recebe as OS que o Auditor já pareceu e dá a palavra final — **Homologar** (mantém o parecer) ou **Reformar** (reverte). Kanban de 3 colunas + drawer de detalhe.
**Layout (dentro do AppLayout):**
- Header: H1 "Painel do Supervisor" + subtítulo.
- **Faixa de métricas** (3 pílulas: Concordância Sup × Auditor [User], Sup × IA [Bot], SLA médio [Clock]; valores `%` ou "—").
- **Kanban** 3 colunas (header com bolinha colorida + label + contador): **Aguardando Supervisor** (accent), **Em Análise** (âmbar), **Decisão Final/Encerrada** (verde). Vazia → "Sem OS nesta coluna."
- **Card de OS:** RENACH mono + nº OS; candidato; faixa divergência (AlertTriangle + `tipo_divergencia`); comparativo Oficial × Calculado (IA) com bolinha verde/vermelho; resumo do parecer do Auditor (tag Homologar/Reformar + justificativa truncada); rodapé SLA (Clock + label, cor muda por SLA: ok/warn<4h/late).
- **Drawer de detalhe** (abre ao clicar): header RENACH+OS+tag+X; seções: **O caso** (candidato + comparação lado a lado), **Laudo do Comitê** (Scale: resultado/resumo/votos), **Parecer do Auditor** (User: decisão/resultado/justificativa), **Trilha** (timeline vertical), **Decisão do Supervisor** (ShieldCheck: toggle Homologar verde / Reformar âmbar + textarea de justificativa obrigatória). Rodapé: frase-resumo + Cancelar + "Confirmar decisão" (desabilitado até decisão + justificativa).
**Dados:** card — `renach`, `numero_os`, `candidato_nome`, `tipo_divergencia`, `resultado_oficial`, `resultado_calculado`, `parecer_auditor.{decisao,justificativa}`, `sla_due_at`. Drawer + `comite.{resultado,resumo,votos[]}`, `eventos[]`.
**Contratos:**
- `GET /api/os?status=aguardando_supervisor` → `{count, items[], source}`. Item: `os_id, numero_os, exam_hash, candidato_nome, unidade, resultado_oficial, resultado_calculado, pontuacao_oficial, pontuacao_calculada, tipo_divergencia, status, sla`. Poll 30s.
- `GET /api/os/{os_id}` → detalhe + `comparacao`, `laudo_comite{...}`, `infracoes_oficiais[]`, `infracoes_calculadas[]`, `fichas_mbedv[]`.
- `POST /api/os/{os_id}/decisao` `{decisao: "homologar"|"reformar", justificativa}`.
- `GET /api/dashboard/supervisor-metrics?dias=30` → `{ total_decisoes, homologadas, reformadas, concordancia_supervisor_auditor_pct, concordancia_supervisor_ia_pct }`.
**Estados:** "Carregando fila do supervisor…"; coluna vazia; drawer "Carregando detalhe da OS…"; erro de mutation "Falha ao registrar a decisão."; métricas "—".
**Observações:** ⚠️ drift de nomes: frontend lê `parecer_auditor`/`comite`/`sla_due_at`/`eventos`, backend mock devolve `parecer`/`laudo_comite`/`sla` e não devolve `eventos` (campos opcionais → não quebra, mas podem vir vazios). Decisão final = Homologar/Reformar; justificativa obrigatória. **TODAS as OS concluídas pelo Auditor sobem ao Supervisor** (§11).

### Fila do Auditor — `/fila-auditor` (alias `/fila`)
**Acesso:** auditor (3º nível: revisa divergências que o Comitê de IA **não** resolveu). É a tela mais complexa.
**Propósito:** O auditor assiste ao vídeo real, compara Examinador (TechPrático) × ValBot (IA Gemini), monta seu laudo e decide Aprovar/Reprovar. IA consultiva, decisão humana.
**Layout — chrome próprio (NÃO usa AppLayout):**
- **`.pchrome` (topo):** marca ValBot · "Painel do Auditor" · **exam-picker** (RENACH + status + ▾, abre fila) · seletor de tema (Grafite/Cobalto/Claro) · botão "Supervisor" (stub) · link "Dashboard".
- **`.pwork` (2 colunas):**
  - **Esquerda (`.pcenter`):** **Viewer** — barra RENACH + examinador; **StatStrip** (Divergências, Infrações IA, Status, Confiança ValBot); **player de vídeo real** (`/api/exams/{hash}/video`) com overlays: grade, safe-area, play, vinheta, **FrameAnno** (moldura pulsante na cor da gravidade + tarja TV com badges TP/ValBot/Auditor + ticker CTB); **scrubber** (playhead branco + tickmarks coloridos das infrações). **Transport:** timecode mono, ►/❚❚, "← Anterior · Exame N/M · Próximo →".
  - **Direita (`.insp`):** header "IA consultiva · decisão humana"; **Comparison** (TechPrático × ValBot: Resultado/Pontuação/Infrações, flag `≠`); **Parecer do ValBot** (+ % confiança); **Comitê de IA** (status divergência); ações Reprovar/Aprovar/"+ Lançar infração"; **laudo** (FaultRows + tag pontuação→veredito + textarea fundamentação).
- **HowItWorks** (faixa colapsável 3 passos). **Timeline** (faixa inferior full-width). Overlays: DetailModal, modal Supervisor (stub), TourOverlay (1ª visita), toast.

**Sub-componentes (`components/painel/`):**
- **DetailModal.tsx** — ficha oficial da infração/regra (CTB+gravidade+pts, comentários TP/IA/Auditor, condutas que pontuam/não pontuam, enquadramento CTB·MBEDV).
- **FaultPicker.tsx** — lançador de infração: "Início" (timecode atual), busca, sugestões da IA ≤8s, filtros por gravidade, lista de regras + RuleFicha "Lançar esta infração".
- **HowItWorks.tsx** — cartão colapsável 3 passos (Aponte / Lance / Finalize).
- **TourOverlay.tsx** — tour da 1ª visita (spotlight, ~10 passos; marca `vb-guide` no localStorage).

**Timeline (4 trilhas, label gutter 132px + lane):**
1. **Ruler** — régua de timecodes.
2. **Filmstrip** — miniaturas reais (`/thumbnails`); sem frames → gradiente CSS.
3. **Waveform** — SVG dos peaks reais (`/waveform`); sem peaks → desenho determinístico (`hashCode`).
4. **MarkerTrack ×3** — TechPrático (examinador, A/R/N), ValBot (IA, marcadores com "+" pra aceitar), Auditor (laudo, marcadores redimensionáveis). Playhead vertical mono. Toggle Ocultar/Mostrar (`tlOpen`).
- **FaultRow** (laudo): código CTB colorido + pts + remover; steppers Início/Fim (±1s), "marcar", ir-para-início/fim.

**Dados:** Mark `{code, t, len, grav, conf?, ator?}`; Rule `{code, nome, grav, pontos, desc, checks, enquad{art,ctb,mbedv}}`; QueueItem `{id, hash, renach, examinador, dur, cat, status, resultadoExame, tp{result,faults,pts}, vb{result,faults,pts,conf}}`. Parecer enviado `{decisao: "concorda"|"discorda", resultado_final: "aprovado"|"reprovado", infracoes[], justificativa, referencia_mbedv}`.
**Contratos (todos `credentials:include`):**
- `GET /api/rubricas/1020-2025` → catálogo de regras (picker).
- `GET /api/videos?only_unresolved=true` → fila; filtra `has_result && status=="processed"` e `tipo_divergencia_pos_comite != "sem_divergencia"`.
- `GET /api/analyses/hash/{hash}/result` → laudo (`scored.infracoes[]`, `summary{}`, `exame{}`, `pontos_atencao[]`, `positivos[]`).
- `GET /api/exams/{hash}/video` → stream.
- `GET /api/exams/{hash}/thumbnails?n=48` → `{frames: string[]}`.
- `GET /api/exams/{hash}/waveform?buckets=400` → `{peaks: number[]}`.
- `POST /api/exams/{hash}/parecer-auditor` → `{persisted, os_id, coerencia, source}` (nunca 500).
**Estados / degradação:** "Carregando exames…"/"Carregando vídeo e análise…"; vazio "Nenhum exame processado disponível."; erro com "Tentar de novo". **Sem ffmpeg:** thumbnails → gradiente; waveform → desenho por hashCode. **Offline ao salvar:** grava em `localStorage` (`vb-painel-pareceres-pendentes`) + toast "Salvo localmente".
**Observações / gotchas:**
- **Comitê → Fila:** só lista exames cuja divergência **não** foi resolvida pelo Comitê (`only_unresolved=true`).
- **Trava 1ª revisão:** no 1º passe não pode pular além do `watchedMax` (+2s); volta é livre; libera ao assistir ~1.5s do fim.
- **Coerência decisão × laudo:** gravíssima OU >10 pts ⇒ reprovação; se a decisão não bate com o veredito do laudo, "Confirmar" fica desabilitado com aviso.
- Atalhos: Espaço (play), ←/→ (∓1s), `[`/`]` (exame ant./próx.).
- LocalStorage: `vb-painel-v3` (UI), `vb-painel-pareceres-pendentes` (fila offline), `vb-guide` (tour).

---

## Notas para recriar no claude.ai/design

1. **Comece pelo shell + design system** (paleta hardcoded acima) — todas as telas admin vivem dentro do `AppLayout`. A Fila do Auditor é exceção (chrome próprio).
2. **Mismatches de contrato** sinalizados (⚠️) entre frontend e o stub atual valem revisão — não bloqueiam o visual, mas afetam dados reais (reset-password, Medição `serie`/`serie_diaria`, Agendamento enums, Supervisor naming).
3. **Pendências de backend em produção:** `/api/dashboard/kpis` (Dashboard ainda em mock) e ffmpeg no container (Filmstrip/Waveform degradam). Não impedem recriar o visual.
4. **Fonte de verdade do código:** `frontend/artifacts/valbot/src/` na branch `v2`. Endpoints em `tooling/api_stub/server.py`.
