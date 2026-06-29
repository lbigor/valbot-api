# Câmera FRONTAL — Cat B (alinhado ao MBEDV/2026)

## O que esperar nesta câmera

Vista do para-brisa do candidato. Mostra a via à frente: faixas, semáforos,
placas, cruzamentos, contramão, veículos vindo, distância pro veículo da
frente, pedestres atravessando, pista molhada/seca. Movimento horizontal
contínuo enquanto o carro anda.

## Faltas MBEDV primariamente detectadas aqui

### Art. 170 — Dirigir ameaçando pedestres atravessando [Gravíssima, 6 pts]
**Descrição MBEDV:** Conduta deliberada de intimidar, assustar ou forçar a
travessia do pedestre. Intencionalidade é o ponto fundamental.

**Condutas que pontuam:**
1. Acelera junto ao semáforo, ameaçando arrancar independente da fase
   semafórica.
2. Muda repentinamente o rumo do veículo em direção ao pedestre.
3. Acelera bruscamente o veículo em direção ao pedestre na faixa de
   travessia.

**Condutas que NÃO pontuam:**
- Quando há simples intenção de não dar preferência ao pedestre → use
  enquadramento específico (NÃO use Art. 170).
- Se a situação é decorrente de falta de atenção (e não dolosa) → aplicar
  Art. 169 (Leve 1 pt) em vez de Art. 170.

### Art. 175 — Manobra perigosa (arrancada/derrapagem/frenagem com deslizamento) [Gravíssima, 6 pts]
**Descrição MBEDV:** Demonstrar ou exibir destreza ou audácia, realizando
manobras que colocam em risco a si e demais usuários. Intencionalidade
exibicionista.

**Condutas que pontuam:**
1. Arrancada brusca: acelera de forma exagerada e repentina, **pneu
   patinando**.
2. Derrapagem: deslizamento lateral do veículo em curva ou mudança de
   direção, de forma intencional.
3. Frenagem com deslizamento ou arrastamento de pneus: freia abruptamente,
   rodas travam, pneus arrastam no pavimento (marcas/ruído alto) **sem
   necessidade de emergência**.

**Condutas que NÃO pontuam:**
1. Imperícia do candidato (não-intencional) → Art. 169 (Leve).
2. Manobra realizada para evitar sinistro em situação não causada pelo
   candidato.

### Art. 183 — Parar sobre faixa de pedestres na mudança de sinal [Média, 2 pts]
**Descrição MBEDV:** Veículo imobilizado sobre a área demarcada para
travessia de pedestres ao se deparar com semáforo amarelo/vermelho.

**Condutas que pontuam:**
- Candidato imobiliza o veículo (totalidade ou parte) sobre a faixa de
  pedestres no fechamento do semáforo. Deveria ter parado antes da faixa
  (na linha de retenção).

**Condutas que NÃO pontuam:**
- Veículo efetuando embarque/desembarque sobre a faixa → enquadramento
  específico, não Art. 183.

**Pré-requisitos pra detectar:** semáforo presente E faixa demarcada
visível na FRONTAL.

### Art. 186-I — Contramão em vias de duplo sentido [Grave, 4 pts]
**Condutas que pontuam:**
1. Avança em contramão em **local não autorizado**.
2. Demora tempo SUPERIOR ao necessário para executar ultrapassagem.
3. Não dá preferência ao veículo em sentido oposto.

**Condutas que NÃO pontuam:**
- Ultrapassagem em local autorizado, em tempo razoável, com respeito à
  preferência do sentido oposto.

### Art. 186-II — Contramão em via de sentido único [Gravíssima, 6 pts]
**Condutas que pontuam:**
- Candidato conduz em sentido oposto à via com sentido único de direção.

**Condutas que NÃO pontuam:**
- Conduzir no sentido correto da via de sentido único.
- Realizar manobra em marcha à ré em sentido contrário ao da via de
  sentido único **por tempo NÃO superior ao necessário**.

### Art. 191 — Forçar passagem em ultrapassagem [Gravíssima, 6 pts]
**Condutas que pontuam:**
1. Realizando ultrapassagem (mesmo em local permitido), **força a passagem
   entre veículos circulando em sentidos opostos e próximos a passar um
   pelo outro**.
2. Ao iniciar a operação de ultrapassagem (mesmo em local permitido), força
   a passagem entre veículos em sentidos opostos, **mesmo sem completar**.

**Condutas que NÃO pontuam:**
- Ultrapassagem proibida sem forçar passagem → use Art. 186-I (contramão).

### Art. 192 — Não guardar distância de segurança [Grave, 4 pts]
**Condutas que pontuam:**
1. Não mantém distância frontal/lateral entre veículo e demais ou bordo da
   pista, colocando em risco segurança (considerando velocidade, clima,
   geometria).
2. Não mantém distância lateral de veículos parados/estacionados (vide
   geometria).
3. Não mantém distância frontal em **paradas obrigatórias ou semafóricas**
   (encosta no carro da frente).

**Condutas que NÃO pontuam:**
- Bicicleta sem distância → ficha específica Art. 201.
- Transitar pela contramão → Art. 186.
- Forçar passagem → Art. 191.
- Ultrapassagem pela contramão → Art. 203, I-V.

### Art. 193 — Transitar em calçadas/passeios/ciclovias [Gravíssima, 6 pts]
**Condutas que pontuam (a roda transita APOIADA SOBRE a superfície do passeio):**
1. Transitar (total ou parcial) sobre calçada ou passeio.
2. Transitar no avanço do passeio delimitado por sinalização/elemento físico.
3. Transitar sobre calçada/passeio sinalizado como espaço partilhado.

**Condutas que NÃO pontuam:**
- Encostar/raspar/subir MOMENTANEAMENTE o meio-fio/guia em conversão, baliza ou
  estacionamento → é manobra, não trânsito sobre calçada. Avalie Art. 181 ou
  192, NUNCA 193.
- Retorno passando sobre calçada → use Art. 206, III (ficha específica).

## NÃO detectar aqui (use outra câmera)

- Cinto (não existe mais no MBEDV)
- Pisca/seta (use INTERNA — Art. 196 com GUARD anti-falso-positivo)
- Mão no volante (use INTERNA)
- Meio-fio direito tocado (use LATERAL_DIREITA)
- Marcha à ré (use TRASEIRA_ESQ — Art. 194)

## Heurística de qualidade do canal

Se FRONTAL está borrada, com chuva forte ou luminosidade extrema (entardecer
ofuscante), marque `audio_quality_flag` de infrações dependentes do visual
frontal pra `pendente_infraestrutura`.
