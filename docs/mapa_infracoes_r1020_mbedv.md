# Mapa de Infrações: detecção legada (R1020-*) → MBEDV canônico

> Como cada uma das **30 condutas** que o sistema detecta hoje (`src/rubrics/taxonomia.py`,
> IDs `R1020-*`) se relaciona com as **84 fichas reais do MBEDV** (Art. CTB,
> `configs/references/mbedv_fichas.json`). Fonte de verdade do código:
> `backend/matriz/correspondencia.py`. Validar com especialista/Techpark antes do go-live.

## Regra de classificação

- **PONTUA** — correspondência inequívoca com uma ficha CTB → mapeia para `codigo_val` e
  **soma pontos** via Matriz.
- **A VALIDAR** — correspondência plausível, mas artigo/inciso ambíguo → **inerte** (não
  pontua, não some) até validação por especialista.
- **COMPLIANCE** — sem ficha pontuável no MBEDV (cinto, baliza, técnicas de exame) →
  **não pontua**; vira **comentário de compliance** (tela dedicada).

## PONTUA (6) — ativo

| R1020 | Conduta (taxonomia) | → Art. CTB (ficha MBEDV) | Natureza/Peso |
|---|---|---|---|
| R1020-G-a | Desobedecer sinalização semafórica / parada obrigatória | **Art. 208** | gravíssima/6 |
| R1020-G-d | Transitar em contramão (via de duplo sentido) | **Art. 186, I** | grave/4 |
| R1020-G-g | Exceder a velocidade regulamentada | **Art. 218, I** | — (por faixa) |
| R1020-GR-c | Não observar a preferência do pedestre | **Art. 214, I** | gravíssima/6 |
| R1020-GR-e | Não sinalizar a manobra com antecedência (seta) | **Art. 196** | grave/4 |
| R1020-M-e | Usar buzina sem necessidade / local proibido | **Art. 227** | leve/1 |

## A VALIDAR (6) — inerte até validação

| R1020 | Conduta | → Art. CTB candidato | Por que validar |
|---|---|---|---|
| R1020-G-b | Avançar sobre o meio-fio | Art. 193 (calçada/passeio) | "meio-fio" ≠ exatamente "calçada" |
| R1020-G-e | Avançar via preferencial | Art. 215 (deixar de dar preferência) | inciso a confirmar |
| R1020-GR-a | Desobedecer sinalização da via / agente | Art. 195 (desobedecer agente) | pode ser sinalização (207/208) |
| R1020-M-b | Velocidade inadequada p/ condições | Art. 220 (deixar de reduzir) | ou Art. 219 |
| R1020-M-d | Conversão incorreta | Art. 206 (retorno/conversão) | inciso ambíguo |
| R1020-GR-b | Ultrapassagem / mudança de direção incorreta | Art. 199-203 (família) | múltiplos artigos |

## COMPLIANCE (18) — não pontua, vira comentário

Sem ficha pontuável no MBEDV anexo (são técnicas de exame ou artigo ausente do anexo).
Decisão de produto: tratar como **comentário de compliance** (tela dedicada), não infração.

| R1020 | Conduta | Motivo |
|---|---|---|
| R1020-GR-f | Cinto de segurança | Art. 167 **ausente** do anexo de fichas |
| R1020-G-c | Baliza em 3 tentativas | integrada ao estacionamento; sem ficha autônoma |
| R1020-GR-d | Porta aberta durante percurso | sem ficha |
| R1020-G-f | Provocar acidente | consequência; sem ficha pontuável direta |
| R1020-GR-g | Perder o controle da direção | sem ficha direta |
| R1020-M-a | Freio de mão não inteiramente livre | técnica de exame |
| R1020-M-c | Interromper o motor (carro morreu) | técnica + §3.5 (não pontua) |
| R1020-M-f | Desengrenar em declive | técnica de exame |
| R1020-M-g | Partida sem as cautelas | técnica de exame |
| R1020-M-h | Embreagem antes do freio | técnica (exige OBD) |
| R1020-M-i | Ponto neutro em curva | técnica (exige OBD) |
| R1020-M-j | Marchas incorretas | técnica de exame |
| R1020-L-a | Movimentos irregulares | técnica de exame |
| R1020-L-b | Banco mal ajustado | técnica de exame |
| R1020-L-c | Espelhos retrovisores mal ajustados | técnica de exame |
| R1020-L-d | Pé na embreagem em movimento | técnica (exige OBD) |
| R1020-L-e | Uso/interpretação do painel | técnica de exame |
| R1020-L-f | Partida com tração ligada | técnica de exame |

**Total: 6 + 6 + 18 = 30 condutas.**

## Observações

- O **cinto** era um dos detectores Tier A principais do projeto, mas **não tem ficha** no
  MBEDV anexo — por isso vira compliance (não pontua). Decisão a confirmar com a Techpark.
- Reclassificar uma conduta de COMPLIANCE → PONTUA exige uma ficha CTB correspondente e
  validação; basta movê-la de `COMPLIANCE_SEM_FICHA` para `R1020_PARA_CODIGO_VAL`.
