# Câmera LATERAL_DIREITA — Cat B (alinhado ao MBEDV/2026)

## O que esperar nesta câmera

Janela/espelho do passageiro em primeiro plano. Mostra o meio-fio direito,
ciclistas/motos passando pela direita, calçada, eventualmente pé direito do
candidato em pedais, reflexo do pisca lateral direito quando acionado.

## Faltas MBEDV primariamente detectadas aqui

### Art. 181 — Estacionar veículo (várias variações)
**Variações que aparecem na LATERAL_DIREITA:**

| Inciso | Conduta | Gravidade | Peso |
|---|---|---|---|
| II | Afastado 50cm-1m do meio-fio | Leve | 1 |
| III | Afastado **mais de 1m** do meio-fio | Grave | 4 |
| VII | Em acostamento (salvo força maior) | Leve | 1 |
| VIII | Sobre calçada/ciclovia/passeio | Grave | 4 |

**Condutas que pontuam (LATERAL_DIREITA):**
- Veículo encosta no meio-fio com pneu dianteiro direito (II/III conforme distância)
- Para sobre a calçada → VIII

**Condutas que NÃO pontuam:**
- Parada para embarque/desembarque por **tempo estritamente necessário**
  (não é estacionar, é parar).

### Art. 192 — Distância lateral insuficiente [Grave, 4 pts] (vide cam_frontal pra detalhes)
**Detecção LATERAL_DIREITA específica:**
- Ciclista/motociclista passando pela direita com folga visual < 1.5m
  estimado em via urbana.
- Pneu dianteiro direito raspando muito próximo ao meio-fio (sem encostar
  ainda — colocando em risco).

### Art. 193 — Transitar sobre CALÇADA/PASSEIO [Gravíssima, 6 pts]
**Detecção LATERAL_DIREITA específica:**
- SÓ pontua quando o pneu estiver **apoiado e RODANDO sobre a superfície
  elevada do passeio/calçada** (a faixa de pedestres), de forma sustentada —
  o veículo transita POR CIMA da calçada. Exija ver a roda em cima da
  superfície, não apenas um contato.
- **NÃO pontua como Art. 193** (são manobra normal, não "transitar sobre
  calçada"): encostar, raspar ou subir MOMENTANEAMENTE o **meio-fio/guia**
  em conversão, baliza ou estacionamento. Isso é, no máximo, Art. 181
  (estacionamento irregular) ou Art. 192 (distância lateral) — NUNCA 193.
- **PROIBIDO inferir 193** por sinal indireto isolado: solavanco, oscilação
  do horizonte, mudança de perspectiva da câmera, queda abrupta da distância
  pneu→meio-fio, ou áudio "bateu no meio-fio"/"subiu na guia". Esses indícios
  sugerem TOQUE na guia, não trânsito sobre o passeio. Na dúvida, NÃO pontue.

### Art. 196 — Não sinalizou seta (corroboração LATERAL_DIREITA)
**Vide GUARD completo em `cam_interna.md`.**

Esta câmera serve como **canal corroborador**: o reflexo do pisca lateral
direito acende cíclico (luz amarela). Quando ACENDE → confirma sinalização
(desqualifica Art. 196). Quando NÃO aparece → não-conclusivo (o reflexo
pode estar fora do quadro). **Não dispense a câmera INTERNA como fonte
primária + áudio do tic-tac.**

## NÃO detectar aqui (use outra câmera)

- Cinto (não existe mais no MBEDV)
- Semáforos / placas frontais (use FRONTAL)
- Mudança de faixa pra ESQUERDA (use TRASEIRA_ESQ)
- Conduta intencional contra pedestre (use FRONTAL — Art. 170)

## Heurística

- Se câmera mostra **mais "céu" que "rua"** → ângulo ruim ou layout
  invertido. Marque divergência no `layout_disagreement` do JSON.
- Reflexo do pisca direito acende esta câmera em luz amarela cíclica.
  **Sinal CONFIRMATÓRIO** de sinalização — útil pra DESQUALIFICAR
  Art. 196 (não sinalizou).
