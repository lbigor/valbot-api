# Câmera INTERNA — Cat B (alinhado ao MBEDV/2026)

## O que esperar nesta câmera

Painel + volante + tórax + rosto do candidato. Mostra: cinto diagonal cruzando
ombro→quadril, mãos no volante, alavanca de seta/marcha, painel (velocímetro,
LED verde do pisca, alerta sonoro de cinto), pé direito ocasional nos pedais
quando câmera tem ângulo baixo, rosto e olhar do candidato.

## Faltas MBEDV primariamente detectadas aqui

### Art. 169 — Dirigir sem atenção [Leve, 1 pt]
**Descrição MBEDV:** "Dirigir sem atenção ou sem os cuidados indispensáveis à
segurança." No exame, é desatenção/distração/falta de foco.

**Condutas que pontuam (na visão da INTERNA):**
1. Candidato NÃO olha o painel de instrumentos em momentos críticos.
2. Candidato NÃO olha para direita ou esquerda ao sair com o veículo.
3. Candidato mantém a porta do veículo aberta/semiaberta durante o percurso.
4. Engrenar/utilizar marchas de maneira incorreta durante o percurso (audível
   também: ralo metálico).

**Condutas que NÃO pontuam (descartar mesmo se parecer):**
- Tossir/espirrar.
- Conversar brevemente.
- Conduta que se enquadra em outra ficha específica (use a específica).

### Art. 196 — Não sinalizar com antecedência manobra [**Grave, 4 pts**]
**Descrição MBEDV:** "Deixar de indicar com antecedência, mediante gesto
regulamentar de braço ou luz indicadora de direção, o início da marcha, a
manobra de parar o veículo, a mudança de direção ou de faixa de circulação."

**Condutas que pontuam:**
1. Veículo parado/estacionado, candidato inicia marcha **sem sinalizar**.
2. Estacionado/parado, sinaliza início de marcha em uma direção, mas **inicia
   pelo lado oposto**.
3. Sinaliza vai parar/estacionar em uma direção, mas para/estaciona no oposto.
4. **Não sinaliza com antecedência** as manobras de: conversão à E/D, retorno
   à E/D, entrada/saída de lote lindeiro.
5. Sinaliza mudança **contrária à sinalizada** (acendeu seta E mas foi pra D).
6. Não sinaliza mudança de faixa, inclusive em ultrapassagem.

**Condutas que NÃO pontuam:**
1. Conversão em entroncamento com **única direção a seguir** (não há escolha).
2. Saída de lote lindeiro quando a via é de **mão única**.
3. Manobra proibida → use a ficha específica da proibição, não Art. 196.

> **🚨 GUARD ANTI-FALSO-POSITIVO — REGRA DE OURO: A SETA SÓ SE VALIDA POR ÁUDIO.**
>
> O canal VISUAL (rotação do volante, mão na alavanca, ausência de reflexo
> do pisca, LED do painel) **NUNCA** estabelece esta falta sozinho — serve só
> pra LOCALIZAR a manobra. A confirmação da seta é SEMPRE e SOMENTE pelo áudio.
>
> **PASSO 0 — PRÉ-REQUISITO ABSOLUTO (checar ANTES de qualquer coisa):**
> precisa existir faixa de áudio NÍTIDA e avaliável na janela da manobra. Se o
> vídeo está mudo, sem trilha de áudio, ou o áudio é inaudível/abafado/ruidoso
> a ponto de você NÃO conseguir afirmar com certeza se o relé tocou ou não →
> **PARE: marque `nao_detectada` (ou `pendente_audio`). NUNCA `detectada`.**
> Áudio ausente ≠ seta ausente. Ausência de evidência não é evidência de falta.
>
> O relé sonoro do painel ("tic-tac" cíclico de ~1-2Hz) é DIAGNÓSTICO
> DEFINITIVO de sinalização. **Antes de marcar Art. 196:**
>
> 1. RE-ESCUTE os 5s ANTES e os 3s DURANTE a rotação do volante.
> 2. Se há QUALQUER som rítmico periódico de ~1-2Hz nesse intervalo —
>    tic-tac, click, tique cíclico, mesmo abafado — **o motorista
>    SINALIZOU. NÃO marque.** Mínimo de 3 ciclos consecutivos.
> 3. Só marque `detectada` quando o áudio é CLARO **E** (a) comprovadamente
>    NÃO há relé em TODA a janela, **OU** (b) o EXAMINADOR verbaliza
>    ("esqueceu a seta", "não deu seta", "faltou sinalizar").
> 4. **Ausência VISUAL da luz JAMAIS basta** — o reflexo do pisca pode estar
>    fora dos 4 quadrantes do layout 2×2. Áudio é o ÚNICO canal autoritativo.
>
> **Informações complementares MBEDV:** "A sinalização indicadora de
> direção deve permanecer acionada durante TODA a execução da manobra.
> Caso o dispositivo desarme antes da conclusão, o candidato deverá
> reativá-lo imediatamente." → desarmar e não reativar TAMBÉM pontua
> Art. 196.

### Art. 195 — Desobedecer ordens da autoridade/examinador [Grave, 4 pts]
**Descrição MBEDV:** "Desobedecer às ordens emanadas da autoridade competente
de trânsito ou de seus agentes."

**Condutas que pontuam:**
1. Candidato desobedece ordem da autoridade de trânsito + examinadores
   (gesto ou verbal/sonora).

**Condutas que NÃO pontuam:**
- Reduzir velocidade desobedecendo agente que controla com sinais sonoros
  ou gestos → ficha específica: Art. 220, II.

**Detecção INTERNA:** o áudio do examinador é primário. Capture transcript
literal ("vire à esquerda", "pare aqui", "encoste") + correlate com a
reação do candidato. Se o candidato **continuou reto após "pare"** → Art. 195.

### Cinto de segurança — **NÃO existe mais como falta no MBEDV/2026**
**ANTES (v25):** marcávamos como "eliminatória" — não tem mais.

A nova rubrica MBEDV/2026 não lista cinto como falta avaliável. Conduzir
sem cinto continua sendo infração de trânsito (Art. 167 CTB administrativo)
mas **não é falta avaliada em exame prático** nesta rubrica. **NÃO MARQUE
mais infração de cinto no JSON.**

(Se o operador humano discordar, registre como `verificacao_examinador:
diverge` baseado em anotação de referência — mas não invente o ID.)

## NÃO detectar aqui (use outra câmera)

- Sinalização da via, semáforos (use FRONTAL — Art. 208)
- Posicionamento em relação ao meio-fio direito (use LATERAL_DIREITA)
- Baliza/estacionamento (não é mais avaliado em isolamento — vide MBEDV)

## Sinais autoritativos no painel (vista interna)

| Sinal | Diagnóstico |
|---|---|
| Tic-tac cíclico ~1-2Hz no áudio | Pisca/seta acionado. Desqualifica Art. 196. |
| LED verde do pisca acendendo cíclico | Confirmação visual de sinalização. |
| Velocímetro estável legível | Pode informar excesso de velocidade. |
