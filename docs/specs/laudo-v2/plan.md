# Plano Técnico — Laudo v2.0

**Short name:** laudo-v2 · Base: `spec.md` + `requisitos_laudo_v2.md` + `backend/reporting/laudo.py` + `backend/models.py`.

> Desenho de COMO implementar os 12 blocos. A implementação é executada pelas tarefas de laudo paralelas; aqui ficam contratos, recomendações e reúso. **Decisão estrutural deixada à tarefa de implementação** (ver §1).

## 1. Estratégia de evolução do JSON — **recomendação: ADITIVO**
Manter as chaves atuais do `montar_laudo_json()` (`cobertura`, `divergencia`, `analise_detalhada`, `resultado_calculado`, `eventos_examinador`, `comentarios_compliance`, `integridade`, `versoes`, `ordem_servico`) e **somar** os blocos faltantes como novas chaves. Evita breaking change no frontend (`frontend/.../types/laudo.ts`), no template PDF (`src/reporting/templates/laudo.html`) e nos consumidores (Techpark, BI).

Mapa 12-blocos → chave JSON (nomes propostos; a tarefa de implementação confirma):

| Bloco | Chave JSON | Origem |
|---|---|---|
| 1 Cabeçalho | `identificacao` + `versoes` + `integridade` (+ `codigo_laudo`, `fichas_mbedv`, `integridade.matriz_hash`) | já existe + adições |
| 2 Sumário Executivo | **`sumario_executivo`** (novo, derivado) | computado dos demais blocos |
| 3 Identificação | `identificacao` + `candidato` + `examinador` (+ `comissao`, `veiculo`, `cfc`, `unidade`, `trajeto`) | expandir |
| 4 Resultado Oficial | `resultado_oficial` (+ `anotacoes_tpa`, `motivo_interrupcao`) | expandir |
| 5 Resultado ValBot | `resultado_calculado` (+ `confianca_agregada`, `evidencia_insuficiente`) | existe |
| 6 Divergência | `divergencia` (+ `cor_severidade`, `justificativa_tecnica`, `hipoteses_causa`) | expandir |
| 7 Infrações | `analise_detalhada` (+ `inf_id` INF-NNN, `cor`, `links`, `recomendacao_tecnica`) | expandir |
| 8 Linha do Tempo | **`linha_do_tempo`** (novo) | agrega `exam_eventos` + áudio + TPA + decisões |
| 9 Conduta Examinador | **`conduta_examinador`** (novo, substitui/estende `eventos_examinador`) | classificação tripla + % |
| 10 Checklist Anexo K | **`checklist_anexo_k`** (novo) | 12 validações |
| 11 Encaminhamento | `ordem_servico` + **`encaminhamento`** (pareceres/estados) | expandir |
| 12 Trilha Auditoria | `versoes` + `integridade` + **`trilha_auditoria`** (log de acesso) | expandir |

`laudo_versao` passa de `"laudo/2.0"` para refletir a estrutura do novo doc (ex.: `"laudo/2.1-12blocos"`) — sem quebrar leitura tolerante.

## 2. Contratos novos (modelos Pydantic — `backend/models.py`)
Adicionar (sem alterar os existentes):
- **`EventoLinhaTempo`**: `tipo` (enum 8 valores: telemetria | comportamento | audio_candidato | audio_examinador | anotacao_tpa | etapa | decisao_ia | interrupcao), `origem`, `timestamp_s`, `descricao`, `camera_origem?`, `link_video?`. Fonte: `SaidaDeteccao.eventos_detectados` (já tem `timestamp_video_seg`, `camera_origem`, `transcricao`) + `comentarios_examinador` + `payload.telemetria` + anotações TPA do `resultado_oficial`.
- **`ClassificacaoConduta`** (enum: adequado | atencao | inadequado) e **`CondutaExaminador`**: `comentarios: list[ComentarioExaminador+classificacao]`, `pct_conformidade: float`, `recomendacao_apuracao: bool`, `fundamentacao_mbedv: list[str]`. Estende `ComentarioExaminador` (já existe) com a classificação tripla.
- **`ItemChecklistAnexoK`**: `numero` (1–12), `pergunta`, `veredito` (enum: sim | nao | nao_aplicavel | requer_verificacao_humana), `critico: bool` (itens 1,2,8,9,10), `timestamp_s?`, `evidencia?`. **`ChecklistAnexoK`**: `itens: list[...]`, `aprovados: int`, `total: int = 12`, `escalou_auditor: bool`.
- **`SumarioExecutivo`**: `resultado_oficial`, `resultado_calculado`, `cor_semaforo` (enum: verde|vermelho|laranja|cinza|roxo), `tipo_divergencia?`, `indicadores: list[{label,valor}]` (3–5), `recomendacao_encaminhamento`.
- **`VersaoLaudo`** (enum: PRELIMINAR | INTERMEDIARIO | FINAL | CONSOLIDADO) — parâmetro de `montar_laudo_json()`.

Enums de cor/severidade derivam de regra determinística (§3) — não vêm da IA.

## 3. Regras determinísticas (puras, testáveis — constitution §VII)
- **Semáforo (FR-LAU-02 / doc §5.3):** `verde` se concordância de resultado; `vermelho` se `1_resultado`; `laranja` se `2_pontuacao`/`3_infracao`/`4_enquadramento`; `cinza` se `5_evidencia_insuficiente`; `roxo` se `houve_interrupcao`. Função pura sobre `Comparacao` + `ResultadoPontuacao`.
- **Item crítico do checklist:** `numero in {1,2,8,9,10}`; se `veredito == nao` em qualquer crítico → `escalou_auditor = True`.
- **Conduta % conformidade:** `adequados / total_comentarios`; comentário `inadequado` **nunca** entra na pontuação (constitution §V) — só aciona `recomendacao_apuracao`.
- **INF-NNN:** numeração sequencial estável por ordem de `timestamp_s` crescente.

## 4. Reúso (não reescrever)
- `hash_relatorio()` em `backend/reporting/laudo.py:172` — integridade SHA-256 ignorando o próprio hash. Aplicar igual ao `matriz_hash`.
- `_mascarar_cpf()` em `laudo.py:32` — base da LGPD (FR-LAU-T1); estender para versão controlada vs. externa.
- `engines/comparacao.py` — já classifica os 5 tipos; bloco 6 só formata + adiciona cor/justificativa.
- `engines/excecoes.py` + `exam_comentarios_compliance` (migration 016) — não-pontuáveis → compliance (FR-LAU-T6), já implementado.
- `backend/committee/comite.py` — laudo do Comitê read-only (FR-LAU-11 / constitution §I).
- `backend/workflow/ordens.py` (`os_eventos` append-only) — base da trilha (bloco 12) e dos estados (bloco 11).
- `src/reporting/pdf.py` + `templates/laudo.html` — base do HTML/PDF; estender, não refazer.

## 5. Persistência
Maior parte é **derivada em tempo de montagem** (não exige migration nova): linha do tempo agrega `exam_eventos`; sumário e semáforo são computados; checklist deriva de validações já existentes (`exam_camera_validations`) + áudio. Migrations novas só se a tarefa de implementação optar por persistir o checklist/conduta (avaliar `exam_checklist_anexo_k` e `exam_conduta_examinador`). **Decisão de persistir vs. derivar fica para a implementação.**

## 6. Itens diferidos (não implementar)
Assinatura ICP-Brasil, carimbo de tempo, PDF/A-2, biometria 1:1 (checklist item 1 → `requer_verificacao_humana` por ora), telemetria URE (linha do tempo usa o que houver em `payload.telemetria`). Ver `requisitos_laudo_v2.md` §Itens diferidos.

## 7. Test scenarios (para a implementação)
- Semáforo: 5 entradas → 5 cores corretas (tabela §3). Determinístico.
- Checklist: exame com item crítico `nao` → `escalou_auditor == True`; indicador "X de 12".
- Conduta: comentário inadequado → `pct_conformidade` reduz, pontuação do candidato **inalterada**, `recomendacao_apuracao == True`.
- Linha do tempo: eventos ordenados por timestamp, 8 tipos representados, cada um com origem.
- Aditivo: laudo v1 continua parseável (chaves antigas presentes) após somar blocos novos.
- Integridade: `hash_relatorio` estável e reprodutível ignorando o próprio campo.
