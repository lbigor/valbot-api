# Backend v2 — Relatório de Cobertura e Divergências

> Reescrita do backend do **Val Auditor Exames** alinhada à Especificação
> Funcional v2.0 (CONTRAN 1.020/2025 + MBEDV).
> Branch: `feat/backend-rewrite-v2` · Data: 2026-06-14 · 20 testes de motor verdes.

Este documento responde a duas perguntas: **(1) o que já cobrimos hoje** e
**(2) como e onde ainda temos divergências** (lacunas vs spec), incluindo as que
dependem de dado externo que o integrador ainda não envia.

---

## 1. O que foi construído (mapa por motor da spec §2.2)

| Camada (spec) | Módulo novo | Status |
|---|---|---|
| Contratos (spec §5-§12) | `backend/models.py` | ✅ enums + pydantic de toda a plataforma |
| Config / DB / Segurança | `backend/core/{config,db,security}.py` | ✅ pool psycopg + API key + sessão HMAC |
| **Motor 1 — Evidências** (§5) | `backend/engines/evidencias.py` | ✅ normaliza 2 shapes, valida §5.5, mascara CPF |
| **Motor 2 — Detecção** (§6) | `backend/engines/deteccao.py` | ✅ eventos brutos (reusa Gemini `src/analysis`) |
| **Motor 3 — Normativo** (§7) | `backend/engines/normativo.py` | ✅ Matriz Nacional (DB + seed taxonomia), enquadramento |
| Exceções §3.5 | `backend/engines/excecoes.py` | ✅ regra DURA (carro morre, baliza, indução) |
| **Motor 4 — Pontuação** (§8) | `backend/engines/pontuacao.py` | ✅ pesos 1/2/4/6, limite ≤10, interrupção |
| **Motor 5 — Comparação** (§9) | `backend/engines/comparacao.py` | ✅ 5 divergências + subtipos + dados ausentes |
| **Comitê de IA** (§10) | `backend/committee/comite.py` | ✅ 2ª passada Gemini focada nas infrações achadas |
| **OS + 4 níveis** (§11-§12) | `backend/workflow/ordens.py` | ✅ ciclo de vida, Auditor→Supervisor, trilha |
| **Laudo explicável** (§14) | `backend/reporting/laudo.py` | ✅ JSON §14.2 + cobertura + hash integridade |
| **Dashboard** (§15) | `backend/dashboard/metrics.py` | ✅ indicadores operacionais + regulatórios |
| Persistência | `backend/persistence.py` | ✅ grava cada etapa (auditabilidade) |
| Orquestração | `backend/pipeline.py` | ✅ 1→2→3→4→5 → Comitê → OS → laudo |
| API HTTP | `backend/api/`, `backend/app.py` | ✅ 9 rotas `/api/v2/*` |
| Schema | `migrations/009`–`013` | ✅ matriz, resultado oficial, eventos, divergência, comitê, OS |
| Testes | `tests/backend/` | ✅ 20 passando (motores + pipeline e2e) |

### Regras duras que ficaram cravadas no código (não só no prompt)

- **Carro que morre NÃO pontua** (§3.5). R1020-M-c só pontua com prova de
  "sem justa razão"; o default protege o candidato. Fonte única em
  `excecoes.veiculo_morreu`, testado em `test_carro_morreu_nao_pontua_por_padrao`.
- **Baliza isolada** não é eliminatória; **emergência/preposto** e **comando
  autorizado** do examinador são exceções; **conduta induzida por comentário
  inadequado do examinador** não pontua (correlação no áudio).
- **Dados oficiais ausentes nunca viram "sem divergência"** — viram divergência
  por evidência insuficiente (tipo 5) e vão para o humano. Testado em
  `test_dados_oficiais_ausentes_viram_divergencia`.

---

## 2. Cobertura vs spec — antes → agora

| Item | Antes (28/05) | Agora (backend v2) |
|---|---|---|
| 5 motores separados | 🟡 fundidos no analyzer | ✅ módulos distintos e testáveis |
| Matriz Nacional versionada | 🔴 só prompt `.md` | ✅ `exam_rules` + `matriz_versoes` (fallback taxonomia) |
| 5 tipos de divergência | 🟡 1 de 5 | ✅ 5 de 5 (2/3/4 condicionados ao dado oficial) |
| Categoria "interrompido" | 🔴 | ✅ `ResultadoExame.INTERROMPIDO` no Motor de Pontuação |
| Eventos que não pontuam (§3.5) | 🟡 só no prompt | ✅ módulo `excecoes` aplicado no Normativo |
| Comitê de IA | 🔴 | ✅ 2ª chamada Gemini focada + fallback determinístico |
| OS + fluxo 4 níveis | 🔴 | ✅ tabelas + máquina de estados + API |
| Laudo JSON + hash integridade | 🔴 (só PDF) | ✅ JSON §14.2 com `hash_relatorio` |
| Dashboard regulatório (API) | 🟡 views sem endpoint | ✅ `/api/v2/dashboard` (operacional + regulatório) |
| Resultado oficial detalhado | 🔴 só A/R/N | ✅ pontuação + infrações oficiais (quando enviadas) |

---

## 3. Onde AINDA temos divergência / lacuna (e por quê)

| Lacuna | Natureza | Caminho |
|---|---|---|
| **Pontuação e infrações oficiais** quase nunca chegam | 🟠 bloqueio externo | Backend já aceita e persiste (migrations 010); falta o integrador enviar. Enquanto não vier, todo exame cai em divergência tipo 5 (por design — pedido do produto). |
| **Áudio/Whisper dedicado** para comentários do examinador | 🟡 parcial | Hoje depende do que o Gemini capta no áudio; classificador dedicado fica para evolução. A correlação de indução (§3.5) já está pronta para consumir esses eventos. |
| **Detecção CV** de contramão/saída-faixa/velocidade/capacete | 🟡 | Depende de evolução do Motor de Detecção/infra (Tier C da taxonomia). |
| **PDF do laudo v2** | 🟡 | JSON canônico pronto; `gerar_pdf` reusa `src/reporting` (best-effort). |
| **Retroalimentação automática** (§16) | 🔴 | Captura já existe; loop de re-treino batch fica para fase seguinte. |
| **Polling incremental Techpark** (§5.3) | 🟠 | Hoje é push (`ingest`); polling depende do contrato do cliente. |
| **Migração do servidor atual** → v2 | 🟡 | `backend/app.py` roda em paralelo sob `/api/v2`; streaming/upload seguem no servidor atual durante a transição. |

> Nota honesta: o backend v2 **não foi exercitado contra Vertex/Postgres reais**
> nesta sessão — os 20 testes cobrem os motores determinísticos e o pipeline com
> `result` simulado (sem rede/DB). Os caminhos que chamam Gemini têm fallback
> resiliente, mas precisam de um teste de fumaça em homologação antes do corte.

---

## 4. Como validar

```bash
cd ~/Desktop/Valbot
python3 -m venv .venv-test && .venv-test/bin/pip install pydantic pytest fastapi httpx
VALBOT_DB_DISABLED=1 .venv-test/bin/python -m pytest tests/backend/ -q     # 20 passed
VALBOT_DB_DISABLED=1 .venv-test/bin/uvicorn backend.app:app --port 8001    # /api/v2/health
```

Migrations: aplicar `migrations/009`–`013` no Postgres (idempotentes, `IF NOT EXISTS`).

---

## 5. Próximos passos sugeridos

1. **Carregar a Matriz Nacional no DB** (`exam_rules`) a partir da taxonomia +
   artigos CTB/fichas MBEDV reais; hoje o seed cobre as 47 condutas da 1.020.
2. **Acordar com o integrador** o envio de `pontuacao_oficial` + `infracoes` —
   destrava as divergências 2/3/4 de verdade.
3. **Teste de fumaça em homologação** (Gemini + Postgres reais) de um exame ponta
   a ponta pelo `backend.pipeline.processar`.
4. **Portais Auditor/Supervisor** (frontend) consumindo `/api/v2/os`.
5. **Migrar o servidor atual** para o app v2 incrementalmente.
