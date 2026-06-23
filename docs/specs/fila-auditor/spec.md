# Feature Spec — Fila do Auditor (tela imersiva)

**Short name:** fila-auditor · **Status:** Draft · Base: briefing + constitution (Val Auditor), spec funcional v2 §13.2.

## Resumo
Tela única e imersiva onde o Auditor (Techpark, nível 3) revisa exames de direção com divergência entre o registro do examinador (TechPrático) e o cálculo da IA (ValBot), e emite seu parecer. A IA é consultiva; a decisão é humana (constitution §I). Substitui a antiga "Fila Operacional" como tela-padrão do revisor.

## User Scenarios & Testing

### US1 — Escolher e revisar uma OS de divergência (P1, MVP)
O Auditor abre a Fila, seleciona uma OS pelo dropdown do topo, assiste ao vídeo e vê, na timeline, as 3 trilhas (TechPrático, ValBot, Auditor) com as infrações posicionadas no tempo. **Testável:** ao escolher uma OS, o player carrega, as trilhas mostram os marcadores por gravidade e o playhead navega.

### US2 — Comparar IA × Examinador e ler o laudo do Comitê (P1)
No inspector, o Auditor vê a Comparação (resultado/pontuação/infrações TP×VB com destaque de divergência) e o laudo do Comitê de IA (causas, recomendação) em modo leitura. **Testável:** linhas divergentes aparecem marcadas (≠); o laudo do Comitê é visível e read-only.

### US3 — Montar o laudo e emitir parecer (P1)
O Auditor lança infrações (pelo picker da Matriz MBEDV ou aceitando marcadores das trilhas), ajusta início/fim, e aprova/reprova. O sistema valida a coerência entre o laudo e o veredito (pontuação ≤10 = apto) antes de confirmar. **Testável:** Aprovar com laudo >10 pts é bloqueado com aviso; confirmar coerente registra e avança para o próximo exame.

### US4 — Consultar a ficha da infração (P2)
Para cada infração, o Auditor abre a ficha MBEDV (definição, como a IA detecta, enquadramento CTB+MBEDV). **Testável:** abrir o detalhe/ficha mostra artigo CTB, gravidade, peso e seções normativas.

### US5 — Alternar tema e ver telemetria (P3)
O Auditor alterna entre tema Claro e Grafite (persistente) e o Supervisor acompanha acessos/tempo de vídeo/veredito por exame. **Testável:** o toggle troca o tema e mantém após reload; o SupervisorModal lista a telemetria por OS.

### Edge cases
- Exame **interrompido**: trilha mostra região de interrupção; sem pontuação calculada.
- Exame sem divergência (concordância): trilhas alinhadas; laudo herda concordância.
- ValBot ainda processando: trilha ValBot vazia com aviso.

## Requirements (Functional)
- **FR-01:** Tela única imersiva (sem lista+detalhe separados); seleção de OS por dropdown no topo + navegação por teclado (`[`/`]`).
- **FR-02:** Player de vídeo com play/pause, ±5s, seek por clique, atalhos (espaço/setas); na 1ª revisão o avanço libera conforme o auditor assiste (gating).
- **FR-03:** Timeline com 3 trilhas (TechPrático, ValBot, Auditor), régua de timecode, marcadores por gravidade, playhead, região de divergência e de interrupção; o laudo do Auditor permite arrastar início/fim do marcador.
- **FR-04:** Comparação TP×ValBot (resultado, pontuação, infrações) com destaque de divergência.
- **FR-05:** Laudo do Comitê de IA exibido **read-only** (constitution §I — Comitê explica, não decide).
- **FR-06:** Lançamento de infração via Matriz MBEDV (busca, filtro por gravidade, sugestões pela IA no trecho, ficha do procedimento) e via aceite de marcadores das trilhas.
- **FR-07:** Parecer Aprovar/Reprovar com **validação de coerência** laudo×veredito antes de confirmar; ao confirmar, registra o laudo e avança.
- **FR-08:** Pontuação fiel à Res. 1.020/2025: leve=1/média=2/grave=4/gravíssima=6; reprovado se houver gravíssima OU soma >10 (constitution §V).
- **FR-09:** Toda infração é fundamentada em artigo CTB + ficha MBEDV (constitution §III — explicabilidade).
- **FR-10:** Tema Claro (default) e Grafite intercambiáveis, persistidos.
- **FR-INFRA:** N/A de scheduling/keys/locks — feature de UI stateless (estado em localStorage; persistência de parecer via API quando ligada).

## Key Entities
- **OS/Exame**: RENACH, candidato, examinador, categoria, duração, status (divergência/processando/finalizado/interrompido).
- **Avaliação (TP e ValBot)**: resultado, pontuação, infrações (códigos CTB), confiança (ValBot).
- **Marcador/Infração**: código (Art. CTB), início, duração, gravidade, fonte (TP/VB/Auditor).
- **Laudo do Auditor**: infrações confirmadas + fundamentação + veredito.
- **Laudo do Comitê**: causas, recomendação (read-only).

## Success Criteria
- **SC-01:** O Auditor conclui a revisão de uma OS (escolher → assistir → parecer) sem sair da tela.
- **SC-02:** Aprovar/Reprovar incoerente com a pontuação é impedido em 100% dos casos.
- **SC-03:** Toda infração exibida tem artigo CTB + ficha MBEDV associados.
- **SC-04:** A escolha de tema persiste entre sessões.
- **SC-05:** A tela renderiza e é operável a partir do `/fila-auditor` sem erros de tipo (typecheck verde) e build de produção sem erros.

## Fora de escopo
- Dados reais de OS (hoje mock; wiring a `GET /api/os` etc. é a v2).
- Decisão final do Supervisor (nível 4) — placeholder.
