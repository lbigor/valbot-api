# Relatório de Divergências — Backend × Documento (Spec Funcional v2.0)

> Documento de referência: `Val_Auditor_Exames_Especificacao_Funcional_v2 (v250526) (1).docx`
> (Valma + Techpark — CONTRAN 1.020/2025 + MBEDV).
> Estado avaliado: backend v2 (`feat/backend-rewrite-v2`) + base existente (`src/`, servidor atual).
> Data: 2026-06-14.

**Legenda de divergência**
- ✅ **Sem divergência** — backend atende ao que o documento pede.
- ⚠️ **Divergência parcial** — atende em parte; falta complemento descrito.
- 🟠 **Divergência por dado externo** — backend pronto; depende de informação que o integrador ainda não envia.
- ❌ **Divergência total** — o documento pede e o backend ainda não tem.
- ▫️ **Fora do backend** — item de frontend/processo/contrato (citado para completude).

## Placar geral

| Bloco da spec | Divergência |
|---|---|
| §2 Arquitetura — 5 motores | ✅ |
| §3 Modelo de pontuação (3.2–3.5) | ✅ |
| §4 Matriz Nacional | ✅ |
| §5 Motor de Evidências | ⚠️ / 🟠 |
| §6 Motor de Detecção | ⚠️ |
| §7 Motor Normativo | ✅ |
| §8 Motor de Pontuação | ✅ |
| §9 Motor de Comparação | ✅ / 🟠 |
| §10 Comitê de IA | ✅ |
| §11 Fluxo 4 níveis | ✅ (backend) |
| §12 Ordens de Serviço | ✅ |
| §13 Portais | ▫️ |
| §14 Laudo explicável | ⚠️ |
| §15 Dashboard | ⚠️ |
| §16 Retroalimentação | ❌ |
| §17 Segurança / LGPD | ⚠️ |
| §19 Requisitos não funcionais | ❌ |

---

## Divergências detalhadas, seção por seção

### §2 — Arquitetura funcional (5 motores) — ✅
O documento exige 5 motores especializados. **Sem divergência:** existem como módulos
distintos (`backend/engines/{evidencias,deteccao,normativo,pontuacao,comparacao}.py`),
e o `backend/pipeline.py` reproduz o diagrama §2.3 (1→2→3→4→5 → Comitê → OS; sem
divergência → encerramento). Divergência menor: o diagrama prevê *polling* da Techpark
na entrada — ver §5.3.

### §3 — Modelo de pontuação — ✅
- §3.2 pesos leve=1/média=2/grave=4/gravíssima=6 e §3.3 limite ≤10: **sem divergência**
  (`models.PESO_POR_NATUREZA`, `LIMITE_APROVACAO`; `engines/pontuacao.py`).
- §3.4 interrupção como categoria especial: **sem divergência** (`ResultadoExame.INTERROMPIDO`,
  pontuação nula).
- §3.5 eventos que não pontuam: **sem divergência** — módulo dedicado `engines/excecoes.py`
  cobre os 4 casos (veículo morre, baliza isolada, emergência/preposto, conduta induzida
  por comentário do examinador), com teste cravando "carro morre não pontua".

### §4 — Matriz Nacional de Regras — ✅
- §4.2 (14 campos por regra): **sem divergência.** `exam_rules` (migration 009) cobre todos os
  campos + `constatacao`/`informacoes_complementares`. O conteúdo canônico são as **84 fichas
  reais do MBEDV**, extraídas do PDF oficial (`configs/references/mbedv_anexo_fichas_avaliacao.pdf`,
  89 págs) para `configs/references/mbedv_fichas.json`, indexadas por **Art. CTB** (Art. 169→252).
  Loader idempotente `backend/matriz/seed_mbedv.py`; validação em `tests/backend/test_matriz_mbedv.py`.
- §4.4 versionamento: `matriz_versoes` com snapshot consolidado (`matriz-nacional-v1.0`, vigente);
  cada regra tem `versao_regra`; cada exame grava `matriz_versao`.
- §4.1 evolução sem retreinar a IA: `backend/matriz/prompt_builder.py` gera o bloco de regras do
  prompt **a partir da Matriz vigente** (com condutas que pontuam/NÃO pontuam por artigo) — mudar a
  Matriz muda o prompt, sem retreinar.
- Pendências (não bloqueiam): validação jurídica final das 84 fichas por especialista; migração
  completa dos prompts do Gemini de IDs `R1020-*` para `Art. XXX` (hoje há a ponte conservadora
  `correspondencia.py`, com 2 mapeamentos seguros); fiação do `prompt_builder` no analyzer de produção.

### §5 — Motor de Evidências — ⚠️ / 🟠
- §5.2/§5.4 (payload completo): **divergência por dado externo.** O backend aceita e persiste
  todos os campos (unidade, tipo_exame, examinador.matrícula/eh_preposto, resultado_oficial
  detalhado, infrações oficiais — migrations 010). **Divergência real:** o integrador hoje
  envia ~5 de ~17 campos. Pronto para receber; falta o envio.
- §5.3.1 *polling* a cada 5 min: ❌ **divergência total.** O modelo atual é *push* (`/api/v2/exams/ingest`),
  não *pull* com cursor. Depende do contrato da API da Techpark.
- §5.3.3 autenticação (API key + allowlist): ✅ API key com escopo já existe; allowlist de IP é infra.
- §5.5 validações: ⚠️ **parcial.** Implementadas: campos obrigatórios, duração 1–30 min, coerência
  resultado×soma-infrações, hash anti-adulteração (`evidencias.checar_hash`). **Divergência:** a
  checagem de hash só dispara quando o integrador manda o hash esperado (hoje não manda).
- §5.6 falhas: **resolvido (sem divergência).** Idempotência (`ON CONFLICT(hash)`) + **DLQ**
  (`ingest_dlq`, migration 015) + **retry com backoff** (`ingestion.resiliencia.com_retry`) +
  **alerta operacional** (webhook/log via `ingestion.resiliencia.alertar`). Resta só o `polling`
  (§5.3) e o dado oficial (🟠), ambos externos.

### §6 — Motor de Detecção — ⚠️
- §6.2 categorias de evento: **divergência parcial.** Cobertos: sinalização semafórica/PARE,
  faixa, cinto, parada. **Divergem (não detectados):** contramão, saída de faixa, velocidade,
  capacete de moto, religamento, intervenção do preposto.
- §6.2 comentários proibidos do examinador (áudio): ⚠️ o backend já modela e correlaciona o evento
  (`SaidaDeteccao.comentarios_examinador`, usado na §3.5), mas **depende do que o Gemini capta no
  áudio** — não há classificador/Whisper dedicado. Divergência parcial.
- **Camada de Compliance (não-pontuável):** sinais que NÃO somam pontos — conduta inadequada do
  examinador (§6/§10), conduta do candidato (§4-5) e condutas detectadas fora do escopo pontuável
  do MBEDV (cinto, baliza, técnicas) — são reunidos em `exam_comentarios_compliance` (migration 016),
  com API `/api/v2/compliance` (fila para a tela dedicada) e bloco próprio no laudo. Mapa auditável
  das 30 condutas em `docs/mapa_infracoes_r1020_mbedv.md`.
- §6.3 eventos brutos separados do enquadramento: **sem divergência** — `engines/deteccao.py`
  emite eventos brutos e o enquadramento é etapa à parte (Motor Normativo).

### §7 — Motor Normativo — ✅
§7.2 lógica de enquadramento (busca regra, filtra categoria CNH, aplica exceção `quando_nao_pontuar`,
marca não-enquadrados): **sem divergência** (`engines/normativo.py`). Limitação herdada da §4:
qualidade do enquadramento depende da Matriz canônica ser carregada no DB.

### §8 — Motor de Pontuação — ✅
§8.2 algoritmo (soma pesos dos enquadrados, limite, interrupção): **sem divergência** e coberto por testes.

### §9 — Motor de Comparação — ✅ / 🟠
- §9.2/§9.3 os 5 tipos + precedência: **sem divergência** (`engines/comparacao.py`, testado).
- §9.4 subtipos + encaminhamento (sem divergência → encerra; com → comitê): **sem divergência.**
- 🟠 **Divergência por dado externo:** as divergências 2 (pontuação), 3 (infração) e 4 (enquadramento)
  só se materializam quando o oficial enviar pontuação e lista de infrações. Por decisão de produto,
  a **ausência desses dados vira divergência tipo 5** (evidência insuficiente) — não passa batido.

### §10 — Comitê de IA — ✅
§10.1 princípios (nunca decide, não reverte), §10.2 reanálise focada, §10.3 laudo estruturado:
**sem divergência** — `committee/comite.py` faz a 2ª chamada ao Gemini **restrita às infrações
encontradas** e produz o laudo (`LaudoComite`) com causas, verificações, comentários do examinador
e recomendação. Divergência menor: as "verificações cruzadas com a Matriz vigente" (§10.2) dependem
da Matriz no DB (§4).

### §11 — Fluxo de decisão humana (4 níveis) — ✅ (backend)
§11.2 níveis IA → Comitê → Auditor → Supervisor, sem atalho, supervisor revisa toda divergência:
**sem divergência no backend** (`workflow/ordens.py`: `registrar_parecer` → aguardando_supervisor →
`registrar_decisao` → encerrada; trilha em `os_eventos`). §11.3 prepostos sem tratamento especial:
atendido (fluxo unificado). A camada de UI é frontend (§13).

### §12 — Gestão de OS — ✅
- **Modelo corrigido (regra de negócio):** CADA VÍDEO É UMA OS, aberta no `init_upload`. O número
  da OS é o ID gerado no upload (`numero_os`) e o **SLA começa a contar nesse instante** (`sla_inicio`).
  `backend/workflow/ordens.py` (`abrir_os_no_upload`), migration 014.
- §12.2 ciclo de vida: criada (upload) → análise → **encerrada** (sem divergência, sem humano) |
  **aguardando_auditor** → ... → encerrada (com divergência). `atualizar_pos_analise`.
- §12.3 atribuição "pool aberto": `atribuir` com guard otimista.
- §12.4 SLA: relógio desde o upload + prioridade por tipo de divergência **implementados**
  (`sla_horas_decorridas`/`sla_estourado` calculados na consulta). **Resta apenas** cravar os PRAZOS
  finais com a Techpark (provisórios: 24h auditor / 48h supervisor, configuráveis) — única parte externa.

### §13 — Portais Auditor/Supervisor — ▫️
Itens de frontend. **Backend pronto** para sustentá-los: `/api/v2/os` (lista/detalhe/atribuir/
parecer/decisão) e `/api/v2/dashboard`. A construção das telas em si está fora do backend.

### §14 — Laudo explicável e relatórios — ⚠️
- §14.2 blocos mínimos: **divergência parcial.** O laudo JSON (`reporting/laudo.py`) cobre
  identificação, candidato (CPF mascarado), examinador, resultado oficial e calculado, análise
  detalhada, divergência, comitê, eventos do examinador, versões, **hash de integridade** e
  cobertura. **Divergem (campos ainda vazios até o fluxo humano rodar):** parecer do Auditor e
  decisão do Supervisor no corpo do laudo.
- §14.3 formato PDF + JSON: ⚠️ JSON ✅; **PDF v2 é best-effort** (reusa `src/reporting`, não validado).
- §14.4 arquivamento em bucket + confirmação: ⚠️ o envio à Unidade Gestora existe (callback
  Techpratico), mas o upload em bucket com confirmação descrito na spec não foi reimplementado no v2.

### §15 — Dashboard Regulatório — ⚠️
- §15.2 operacionais e §15.3 regulatórios: **divergência parcial.** `/api/v2/dashboard` calcula
  concordância de resultado/pontuação, distribuição de divergências, top infrações, divergência
  por unidade/examinador/categoria, taxa de interrupção e de evidência insuficiente, comentários
  inadequados. **Divergência:** vários indicadores dependem de dados que hoje não chegam (unidade/
  examinador/pontuação oficial) — ficam zerados até o §5 ser destravado. Há views SQL, mas **sem UI**.

### §16 — Retroalimentação — ❌
§16.2/§16.3 (decisões humanas → evolução de modelo/Matriz, batch mensal): **divergência total no v2.**
A captação de decisões existe na base antiga (`training_annotations`, `examples.jsonl`), mas o loop
automático de re-treino/atualização da Matriz não foi construído.

### §17 — Segurança e Compliance — ⚠️
- §17.1 LGPD: ⚠️ **mascaramento de CPF agora existe** no laudo (`reporting/laudo._mascarar_cpf`) e na
  ingestão (`evidencias._mascarar_cpf`). **Divergências:** criptografia de coluna para dados pessoais
  e mascaramento em logs ainda não implementados; HTTPS/criptografia em repouso são infra (Caddy/GCS).
- §17.2 trilha de auditoria imutável (write-once 12 meses): ⚠️ **parcial** — `os_eventos` e `exam_events`
  são append-only; a política formal de retenção write-once de 12 meses não está configurada.

### §18 — Estratégia de piloto — ▫️
Processo de validação (3 camadas, go/no-go). Fora do backend; o backend fornece os dados para medir
(cobertura, tempos, divergências).

### §19 — Requisitos não funcionais — ❌ (parcial)
- Performance (análise ≤5 min): ✅ provável (Gemini ~30–70 s).
- **Throughput ≥200/h, escala 100k/mês: divergência total** — sem fila distribuída (RabbitMQ/SQS),
  processamento em threads; não escala horizontalmente.
- **RTO ≤4 h / RPO ≤1 h / backup ≥30 dias: divergência total** — sem plano de DR/backup formal.
- Versionamento da Matriz rastreável: ✅ (coluna `matriz_versao`).

### §20–§21 — Arquitetura sugerida e pendências — ▫️
Decisões técnicas (cloud, fila, GPU) e pendências com a Techpark. O backend v2 segue a stack sugerida
(Python, PostgreSQL, FastAPI). As pendências do §21 (padrão da API de polling, envio de pontuação/
infrações oficiais, SLAs, auth de usuários) são exatamente as origens das divergências 🟠 acima.

---

## Onde estão, em resumo, as divergências que importam

1. **🟠 Dado oficial que não chega** (pontuação + infrações + unidade + examinador) — destrava §9 (divergências
   2/3/4), §15 (indicadores) e parte do §14. **Maior alavanca, e externa** (depende do integrador).
   Confirmado na VM viva (`valbot-497920`): dos últimos uploads chegam só `renach`, `categoria` e
   `resultado_exame` (A/R); `examinador`/`unidade`/`external_id` vêm vazios; pontuação/infrações nem têm campo.
2. **✅ FINALIZADO nesta rodada (não dependia de terceiro):**
   - Resiliência de ingestão — DLQ + retry + alerta (§5.6).
   - OS = vídeo, número = ID do upload, relógio de SLA desde o upload (§12) — só os prazos finais são externos.
3. **❌ Fila distribuída / escala 100k/mês / DR-backup** (§19) — depende de infra (não é "agente terceiro", mas é obra de plataforma).
4. **❌ Retroalimentação automática** (§16) — re-treino batch.
5. **✅ Matriz canônica do MBEDV** (§4) — FEITO: 84 fichas reais do PDF oficial em tabela versionada
   (`exam_rules` + `matriz_versoes`), por Art. CTB, alimentando o prompt via `prompt_builder`. Resta
   só a validação jurídica por especialista e a migração dos prompts do Gemini para `Art. XXX`.
6. **⚠️ Detecção CV/áudio** ampliada (§6) e **PDF v2 / arquivamento em bucket** (§14).

> Nada aqui foi validado contra Gemini/Postgres reais nesta sessão — as conformidades ✅ dos motores
> determinísticos têm cobertura de teste; os caminhos com IA/DB precisam de teste de fumaça em homologação.
