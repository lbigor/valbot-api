# Mapa de Assertividade — VALBOT v1

**Baseado em:** análise técnica de 4 vídeos VIP Intelbras gravados em 1280×720 (grid 2×2), resultando em 640×360 por câmera individual. Profile H.264 Constrained Baseline com bitrate médio de 4.8 Mbps. Áudio AAC 44.1kHz com clipping detectado.

**Layout confirmado das câmeras:**

| Quadrante | Posição no grid | Função real |
|---|---|---|
| TL | Superior-esquerda | Frontal / pista à frente |
| TR | Superior-direita | Lateral direita (espelho + para-lama) |
| BL | Inferior-esquerda | Interna (candidato + examinador) |
| BR | Inferior-direita | Traseira baixa / lateral esquerda |

---

## Lista consolidada — 22 infrações ordenadas por assertividade

| # | Infração | ID | Câmera | Severidade | Assertividade | Tier |
|---|---|---|---|---|---|---|
| 1 | Não colocar cinto de segurança | `789_elim_03` | INTERNA | Eliminatória | **95%** | 🟢 T1 |
| 2 | Avançar sobre o meio-fio | `789_elim_02` | TRASEIRA-ESQ | Eliminatória | **90%** | 🟢 T1 |
| 3 | Não respeitar linha de retenção | `789_elim_01` | FRONTAL | Eliminatória | **90%** | 🟢 T1 |
| 4 | Não respeitar PARE pintado no chão | `789_elim_01` | FRONTAL | Eliminatória | **90%** | 🟢 T1 |
| 5 | Mão fora do volante (prolongado) | `789_leve_01` | INTERNA | Leve | **88%** | 🟢 T1 |
| 6 | Desobedecer semáforo vermelho próximo | `789_elim_01` | FRONTAL | Eliminatória | **85%** | 🟢 T1 |
| 7 | Cruzar zebrado de canalização (ZPA) | `789_grave_05` | FRONTAL | Grave | **85%** | 🟢 T1 |
| 8 | Não sinalizar seta antes de mudar de faixa | `789_grave_05` | INTERNA+FRONTAL | Grave | **75%** | 🟡 T2 |
| 9 | Não verificar retrovisor antes de manobra | `789_grave_05` | INTERNA | Grave | **75%** | 🟡 T2 |
| 10 | Ultrapassar em linha amarela contínua | `789_grave_05` | FRONTAL | Grave | **75%** | 🟡 T2 |
| 11 | Passar em faixa de pedestre com pedestre | `789_elim_01` | FRONTAL | Eliminatória | **75%** | 🟡 T2 |
| 12 | Subir no meio-fio lateralmente (roda esq.) | `789_elim_02` | TRASEIRA-ESQ | Eliminatória | **75%** | 🟡 T2 |
| 13 | Trepidação anormal (desregulagem) | `789_media_02` | INTERNA+ÁUDIO | Média | **70%** | 🟡 T2 |
| 14 | Solavanco ao trocar marcha | `789_leve_01` | INTERNA | Leve | **70%** | 🟡 T2 |
| 15 | Uso inadequado de buzina | `789_grave_01` | ÁUDIO | Grave | **70%** | 🟡 T2 |
| 16 | Comentário inadequado do examinador | `audit_examinador` | ÁUDIO | Auditoria | **70%** | 🟡 T2 |
| 17 | Não dar preferência (R-2) | `789_grave_05` | FRONTAL+BR | Grave | **55%** | 🟠 T3 |
| 18 | Desobedecer R-4/R-5/R-25 (placas distantes) | `789_grave_05` | FRONTAL | Grave | **55%** | 🟠 T3 |
| 19 | Desobedecer R-19 (velocidade) | `789_media_02` | FRONTAL | Média | **50%** | 🟠 T3 |
| 20 | Parar em local proibido (R-6/R-7) | `789_leve_04` | FRONTAL | Leve | **50%** | 🟠 T3 |
| 21 | Direção defensiva insuficiente | subjetivo | múltiplas | N/A | **45%** | 🟠 T3 |
| 22 | Distância de seguimento inadequada | subjetivo | FRONTAL | N/A | **45%** | 🟠 T3 |

**Linha de corte recomendada para MVP v0.1:** itens 1-7 (≥85% de assertividade).

---

## Tier 4 — Inviável em v1 (requer OBD-II/GPS)

- Pé na embreagem com marcha engrenada
- Freio de estacionamento não acionado
- Marcha adequada à situação
- Velocidade real (excesso ou muito baixa)
- Aceleração/desaceleração bruscas
- Ponto morto em descida
