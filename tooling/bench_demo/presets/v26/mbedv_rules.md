# Catálogo MBEDV — Faltas avaliáveis em exame prático Cat B

> Fonte: Manual Brasileiro de Exames de Direção Veicular (MBEDV), publicado
> pela SENATRAN em 01/fev/2026, baseado na Resolução CONTRAN 1.020/2025.
> PDF oficial em `configs/references/mbedv_anexo_fichas_avaliacao.pdf`.
>
> Este arquivo é a fonte ÚNICA da verdade pros prompts modulares v26. Quando
> mudar peso/gravidade aqui, propague pro `cam_*.md` que cita a regra.

## BASE LEGAL UNIFICADA (v26-lean)

Este catálogo padroniza TODAS as infrações observáveis em prova prática Cat B usando como referencial:

1. **CTB — Lei Federal 9.503/97** (artigos 161–256, infrações de trânsito): fonte primária. Toda falta tem ID `Art. XXX` direto do CTB.
2. **MBEDV — Manual Brasileiro do Examinador da Direção Veicular** (SENATRAN 02/2026): curadoria operacional do CTB pra exame prático. Define quais artigos do CTB aplicam, quais pesos, e como o examinador deve observar.
3. **Res. CONTRAN 1.020/2025**: rubrica histórica. **Resultados anteriores a v26 ficam marcados `catalog_version: v25`** com IDs custom `R1020-*` — não migrar; só novos exames usam `v26`.
4. **MBEDV-MEC-** *(extensão própria)*: condutas mecânicas Cat B (operação de freio de mão, embreagem, marcha, partida) que o MBEDV oficial absorveu em "condições mínimas de segurança/domínio do veículo" sem ID dedicado — aqui catalogadas explicitamente pra a IA detectar e pontuar.

**Resumo da convenção de IDs:**

| Prefixo | Origem | Exemplo | Pontuação |
|---|---|---|---|
| `Art. XXX` | CTB direto (curado pelo MBEDV) | `Art. 186-II` (contramão sentido único) | Tabela CTB oficial |
| `MBEDV-MEC-*` | Condutas operacionais Cat B sem ID CTB | `MBEDV-MEC-estol-motor` | 1 ou 2 pts (Leve/Média) |
| `ETICA-*` | Conduta ética (não pontua, vai pra `observacoes_conduta`) | `ETICA-grito` | sinalização humana |
| `R1020-*` | **LEGADO** (catalog_version=v25 só) | `R1020-G-a` | não usar em prompts v26 |

## Princípios MBEDV (Fevereiro 2026)

1. **Limite de reprovação:** > 10 pontos no total = REPROVADO.
2. **Sem eliminatórias automáticas.** Interrupção do exame só quando o
   candidato não apresenta "condições mínimas de segurança, domínio do
   veículo ou equilíbrio emocional" (julgamento do examinador).
3. **Pesos por gravidade** (uniforme nacional):
   - Leve = 1 ponto
   - Média = 2 pontos
   - Grave = 4 pontos
   - Gravíssima = 6 pontos
4. **Baliza** deixou de ser etapa obrigatória — integrada ao estacionamento
   final do percurso.
5. **Categorias:** A maioria das fichas se aplica a TODAS (ACC, A, B, C, D, E).
   Excepcionalmente algumas variam por categoria (ex: Art. 184 III só pra D).

## Código de conduta e penalidades (MBEDV §4-5)

> Referência normativa. Estas penalidades de CONDUTA são SEPARADAS das faltas
> de trânsito pontuáveis acima — **não somam pontos** e são decididas pela
> comissão humana (processo administrativo), não pela IA. No prompt v26
> (`cat_B/base.md`) a IA apenas SINALIZA em `observacoes_conduta` os eventos
> com evidência audiovisual inequívoca, pra revisão humana.

- **Examinador (§4):** dever de tratar candidatos com educação/respeito,
  imparcialidade e rigor técnico; vedada avaliação privilegiada/discriminatória.
- **Eliminação imediata do candidato:** tentativa de fraude; falta de respeito,
  urbanidade ou decoro; desobediência, desacato ou constrangimento ao examinador.
- **Suspensão (até 6 meses):** fraude comprovada; exame sob efeito de álcool/
  substância; violência moral contra examinador/servidores/candidatos.
- **Cancelamento da habilitação:** reincidência em infrações graves; fraude
  grave ou violência física (exceto legítima defesa).
- **Interrupção do exame:** incapacidade técnica (imperícia reiterada nos
  comandos básicos) OU instabilidade emocional manifesta/comportamento
  incompatível → exame não concluído, sem nota, motivo registrado.

## Tabela de faltas (Art. CTB)

| ID | Descrição curta | Gravidade | Peso | Cats |
|---|---|---|---|---|
| **Art. 169** | Dirigir sem atenção ou sem cuidados indispensáveis | Leve | 1 | ALL |
| **Art. 170-ped** | Dirigir ameaçando pedestres atravessando | Gravíssima | 6 | ALL |
| **Art. 170-vei** | Dirigir ameaçando demais veículos | Gravíssima | 6 | ALL |
| **Art. 171-ped** | Usar veículo p/ arremessar sobre pedestres (água/detritos) | Média | 2 | ALL |
| **Art. 171-vei** | Usar veículo p/ arremessar sobre veículos | Média | 2 | ALL |
| **Art. 172-atirar** | Atirar do veículo objetos/substâncias na via | Média | 2 | ALL |
| **Art. 172-aband** | Abandonar na via objetos/substâncias | Média | 2 | ALL |
| **Art. 175** | Demonstrar manobra perigosa (arrancada, derrapagem, frenagem) | Gravíssima | 6 | ALL |
| **Art. 181-II,VII** | Estacionar afastado 50cm-1m do meio-fio / em acostamento | Leve | 1 | ALL |
| **Art. 181-I,IV,VI,IX,X,XIII,XV,XVIII** | Estacionar (variações médias) | Média | 2 | ALL |
| **Art. 181-III,VIII,XI,XII,XIV,XVI,XVII,XIX** | Estacionar (variações graves) | Grave | 4 | ALL |
| **Art. 181-V,XX** | Estacionar em rodovia/via rápida; vagas PCD/idoso s/ credencial | Gravíssima | 6 | ALL |
| **Art. 183** | Parar veículo sobre faixa de pedestres na mudança de sinal | Média | 2 | ALL |
| **Art. 184-I** | Transitar em faixa direita exclusiva (ex: ônibus) | Leve | 1 | ALL |
| **Art. 184-II** | Transitar em faixa esquerda exclusiva | Grave | 4 | ALL |
| **Art. 184-III** | Transitar em faixa exclusiva de transporte coletivo | Gravíssima | 6 | ALL (atenção Cat D) |
| **Art. 185-I** | Não conservar faixa de regulamentação (uso exames) | Média | 2 | ALL |
| **Art. 185-II** | Não manter faixas da direita (veículos lentos/maior porte) | Média | 2 | ALL |
| **Art. 186-I** | Contramão em vias de duplo sentido | Grave | 4 | ALL |
| **Art. 186-II** | Contramão em via de sentido único | Gravíssima | 6 | ALL |
| **Art. 187** | Transitar em locais/horários não permitidos | Média | 2 | ALL |
| **Art. 188** | Transitar ao lado de outro veículo interrompendo trânsito | Média | 2 | ALL |
| **Art. 189** | Deixar de dar passagem a veículos de urgência (batedores, ambulâncias) | Gravíssima | 6 | ALL |
| **Art. 190** | Seguir veículo em serviço de urgência | Grave | 4 | ALL |
| **Art. 191** | Forçar passagem entre veículos em ultrapassagem | Gravíssima | 6 | ALL |
| **Art. 192** | Não guardar distância de segurança (frontal/lateral) | Grave | 4 | ALL |
| **Art. 193** | Transitar em calçadas, passeios, ciclovias, ilhas, gramados | Gravíssima | 6 | ALL |
| **Art. 194** | Transitar em marcha à ré (com risco) | Grave | 4 | ALL |
| **Art. 195** | Desobedecer ordens da autoridade de trânsito / examinador | Grave | 4 | ALL |
| **Art. 196** | **Não sinalizar com antecedência** manobra (seta) | **Grave** | **4** | **ALL** |
| ... (Art. 197+) | A catalogar | | | |

## Faltas mecânicas Cat B (MBEDV-MEC-*)

> 7 condutas sem artigo CTB dedicado mas observáveis no exame Cat B. MBEDV
> as agrupa em "condições mínimas de segurança". Pontuam normal.

| ID | Descrição | Gravidade | Peso |
|---|---|---|---|
| MBEDV-MEC-freio-mao | Conduzir com freio de mão acionado | Média | 2 |
| MBEDV-MEC-estol-motor | Motor calar sem justa razão | Média | 2 |
| MBEDV-MEC-embreagem-pre-freio | Pisar embreagem antes do freio em frenagem | Média | 2 |
| MBEDV-MEC-ponto-neutro-curva | Curva em ponto morto | Média | 2 |
| MBEDV-MEC-engrenar-incorreto | Engrenar marcha errada | Média | 2 |
| MBEDV-MEC-pe-embreagem | Pé na embreagem >=5s em movimento | Leve | 1 |
| MBEDV-MEC-partida-engrenado | Partida com cambio engatado (salto) | Leve | 1 |

## Notas críticas vs. v25 prompt antigo

| Mudança | Antes (v25) | Agora (v26-lean, MBEDV + CTB) |
|---|---|---|
| ID das faltas | Custom `R1020-X-y` | `Art. XXX` do CTB + `MBEDV-MEC-*` (mecânicas Cat B) |
| Catálogo de mecânicas | 7 IDs (`R1020-M-{a,c,h,i,j}`, `R1020-L-{d,f}`) | 7 IDs `MBEDV-MEC-*` com mesmos pesos/severidades |
| Não sinalizou seta | R1020-GR-e Gravíssima 6 | **Art. 196 Grave 4** ✅ correção |
| Eliminatórias automáticas | Tinha (cinto, celular) | Não existe mais — só julgamento de "condições mínimas" |
| Limite reprovação | "> 10 pontos" | Confirma "> 10 pontos" |
| Baliza | Etapa obrigatória avaliada | Não-obrigatória; integrada ao estacionamento |
| Histórico (303 exames) | `catalog_version: v25`, mantém IDs R1020-* | Imutável; só novos exames usam IDs `Art. XXX` / `MBEDV-MEC-*` |

## Estrutura padrão de cada Art. XXX no preset

Cada regra no `cam_*.md` deve seguir o template MBEDV:

```markdown
### Art. XXX — <descrição curta> [<gravidade>, <peso> pts]

**Descrição:** <enunciado MBEDV>

**Condutas que pontuam (qualquer uma basta):**
- <comportamento 1>
- <comportamento 2>
- ...

**Condutas que NÃO pontuam (descartar mesmo se parecer):**
- <exceção 1>
- <exceção 2>
- ...

**Constatação:** <quando o examinador anota>

**Evidência visual esperada nesta câmera:** <específico da câmera>

**Evidência de áudio confirmatória/desqualificadora:** <som diagnóstico>
```

## Próximos passos

- [ ] Ler páginas 31+ do PDF (Art. 197 em diante)
- [ ] Mapear todas as fichas do PDF (estimo ~50-60 artigos)
- [ ] Atualizar `cam_*.md` pra usar IDs `Art. XXX`
- [ ] Corrigir Art. 196 no GUARD anti-falso-positivo (estava como GR-e)
- [ ] Validar contra os 12 exames já processados — quanto muda o resultado?
