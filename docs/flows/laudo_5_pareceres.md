# Laudo — Cadeia de Decisão (os 5 pareceres)

> Os **5 contextos de veredito** que um laudo de exame prático carrega, na ordem
> da escalação. Catálogo único de fonte de dados, estados e onde cada um aparece.

## Por que existe

Um mesmo exame é julgado por até **cinco instâncias diferentes**. Antes, o laudo
só destacava duas delas (Examinador e IA); Comitê, Auditor e Supervisor ficavam
restritos aos workspaces. Esta seção do laudo torna os **cinco** explícitos, num
só lugar e na ordem em que a decisão escala — para o leitor entender quem decidiu
o quê, em que ordem, e onde houve convergência ou divergência.

## A cadeia

```
① Examinador  →  ② Auditor Val (IA)  →  ③ Comitê de IA  →  ④ Auditor  →  ⑤ Supervisor
  presencial       motor automático      refino (se          parecer        decisão
  (TechPrático)    (resultado calc.)     divergência)        humano         final
```

A ordem é de **escalação**: cada elo pode concordar ou divergir do anterior. Nem
todos sempre existem — ver "Estados pendentes".

## Fonte de dados (blocos do `laudo-json`)

Todos os cinco saem do **mesmo** `laudo-json` (`/api/exams/{hash}/laudo-json`,
montado por `_laudo_blocos_14_2`). Web e PDF leem a mesma fonte → ficam coerentes.

| # | Parecer | Fonte | Campos principais |
|---|---------|-------|-------------------|
| ① | **Examinador** | `3_examinador` + `4_resultado_oficial` | `nome`, `resultado_oficial`/`resultado_exame` (A/R), `pontuacao_oficial`, `anotacoes_tpa` |
| ② | **Auditor Val (IA)** | `1_identificacao` + `5_resultado_calculado` | `modelo_ia_principal`, `resultado_calculado`/`aprovado`, `pontuacao_calculada` |
| ③ | **Comitê de IA** | `9_comite_ia` | `conclusao_comite`, `recomendacao_para_auditor`, `causas_identificadas` |
| ④ | **Auditor** (humano) | `10_parecer_auditor` | `auditor` (nome), `decisao` (concorda/discorda), `resultado_final`, `justificativa`, `referencia_mbedv` |
| ⑤ | **Supervisor** (humano) | `11_decisao_supervisor` | `decisao_final` (homologar/reformar), `justificativa`, `homologar_conduta` |

Os nomes de Auditor/Supervisor são **dinâmicos** (vêm dos dados). Quando ausentes,
mostra-se apenas o papel.

## Estados pendentes

Nunca se inventa veredito. Quando o bloco está vazio:

- **③ Comitê** → `Não acionado — sem divergência a refinar` (o comitê só roda
  quando há divergência entre ① e ②).
- **④ Auditor** → `Aguardando parecer do auditor`.
- **⑤ Supervisor** → `Aguardando decisão do supervisor`.

Com o DB indisponível, todos os cinco caem em pendente — o documento continua
válido.

## Onde aparece

| Superfície | Arquivo | Componente/função |
|------------|---------|-------------------|
| **Laudo web** | `valbot-web/src/pages/Detalhes/laudo/BlocoCadeiaVereditos.tsx` | `BlocoCadeiaVereditos` (após o Sumário, em `LaudoCompleto`) |
| **PDF oficial** | `valbot-api/tooling/api_stub/server.py` | seção "Cadeia de Decisão — 5 Pareceres" em `_laudo_pdf_v2_html` |

## Notas de domínio

- **Terminologia travada**: veredito de candidato é sempre `APROVADO`/`REPROVADO`
  (CONTRAN 1.020/2025). No frontend, via `resultadoLabel` (`@/design/resultado`);
  no PDF, via o mapeamento `_ar()`. Nunca "APTO/INAPTO".
- **Comitê é recomendação, não veredito final** — apoia o auditor, não decide.
- **Supervisor é a decisão final** (homologa ou reforma o parecer do auditor).
- Resultado `N` do TechPrático = "não avaliado", **não** é reprovado.
