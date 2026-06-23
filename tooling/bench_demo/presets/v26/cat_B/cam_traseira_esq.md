# Câmera TRASEIRA_ESQ — Cat B (alinhado ao MBEDV/2026)

## O que esperar nesta câmera

Roda traseira esquerda + faixa atrás à esquerda + cones de balizamento
durante exame de estacionamento final. Mostra: mudança de faixa pra
esquerda, veículos atrás se aproximando, distância pneu traseiro esquerdo
→ meio-fio esquerdo, alinhamento durante manobra de estacionamento.

> **MUDANÇA MBEDV/2026:** Baliza deixou de ser etapa obrigatória avaliada
> em isolamento. Agora o estacionamento final integra o percurso. Foco
> aqui é em INFRAÇÕES de circulação, não em "completou baliza ou não".

## Faltas MBEDV primariamente detectadas aqui

### Art. 181 — Estacionar veículo (variações que aparecem aqui)

| Inciso | Conduta | Gravidade | Peso |
|---|---|---|---|
| I | Nas esquinas e a menos de 5m do alinhamento da via transversal | Média | 2 |
| V | Em pista de rolamento de rodovias/vias rápidas | Gravíssima | 6 |
| VIII | Sobre calçada ou faixa de pedestres lateral | Grave | 4 |
| XV | Na contramão de direção | Média | 2 |
| XX | Vagas reservadas a PCD/idoso sem credencial | Gravíssima | 6 |

### Art. 184-II — Transitar em faixa esquerda exclusiva [Grave, 4 pts]
**Condutas que pontuam:**
- Candidato circula com veículo em faixa destinada a outro tipo de veículo
  (faixa esquerda regulamentada como exclusiva).

**Condutas que NÃO pontuam:**
1. Acessando imóveis.
2. Realizando conversões à esquerda.

### Art. 185-II — Não manter veículos lentos/maior porte nas faixas da direita [Média, 2 pts]
**Condutas que pontuam:**
- Não circular na faixa destinada a veículos de maior porte/lentidão
  durante o exame (percurso determinado).

**Condutas que NÃO pontuam:**
- Quando o condutor for ingressar à esquerda (manobra justificada).

### Art. 194 — Transitar em marcha à ré (com risco) [Grave, 4 pts]
**Descrição MBEDV:** "Transitar em marcha à ré, salvo na distância necessária
a pequenas manobras e de forma a não causar riscos à segurança."

**Condutas que pontuam:**
1. Marcha à ré colocando em risco segurança de pedestres/veículos.
2. Marcha à ré cruzando o fluxo veicular.
3. Marcha à ré por **ter passado** do cruzamento ou do acesso pretendido.
4. Marcha à ré com **velocidade incompatível** com a segurança.

**Condutas que NÃO pontuam:**
1. Pequenas manobras em marcha à ré para estacionar (sem risco).
2. Candidato com veículo IMOBILIZADO aciona ré por engano (em vez de
   primeira marcha) mas **não movimenta o veículo** — corrige a engrenagem
   a seguir.
3. Quando o examinador SOLICITAR realizar manobra em ré (condição adversa).

**Detecção visual:**
- Vê-se o veículo se deslocando pra trás no campo da TRASEIRA_ESQ.
- A INTERNA pode mostrar o candidato olhando pelo retrovisor / virando o
  pescoço pra ver pra trás — se NÃO fez isso, correlate com Art. 169
  (sem atenção, Leve 1pt).

### Art. 196 — Não sinalizou mudança de faixa esquerda
**Detecção TRASEIRA_ESQ específica:**

Quando o veículo se desloca pra esquerda (faixa adjacente entra no campo
de visão pela esquerda), candidato deveria ter sinalizado **antes**
mediante luz indicadora ou gesto regulamentar.

**Vide GUARD completo em `cam_interna.md`** — áudio do tic-tac é
autoritativo. Esta câmera é canal corroborador (vê o deslocamento), não
primário (não vê o painel da seta).

## NÃO detectar aqui (use outra câmera)

- Semáforo (use FRONTAL)
- Meio-fio direito (use LATERAL_DIREITA)
- Cinto (não existe mais)
- Ações intencionais (Art. 170, 175) — use FRONTAL

## Heurística

- Em manobra de estacionamento final, esta câmera é primária. Examinador
  costuma instruir "encosta aqui, alinha o pneu".
- Se vê só "céu" ou "asfalto vazio" sem o veículo → layout pode estar
  invertido. Marque `layout_disagreement`.
- **NÃO existe mais "não completou baliza" como falta** — se candidato
  bater no meio-fio durante estacionamento, use Art. 192 (distância) ou
  Art. 193 (subiu na calçada).
