/* ============================================================================
   ValBot — Painel do Auditor · Matriz Nacional de Regras (MBEDV / Res. 1.020/2025)
   DADOS, nao UI. Porte fiel de .design-ref/painel-matriz.jsx (window.MBEDV_RULES).
   ============================================================================ */
import type { Rule } from "./painel-data";

export const MBEDV_RULES: Rule[] = [
{
"code": "Art. 169",
"art": "169",
"grav": "leve",
"pontos": 1,
"nome": "Dirigir sem atenção ou sem os cuidados indispensáveis à segurança.",
"desc": "No exame de direção veicular, a atenção e cuidados indispensáveis a segurança são caracterizados por foco e atenção durante todo o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "1. Quando o comportamento do condutor do veículo demonstrar desatenção ou comprometer a segurança do trânsito e desde que não exista enquadramento específico; 2. Quando o candidato não olhar o painel de instrumentos; ou 3. Quando o candidato não olhar para direita ou esquerda ao sair com veículo; 4. Deixar de levantar o cavalete lateral quando iniciado o exame; 5. Manter a porta do veículo aberta ou semiaberta durante o percurso do exame ou parte dele. 6. Executar o percurso do exame, no todo ou parte dele, sem estar o freio de mão inteiramente livre; 7. Engrenar ou utilizar as marchas de maneira incorreta, durante o percurso.",
"naoPontua": "1. Quando a conduta se enquadrar em uma conduta específica; 2. Tossir/espirrar; ou 3.",
"definicoes": "Conversar brevemente. Essa infração caracteriza-se por um comportamento do condutor que, por descuido, distração ou falta de foco, não mantém o nível de atenção e cautela necessários para operar um veículo automotor de forma segura no ambiente de trânsito.",
"checks": "1. Quando o comportamento do condutor do veículo demonstrar desatenção ou comprometer a segurança do trânsito e desde que não exista enquadramento específico; 2. Quando o candidato não olhar o painel de instrumentos; ou 3. Quando o candidato não olhar para direita ou esquerda ao sair com veículo; 4. Deixar de levantar o cavalete lateral quando iniciado o exame; 5. Manter a porta do veículo aberta ou semiaberta durante o percurso do exame ou parte dele. 6. Executar o percurso do exame, no todo ou parte dele, sem estar o freio de mão inteiramente livre; 7. Engrenar ou utilizar as marchas de maneira incorreta, durante o percurso. 1. Quando a conduta se enquadrar em uma conduta específica; 2. Tossir/espirrar; ou 3. Conversar brevemente. Essa infração caracteriza-se por um comportamento do condutor que, por descuido, distração ou falta de foco, não mantém o nível de atenção e cautela necessários para operar um veículo automotor de forma segura no ambiente de trânsito.",
"compl": "O rol de situações descritas no campo “quando autuar” é meramente exemplificativo e não exaure e nem exclui outras situações que impliquem dirigir ameaçando os demais veículos.",
"enquad": {
"art": "169",
"ctb": "CTB Art. 169",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 170",
"art": "170",
"grav": "gravissima",
"pontos": 6,
"nome": "Dirigir ameaçando os pedestres que estejam atravessando a via pública.",
"desc": "Ocorre quando o condutor age com a intenção deliberada de intimidar, assustar ou forçar a travessia do pedestre, durante a realização do percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Condutor que intencionalmente intimida pedestre que esteja atravessando a via: 1. com o intuito de assustar, intimidar, incutir medo ou ameaçar o pedestre ou apressar a sua travessia; 2. acelera o veículo junto ao semáforo, ameaçando arrancar, independentemente da fase semafórica; ou 3. muda repentinamente o rumo do veículo em direção ao pedestre. Quando houver a simples intenção de não dar a preferência de passagem a pedestre, utilizar enquadramentos específicos. Para que a autuação seja válida, é essencial que o examinador registre a intencionalidade e o tipo de ameaça observada. Sendo obrigado descrever a conduta na pauta do exame. (ex: \"Condutor acelerou bruscamente o veículo em direção ao pedestre na faixa de travessia\"). Quando se percebe que a situação é decorrente de falta de atenção, deve ser aplicada a penalidade do art. 169.",
"checks": "Condutor que intencionalmente intimida pedestre que esteja atravessando a via: 1. com o intuito de assustar, intimidar, incutir medo ou ameaçar o pedestre ou apressar a sua travessia; 2. acelera o veículo junto ao semáforo, ameaçando arrancar, independentemente da fase semafórica; ou 3. muda repentinamente o rumo do veículo em direção ao pedestre. Quando houver a simples intenção de não dar a preferência de passagem a pedestre, utilizar enquadramentos específicos. Para que a autuação seja válida, é essencial que o examinador registre a intencionalidade e o tipo de ameaça observada. Sendo obrigado descrever a conduta na pauta do exame. (ex: \"Condutor acelerou bruscamente o veículo em direção ao pedestre na faixa de travessia\"). Quando se percebe que a situação é decorrente de falta de atenção, deve ser aplicada a penalidade do art. 169.",
"compl": "O rol de situações descritas no campo “quando autuar” é meramente exemplificativo e não exaure e nem exclui outras situações que impliquem dirigir ameaçando os demais usuários da via.",
"enquad": {
"art": "170",
"ctb": "CTB Art. 170",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 170 (2)",
"art": "170",
"grav": "gravissima",
"pontos": 6,
"nome": "Dirigir ameaçando os demais veículos.",
"desc": "Ocorre quando o condutor utiliza o veículo para intimidar, bloquear ou colocar em risco outros motoristas, durante o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "1. Mudar repentinamente o rumo do veículo em direção a outro, ameaçando colidir lateralmente ou tomar sua frente de forma perigosa; 2. Perseguir outro veículo com a intenção de interceptá-lo ou bloqueá-lo; ou 3. Acelerar o veículo parado junto a outro no semáforo, ameaçando arrancar com a finalidade de intimidar ou apressar o condutor à frente.",
"naoPontua": "1. Quando houver a simples intenção de não dar a preferência ou prioridade de passagem aos demais veículos, utilizar enquadramentos específicos. 2.",
"definicoes": "Condutor que dirige ameaçando os pedestres, utilizar enquadramento específico A infração é caracterizada pela conduta intencional (dolosa) do motorista em utilizar o veículo como instrumento de intimidação ou agressão no trânsito, colocando outros veículos e seus ocupantes em risco.",
"checks": "1. Mudar repentinamente o rumo do veículo em direção a outro, ameaçando colidir lateralmente ou tomar sua frente de forma perigosa; 2. Perseguir outro veículo com a intenção de interceptá-lo ou bloqueá-lo; ou 3. Acelerar o veículo parado junto a outro no semáforo, ameaçando arrancar com a finalidade de intimidar ou apressar o condutor à frente. 1. Quando houver a simples intenção de não dar a preferência ou prioridade de passagem aos demais veículos, utilizar enquadramentos específicos. 2. Condutor que dirige ameaçando os pedestres, utilizar enquadramento específico A infração é caracterizada pela conduta intencional (dolosa) do motorista em utilizar o veículo como instrumento de intimidação ou agressão no trânsito, colocando outros veículos e seus ocupantes em risco.",
"compl": "O rol de situações descritas no campo “quando autuar” é meramente exemplificativo e não exaure e nem exclui outras situações que impliquem dirigir ameaçando os demais veículos.",
"enquad": {
"art": "170",
"ctb": "CTB Art. 170",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 171",
"art": "171",
"grav": "media",
"pontos": 2,
"nome": "Usar o veículo para arremessar, sobre os pedestres, água ou detritos.",
"desc": "O ato infracional consiste em lançar, propositalmente ou por negligência grave, água ou quaisquer detritos (lama, cascalho, lixo) que se encontrem na via, atingindo um pedestre que esteja na calçada ou atravessando, ou outro veículo, durante o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "1. Possibilidade de desvio/redução: O condutor, existindo condições de desviar da poça d'água ou reduzir a velocidade para evitar o arremesso, não o faz. 2. Mudança de curso: O condutor muda o curso do veículo especificamente para passar sobre a poça ou detritos, com o objetivo claro de arremessá-los.",
"naoPontua": "1. Substância arremessada em outros veículos, utilizar enquadramento específico 2.",
"definicoes": "Atirar do veículo, ou abandonar na via, objetos ou substâncias, utilizar enquadramento específico. A infração pune a falta de civilidade e o desrespeito dos condutores ao utilizar o veículo para sujar ou molhar outros usuários da via.",
"checks": "1. Possibilidade de desvio/redução: O condutor, existindo condições de desviar da poça d'água ou reduzir a velocidade para evitar o arremesso, não o faz. 2. Mudança de curso: O condutor muda o curso do veículo especificamente para passar sobre a poça ou detritos, com o objetivo claro de arremessá-los. 1. Substância arremessada em outros veículos, utilizar enquadramento específico 2. Atirar do veículo, ou abandonar na via, objetos ou substâncias, utilizar enquadramento específico. A infração pune a falta de civilidade e o desrespeito dos condutores ao utilizar o veículo para sujar ou molhar outros usuários da via.",
"compl": "Não há.",
"enquad": {
"art": "171",
"ctb": "CTB Art. 171",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 171 (2)",
"art": "171",
"grav": "media",
"pontos": 2,
"nome": "Usar o veículo para arremessar, sobre os veículos, água ou detritos.",
"desc": "No exame de direção veicular, a pontuação ocorre quando o condutor utiliza o seu veículo para projetar água, lama ou detritos que estão na pista de rolamento contra outro veículo, sujando-o e, potencialmente, colocando-o em risco.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato",
"pontua": "1. Existindo condições de desviar ou reduzir a velocidade, não o faz; ou 2. mudando o curso do veículo para arremessá-las.",
"naoPontua": "1. Substância arremessada em pedestres, utilizar enquadramento específico; ou 2.",
"definicoes": "Atirar do veículo, ou abandonar na via, objetos ou substâncias, utilizar enquadramento específico. O ato é uma infração de desrespeito e falta de civilidade que pode, inclusive, causar risco ou dano material ao outro veículo. Assim como na situação com pedestres, o ponto fundamental é a intencionalidade ou negligência grave do condutor.",
"checks": "Condutor que intencionalmente atinge outro veículo com água ou detritos que se encontram na pista de rolamento: 1. Existindo condições de desviar ou reduzir a velocidade, não o faz; ou 2. mudando o curso do veículo para arremessá-las. 1. Substância arremessada em pedestres, utilizar enquadramento específico; ou 2. Atirar do veículo, ou abandonar na via, objetos ou substâncias, utilizar enquadramento específico. O ato é uma infração de desrespeito e falta de civilidade que pode, inclusive, causar risco ou dano material ao outro veículo. Assim como na situação com pedestres, o ponto fundamental é a intencionalidade ou negligência grave do condutor.",
"compl": "Não há.",
"enquad": {
"art": "171",
"ctb": "CTB Art. 171",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 172",
"art": "172",
"grav": "media",
"pontos": 2,
"nome": "Atirar do veículo na via objetos ou substâncias.",
"desc": "No exame de direção veicular, é o ato de arremessar qualquer objeto ou substância para fora do veículo, estando ele em movimento ou parado, durante todo o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "1. Consiste em arremessar, lançar ou descartar qualquer objeto ou substância para fora do veículo, atingindo a superfície da via (pista, calçada, acostamento etc.). O objetivo da norma é garantir que a via permaneça livre de obstáculos ou perigos. 2. Refere-se ao descarte ativo, geralmente feito através das janelas, portas ou teto do veículo. Quando a substância for atirada por passageiros de transporte coletivo.",
"naoPontua": "1. Via: superfície por onde transitam veículos, pessoas e animais, compreendendo a pista, a calçada, o acostamento, ilha e canteiro central. 2.",
"definicoes": "Exemplos de objetos e substâncias: cigarro, papel, resto de alimento, água, lata de bebida (cerveja, suco, refrigerante, água etc.), lixo, entulho etc.",
"checks": "1. Consiste em arremessar, lançar ou descartar qualquer objeto ou substância para fora do veículo, atingindo a superfície da via (pista, calçada, acostamento etc.). O objetivo da norma é garantir que a via permaneça livre de obstáculos ou perigos. 2. Refere-se ao descarte ativo, geralmente feito através das janelas, portas ou teto do veículo. Quando a substância for atirada por passageiros de transporte coletivo. 1. Via: superfície por onde transitam veículos, pessoas e animais, compreendendo a pista, a calçada, o acostamento, ilha e canteiro central. 2. Exemplos de objetos e substâncias: cigarro, papel, resto de alimento, água, lata de bebida (cerveja, suco, refrigerante, água etc.), lixo, entulho etc.",
"compl": "Não há.",
"enquad": {
"art": "172",
"ctb": "CTB Art. 172",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 172 (2)",
"art": "172",
"grav": "media",
"pontos": 2,
"nome": "Abandonar na via objetos ou substâncias.",
"desc": "No exame de direção veicular, é o ato de abandonar na via e refere-se a deixar ou largar objetos ou substâncias na superfície da via (pista de rolamento, acostamento, calçada etc. É uma conduta passiva, mas intencional, que cria um obstáculo ou perigo para outros usuários, durante todo o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante o exame.",
"pontua": "",
"naoPontua": "",
"definicoes": "Com o veículo estacionado ou parado e o candidato deixar objeto ou substância na via, saindo do local. É importante diferenciar esta infração de outras condutas: Derrame de carga: se a infração for o derramamento, lançamento ou arrastamento de carga, o enquadramento correto é o art. 231, inciso II do CTB. Vazamento acidental: vazamentos de óleo, combustível ou outros líquidos devido a falha mecânica pode configurar outras infrações relacionadas ao estado de conservação do veículo. O examinador deve descrever qual objeto ou substância foi abandonado e onde na pauta do exame.",
"checks": "Com o veículo estacionado ou parado e o candidato deixar objeto ou substância na via, saindo do local. É importante diferenciar esta infração de outras condutas: Derrame de carga: se a infração for o derramamento, lançamento ou arrastamento de carga, o enquadramento correto é o art. 231, inciso II do CTB. Vazamento acidental: vazamentos de óleo, combustível ou outros líquidos devido a falha mecânica pode configurar outras infrações relacionadas ao estado de conservação do veículo. O examinador deve descrever qual objeto ou substância foi abandonado e onde na pauta do exame.",
"compl": "Não há.",
"enquad": {
"art": "172",
"ctb": "CTB Art. 172",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 175",
"art": "175",
"grav": "gravissima",
"pontos": 6,
"nome": "Utilizar-se de veículo para demonstrar ou exibir manobra perigosa, mediante arrancada brusca, derrapagem ou frenagem com deslizamento ou arrastamento de pneus.",
"desc": "No exame de direção veicular, o cerne da infração é a intencionalidade do condutor em demonstrar ou exibir destreza ou audácia, realizando manobras que, por sua natureza, colocam em risco a segurança de si próprio e dos demais usuários da via, durante o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "1. Utilizar-se de veículo para demonstrar ou exibir manobra perigosa. 2. Arrancada brusca: acelerar de forma exagerada e repentina, muitas vezes fazendo o pneu patinar. 3. Derrapagem: deslizamento lateral do veículo em uma curva ou mudança de direção, de forma intencional. 4. Frenagem com deslizamento ou arrastamento de pneus: frear de maneira abrupta e proposital, a ponto de as rodas travarem e os pneus arrastarem no pavimento, deixando marcas ou emitindo ruído alto, sem que haja necessidade de emergência.",
"naoPontua": "1. Quando se trata por imperícia por parte do candidato, deve ser enquadrado no art. 169. 2.",
"definicoes": "Quando se dá para evitar sinistros, em situação não causada pelo candidato. Demonstrar: ato de realizar a manobra com a intenção de mostrar ou provar algo, ainda que a um grupo pequeno ou a si mesmo. Exibir: ato de realizar a manobra com o objetivo de ostentar, alardear ou chamar a atenção de um público (mesmo que casual). Via: superfície por onde transitam veículos, pessoas e animais, compreendendo a pista, a calçada, o acostamento, ilha e canteiro central. Essa infração trata-se de ação exibicionista não organizada. O ato de utilizar pressupõe a não existência de outros veículos envolvidos e/ou espectadores. O examinador deve detalhar, de forma clara, a manobra realizada e a intenção de exibição, relatar na pauta do exame.",
"checks": "1. Utilizar-se de veículo para demonstrar ou exibir manobra perigosa. 2. Arrancada brusca: acelerar de forma exagerada e repentina, muitas vezes fazendo o pneu patinar. 3. Derrapagem: deslizamento lateral do veículo em uma curva ou mudança de direção, de forma intencional. 4. Frenagem com deslizamento ou arrastamento de pneus: frear de maneira abrupta e proposital, a ponto de as rodas travarem e os pneus arrastarem no pavimento, deixando marcas ou emitindo ruído alto, sem que haja necessidade de emergência. 1. Quando se trata por imperícia por parte do candidato, deve ser enquadrado no art. 169. 2. Quando se dá para evitar sinistros, em situação não causada pelo candidato. Demonstrar: ato de realizar a manobra com a intenção de mostrar ou provar algo, ainda que a um grupo pequeno ou a si mesmo. Exibir: ato de realizar a manobra com o objetivo de ostentar, alardear ou chamar a atenção de um público (mesmo que casual). Via: superfície por onde transitam veículos, pessoas e animais, compreendendo a pista, a calçada, o acostamento, ilha e canteiro central. Essa infração trata-se de ação exibicionista não organizada. O ato de utilizar pressupõe a não existência de outros veículos envolvidos e/ou espectadores. O examinador deve detalhar, de forma clara, a manobra realizada e a intenção de exibição, relatar na pauta do exame.",
"compl": "Não há.",
"enquad": {
"art": "175",
"ctb": "CTB Art. 175",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 181",
"art": "181",
"grav": "gravissima",
"pontos": 1,
"nome": "Estacionar veículo: I - nas esquinas e a menos de cinco metros do bordo do alinhamento da via transversal; II - afastado da guia da calçada (meio-fio) de cinquenta centímetros a um metro; III - afastado da guia da calçada (meio-fio) a mais de um metro; IV - em desacordo com as posições estabelecidas no CTB; V - na pista de rolamento das estradas, das rodovias, das vias de trânsito rápido e das vias dotadas de acostamento; VI - junto ou sobre hidrantes de incêndio, registro de água ou tampas de poços de visita de galerias subterrâneas, desde que devidamente identificados, conforme especificação do Contran; VII - nos acostamentos, salvo motivo de força maior; VIII - no passeio ou sobre faixa destinada a pedestre, sobre ciclovia ou ciclofaixa, bem como nas ilhas, refúgios, ao lado ou sobre canteiros centrais, divisores de pista de rolamento, marcas de canalização, gramados ou jardim público; IX - onde houver guia de calçada (meio-fio) rebaixada destinada à entrada ou saída de veículos; X - impedindo a movimentação de outro veículo; XI - ao lado de outro veículo em fila dupla; XII - na área de cruzamento de vias, prejudicando a circulação de veículos e pedestres; XIII - onde houver sinalização horizontal delimitadora de ponto de embarque ou desembarque de passageiros de transporte coletivo ou, na inexistência desta sinalização, no intervalo compreendido entre dez metros antes e depois do marco do ponto; XIV - nos viadutos, pontes e túneis; XV - na contramão de direção; XVI - em aclive ou declive, não estando devidamente freado e sem calço de segurança, quando se tratar de veículo com peso bruto total superior a 3.500 kg; XVII - em desacordo com as condições regulamentadas especificamente pela sinalização (placa - estacionamento regulamentado); XVIII - em locais e horários proibidos especificamente pela sinalização (placa - proibido estacionar); XIX - em locais e horários de estacionamento e parada proibidos pela sinalização (placa - proibido parar e estacionar); XX - nas vagas reservadas às pessoas com deficiência ou idosos, sem credencial que comprove tal condição;",
"desc": "No exame de direção veicular, a infração varia em gravidade conforme o potencial de risco e obstrução que o estacionamento indevido representa para o tráfego e a segurança. O estacionamento é definido",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Leve: estacionar afastado da guia (meio-fio) entre 50 cm e 1 metro (inciso II); estacionar em acostamentos, salvo motivo de força maior (inciso VII). Média: estacionar nas esquinas e a menos de 5 m do alinhamento da via transversal (inciso I); estacionar em desacordo com as posições estabelecidas (inciso IV); estacionar impedindo a movimentação de outro veículo (inciso X); estacionar na contramão de direção (inciso XV). Grave: estacionar afastado da guia (meio-fio) a mais de 1 m (inciso III); estacionar sobre faixa de pedestre, ciclovia ou calçada (passeio) (inciso VIII); estacionar em viadutos, pontes ou túneis (inciso XIV). Gravíssima: estacionar na pista de rolamento das rodovias, estradas ou vias de trânsito rápido (inciso V); Estacionar em vagas reservadas às pessoas com deficiência ou idosos, sem credencial (inciso XX). Quando se tratar de imobilização por falta de combustível, deve se enquadrar na falta do art. 180. Parada: imobilização do veículo com a finalidade e pelo tempo estritamente necessário para efetuar o embarque ou desembarque de passageiros. Estacionamento: imobilização do veículo por tempo superior ao necessário para o embarque ou desembarque de passageiros. Atentar aos incisos que necessitam de sinalização específica para sua configuração.",
"checks": "Leve: estacionar afastado da guia (meio-fio) entre 50 cm e 1 metro (inciso II); estacionar em acostamentos, salvo motivo de força maior (inciso VII). Média: estacionar nas esquinas e a menos de 5 m do alinhamento da via transversal (inciso I); estacionar em desacordo com as posições estabelecidas (inciso IV); estacionar impedindo a movimentação de outro veículo (inciso X); estacionar na contramão de direção (inciso XV). Grave: estacionar afastado da guia (meio-fio) a mais de 1 m (inciso III); estacionar sobre faixa de pedestre, ciclovia ou calçada (passeio) (inciso VIII); estacionar em viadutos, pontes ou túneis (inciso XIV). Gravíssima: estacionar na pista de rolamento das rodovias, estradas ou vias de trânsito rápido (inciso V); Estacionar em vagas reservadas às pessoas com deficiência ou idosos, sem credencial (inciso XX). Quando se tratar de imobilização por falta de combustível, deve se enquadrar na falta do art. 180. Parada: imobilização do veículo com a finalidade e pelo tempo estritamente necessário para efetuar o embarque ou desembarque de passageiros. Estacionamento: imobilização do veículo por tempo superior ao necessário para o embarque ou desembarque de passageiros. Atentar aos incisos que necessitam de sinalização específica para sua configuração.",
"compl": "Não há.",
"enquad": {
"art": "181",
"ctb": "CTB Art. 181",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 183",
"art": "183",
"grav": "media",
"pontos": 2,
"nome": "Parar o veículo sobre a faixa de pedestres na mudança de sinal luminoso.",
"desc": "No exame de direção veicular, configura-se quando o candidato para o veículo em cima da faixa de pedestres quando da mudança do sinal luminoso. Trata-se especificamente de um erro de conduta que compromete a segurança e o direito de passagem do pedestre nos cruzamentos controlados por semáforo, durante o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "A infração ocorre quando o condutor, ao se deparar com a iminência de fechamento do sinal (luz amarela ou vermelha), posiciona o veículo de tal forma que sua totalidade ou parte dele imobiliza-se sobre a área demarcada para a travessia de pedestres. Veículo efetuando embarque e desembarque sobre a faixa de pedestre, utilizar enquadramento específico. Parar o veículo: refere-se à imobilização do veículo. A infração é de parada proibida, e não de estacionamento, pois a imobilização não é voluntária ou prolongada, mas sim decorrente do trânsito no cruzamento. Sobre a faixa de pedestres: o local exato onde a infração se configura. A faixa de pedestres é a área demarcada na via, destinada à travessia de pedestres. Na mudança de sinal luminoso: o contexto temporal da infração. A manobra ou a parada que resulta na imobilização sobre a faixa ocorre quando o condutor deveria ter aguardado antes da faixa (na linha de retenção) para evitar a obstrução.",
"checks": "A infração ocorre quando o condutor, ao se deparar com a iminência de fechamento do sinal (luz amarela ou vermelha), posiciona o veículo de tal forma que sua totalidade ou parte dele imobiliza-se sobre a área demarcada para a travessia de pedestres. Veículo efetuando embarque e desembarque sobre a faixa de pedestre, utilizar enquadramento específico. Parar o veículo: refere-se à imobilização do veículo. A infração é de parada proibida, e não de estacionamento, pois a imobilização não é voluntária ou prolongada, mas sim decorrente do trânsito no cruzamento. Sobre a faixa de pedestres: o local exato onde a infração se configura. A faixa de pedestres é a área demarcada na via, destinada à travessia de pedestres. Na mudança de sinal luminoso: o contexto temporal da infração. A manobra ou a parada que resulta na imobilização sobre a faixa ocorre quando o condutor deveria ter aguardado antes da faixa (na linha de retenção) para evitar a obstrução.",
"compl": "Obrigatória a existência de semáforo e sinalização horizontal de faixa de travessia de pedestres.",
"enquad": {
"art": "183",
"ctb": "CTB Art. 183",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 184",
"art": "184",
"grav": "leve",
"pontos": 1,
"nome": "Transitar com o veículo: I - na faixa ou pista da direita, regulamentada como de circulação exclusiva para determinado tipo de veículo, exceto para acesso a imóveis lindeiros ou conversões à direita.",
"desc": "No exame de direção veicular a falta deverá ser anotada quando o candidato conduzir o veículo em local exclusivo a outra categoria ou espécie de veículo.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato circular com o veículo em faixa destinada a outros veículos. 1. Quando estiver acessando a imóveis; ou 2. realizando conversões à direita. O examinador deve verificar se a conduta foi por necessidade (conversão à direta ou acesso a algum local). Caso não seja, deve anotar a ocorrência na ficha de avaliação, aplicar a pontuação correspondente e não interromper o exame, salvo se a manobra gerar perigo iminente.",
"checks": "Quando o candidato circular com o veículo em faixa destinada a outros veículos. 1. Quando estiver acessando a imóveis; ou 2. realizando conversões à direita. O examinador deve verificar se a conduta foi por necessidade (conversão à direta ou acesso a algum local). Caso não seja, deve anotar a ocorrência na ficha de avaliação, aplicar a pontuação correspondente e não interromper o exame, salvo se a manobra gerar perigo iminente.",
"compl": "Não há.",
"enquad": {
"art": "184",
"ctb": "CTB Art. 184",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 184 (2)",
"art": "184",
"grav": "grave",
"pontos": 4,
"nome": "Transitar com o veículo: II - na faixa ou pista da esquerda regulamentada como de circulação exclusiva para determinado tipo de veículo.",
"desc": "No exame de direção veicular, a falta deverá ser anotada quando o candidato conduzir em faixa da esquerda em local exclusivo a outro tipo de veículo.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato circular com o veículo em faixa destinada outro tipo de veículo. 1. Quando estiver acessando a imóveis; ou 2. realizando conversões à esquerda. O examinador deve verificar se a conduta foi por necessidade (conversão à esquerda ou acesso a algum local). Caso não seja, deve anotar a ocorrência na ficha de avaliação, aplicar a pontuação correspondente e não interromper o exame, salvo se a manobra gerar perigo iminente.",
"checks": "Quando o candidato circular com o veículo em faixa destinada outro tipo de veículo. 1. Quando estiver acessando a imóveis; ou 2. realizando conversões à esquerda. O examinador deve verificar se a conduta foi por necessidade (conversão à esquerda ou acesso a algum local). Caso não seja, deve anotar a ocorrência na ficha de avaliação, aplicar a pontuação correspondente e não interromper o exame, salvo se a manobra gerar perigo iminente.",
"compl": "Não há.",
"enquad": {
"art": "184",
"ctb": "CTB Art. 184",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 184 (3)",
"art": "184",
"grav": "gravissima",
"pontos": 6,
"nome": "Transitar com o veículo: III - na faixa ou via de trânsito exclusivo, regulamentada com circulação destinada aos veículos de transporte público coletivo de passageiros, salvo casos de força maior e com autorização do poder público competente.",
"desc": "No exame de direção veicular a falta deverá ser anotada quando o candidato conduzir o veículo em local exclusivo ao transporte público de passageiros.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "",
"checks": "",
"compl": "Nesta infração é importante observarmos que o candidato de categoria D não deve conduzir em faixa destinada à uso exclusivo de ônibus, pois em que pese a equivalência de categoria, não estaria autorizado à circular naquele local.",
"enquad": {
"art": "184",
"ctb": "CTB Art. 184",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 185",
"art": "185",
"grav": "media",
"pontos": 2,
"nome": "Quando o veículo estiver em movimento, deixar de conservá- lo: I - na faixa a ele destinada pela sinalização de regulamentação, exceto em situações de emergência.",
"desc": "No exame de direção veicular, a falta deverá ser anotada quando o candidato tiver percurso determinado a cumprir e deixar de conduzir em faixa destinada a circulação.",
"categorias": "ACC, A B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "",
"checks": "",
"compl": "É possível ao órgão ou entidade determinar percurso a ser utilizado pelo candidato, caso o candidato não conduza no percurso determinado, deverá ser anotada esta falta, a exceção se dá em casos de emergência.",
"enquad": {
"art": "185",
"ctb": "CTB Art. 185",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 185 (2)",
"art": "185",
"grav": "media",
"pontos": 2,
"nome": "Quando o veículo estiver em movimento, deixar de conservá-lo: II - nas faixas da direita, os veículos lentos e de maior porte.",
"desc": "No exame de direção veicular a falta deverá ser anotada quando o candidato tiver percurso determinado a cumprir e deixar de conduzir em faixa destinada a circulação",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "",
"checks": "",
"compl": "Situação similar ao art. 185, inciso I, do CTB, porém destinada às Categorias profissionais.",
"enquad": {
"art": "185",
"ctb": "CTB Art. 185",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 186",
"art": "186",
"grav": "grave",
"pontos": 4,
"nome": "Transitar pela contramão de direção em: I - vias com duplo sentido de circulação, exceto para ultrapassar outro veículo e apenas pelo tempo necessário, respeitada a preferência do veículo que transitar em sentido contrário.",
"desc": "A falta deverá ser anotada quando o candidato conduzir em contramão de direção e avançar a via em sentido contrário, em local não autorizado, ou em tempo superior ao necessário para realizar a manobra ou ainda sem respeitar a preferência do veículo que transita em sentido oposto.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "",
"checks": "",
"compl": "Não há.",
"enquad": {
"art": "186",
"ctb": "CTB Art. 186",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 186 (2)",
"art": "186",
"grav": "gravissima",
"pontos": 6,
"nome": "Transitar pela contramão de direção em: II - vias com sinalização de regulamentação de sentido único de circulação",
"desc": "A falta deverá ser anotada quando o candidato conduzir em sentido oposto ao da via com sentido único de direção",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato conduzir em sentido oposto à via com sentido único. 1. Quando o candidato conduzir no sentido da via de sentido único; 2. Quando o candidato realizar manobra em marcha ré em sentido contrário ao da via de sentido único por tempo superior ao necessário. Não sendo caso de força maior, o examinador deve anotar a ocorrência na ficha de avaliação, aplicar a pontuação correspondente e solicitar para o candidato pare o veículo e faça a manobra no sentido correto da via.",
"checks": "Quando o candidato conduzir em sentido oposto à via com sentido único. 1. Quando o candidato conduzir no sentido da via de sentido único; 2. Quando o candidato realizar manobra em marcha ré em sentido contrário ao da via de sentido único por tempo superior ao necessário. Não sendo caso de força maior, o examinador deve anotar a ocorrência na ficha de avaliação, aplicar a pontuação correspondente e solicitar para o candidato pare o veículo e faça a manobra no sentido correto da via.",
"compl": "Não há.",
"enquad": {
"art": "186",
"ctb": "CTB Art. 186",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 187",
"art": "187",
"grav": "media",
"pontos": 2,
"nome": "Transitar em locais e horários não permitidos pela regulamentação estabelecida pela autoridade competente.",
"desc": "A falta deverá ser anotada quando o candidato transitar via com regulamentação específica quanto a circulação ou horário de circulação.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "",
"checks": "",
"compl": "Não há.",
"enquad": {
"art": "187",
"ctb": "CTB Art. 187",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 188",
"art": "188",
"grav": "media",
"pontos": 2,
"nome": "Transitar ao lado de outro veículo, interrompendo ou perturbando o trânsito.",
"desc": "No exame de direção veicular, quando transitar ao lado de outro veículo, interrompendo ou perturbando o trânsito.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Candidato transitando ao lado de outro veículo, na mesma velocidade, com o propósito de causar lentidão do fluxo; ou 2. Candidato interrompeu o trânsito, emparelhando o veículo com outro para conversar.",
"naoPontua": "1. Quando o condutor transitar ao lado de um veículo de duas rodas, na mesma faixa de circulação, utilizar enquadramento específico do art. 192. Art. 26. Os usuários das vias terrestres devem: I - abster-se de todo ato que possa constituir perigo ou obstáculo para o trânsito de veículos, de pessoas ou de animais, ou ainda causar danos a propriedades públicas ou privadas. Art. 29.",
"definicoes": "O trânsito de veículos nas vias terrestres abertas à circulação obedecerá às seguintes normas: [...] IV - quando uma pista de rolamento comportar várias faixas de circulação no mesmo sentido, são as da direita destinadas ao deslocamento dos veículos mais lentos e de maior porte, quando não houver faixa especial a eles destinada, e as da esquerda, destinadas à ultrapassagem e ao deslocamento dos veículos de maior velocidade",
"checks": "1. Candidato transitando ao lado de outro veículo, na mesma velocidade, com o propósito de causar lentidão do fluxo; ou 2. Candidato interrompeu o trânsito, emparelhando o veículo com outro para conversar. 1. Quando o condutor transitar ao lado de um veículo de duas rodas, na mesma faixa de circulação, utilizar enquadramento específico do art. 192. Art. 26. Os usuários das vias terrestres devem: I - abster-se de todo ato que possa constituir perigo ou obstáculo para o trânsito de veículos, de pessoas ou de animais, ou ainda causar danos a propriedades públicas ou privadas. Art. 29. O trânsito de veículos nas vias terrestres abertas à circulação obedecerá às seguintes normas: [...] IV - quando uma pista de rolamento comportar várias faixas de circulação no mesmo sentido, são as da direita destinadas ao deslocamento dos veículos mais lentos e de maior porte, quando não houver faixa especial a eles destinada, e as da esquerda, destinadas à ultrapassagem e ao deslocamento dos veículos de maior velocidade",
"compl": "Não há.",
"enquad": {
"art": "188",
"ctb": "CTB Art. 188",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 189",
"art": "189",
"grav": "gravissima",
"pontos": 6,
"nome": "Deixar de dar passagem aos veículos precedidos de batedores, de socorro de incêndio e salvamento, de polícia, de operação e fiscalização de trânsito e às ambulâncias, quando em serviço de urgência e devidamente identificados por dispositivos regulamentados de alarme sonoro e iluminação intermitente.",
"desc": "No exame de direção veicular, deixar de dar passagem aos veículos precedidos de batedores, de socorro de incêndio e salvamento, de polícia, de operação e fiscalização de trânsito e às ambulâncias, quando em serviço de urgência e devidamente identificados por dispositivos regulamentados de alarme sonoro e iluminação intermitente.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Durante o exame de direção será pontuado o candidato que permanecer com o veículo nessas condições: 1. O veículo permaneceu imóvel interrompendo a passagem de veículo com batedores, devidamente sinalizados. 2. O veículo não se deslocou para dar passagem ao veículo precedido de batedores, devidamente sinalizados. 3. Deixou de dar passagem a veículo com batedores devidamente sinalizados. Se a imobilização ou o deslocamento do veículo para outra faixa causar riscos à sua segurança, ou à segurança de outros veículos ou pedestres. Veículo precedido de batedores, sem que os dispositivos regulamentados de alarme sonoro e iluminação intermitente estejam simultaneamente acionados. Art. 29, VI - os veículos precedidos de batedores terão prioridade de passagem, respeitadas as demais normas de circulação.",
"checks": "Durante o exame de direção será pontuado o candidato que permanecer com o veículo nessas condições: 1. O veículo permaneceu imóvel interrompendo a passagem de veículo com batedores, devidamente sinalizados. 2. O veículo não se deslocou para dar passagem ao veículo precedido de batedores, devidamente sinalizados. 3. Deixou de dar passagem a veículo com batedores devidamente sinalizados. Se a imobilização ou o deslocamento do veículo para outra faixa causar riscos à sua segurança, ou à segurança de outros veículos ou pedestres. Veículo precedido de batedores, sem que os dispositivos regulamentados de alarme sonoro e iluminação intermitente estejam simultaneamente acionados. Art. 29, VI - os veículos precedidos de batedores terão prioridade de passagem, respeitadas as demais normas de circulação.",
"compl": "Não há.",
"enquad": {
"art": "189",
"ctb": "CTB Art. 189",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 190",
"art": "190",
"grav": "grave",
"pontos": 4,
"nome": "Seguir veículo em serviço de urgência, estando este com prioridade de passagem devidamente identificada por dispositivos regulamentares de alarme sonoro e iluminação intermitente:",
"desc": "",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Candidato que segue outro veículo em serviço de urgência, devidamente identificado e com seus dispositivos de alarme sonoro e iluminação intermitente acionados. Caso o veículo que esteja sendo seguido não tenha acionado os dispositivos regulamentares de alarme sonoro e iluminação intermitente. Art. 29. O trânsito de veículos nas vias terrestres abertas à circulação obedecerá às seguintes normas: [...] VII os veículos destinados a socorro de incêndio e salvamento, os de polícia, os de fiscalização e operação de trânsito e as ambulâncias, além de prioridade no trânsito, gozam de livre circulação, estacionamento e parada, quando em serviço de urgência, de policiamento ostensivo ou de preservação da ordem pública.",
"checks": "Candidato que segue outro veículo em serviço de urgência, devidamente identificado e com seus dispositivos de alarme sonoro e iluminação intermitente acionados. Caso o veículo que esteja sendo seguido não tenha acionado os dispositivos regulamentares de alarme sonoro e iluminação intermitente. Art. 29. O trânsito de veículos nas vias terrestres abertas à circulação obedecerá às seguintes normas: [...] VII os veículos destinados a socorro de incêndio e salvamento, os de polícia, os de fiscalização e operação de trânsito e as ambulâncias, além de prioridade no trânsito, gozam de livre circulação, estacionamento e parada, quando em serviço de urgência, de policiamento ostensivo ou de preservação da ordem pública.",
"compl": "Não há.",
"enquad": {
"art": "190",
"ctb": "CTB Art. 190",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 191",
"art": "191",
"grav": "gravissima",
"pontos": 6,
"nome": "Forçar passagem entre veículos que, transitando em sentidos opostos, estejam na iminência de passar um pelo outro ao realizar operação de ultrapassagem.",
"desc": "No exame de direção veicular, forçar passagem entre veículos que, transitando em sentidos opostos, estejam na iminência de passar um pelo outro ao realizar operação de ultrapassagem.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "1. Quando o candidato com o veículo que ao realizar ultrapassagem, mesmo em local permitido, força a passagem entre veículos que estejam circulando em sentidos opostos e próximos a passar um pelo outro. 2. Veículo que ao iniciar a operação de ultrapassagem, mesmo em local permitido, força a passagem entre veículos que estejam circulando em sentidos opostos e próximos a passar um pelo outro, mesmo que não complete a manobra de ultrapassagem. Quando o veículo fizer ultrapassagem proibida e não forçar a passagem entre dois outros veículos, utilizar enquadramento específico de transitar na contramão de direção, art. 186, I.",
"naoPontua": "1. Art. 29. O trânsito de veículos nas vias terrestres abertas à circulação obedecerá às seguintes normas: [...] X - todo condutor deverá, antes de efetuar uma ultrapassagem, certificar-se de que: [...] c) a faixa de trânsito que vai tomar esteja livre numa extensão suficiente para que sua manobra não ponha em perigo ou obstrua o trânsito que venha em sentido contrário. 2.",
"definicoes": "Forçar passagem - veículo que ao realizar ou tentar realizar ultrapassagem, mesmo em local permitido, força a passagem entre veículos que estejam circulando em sentidos opostos e próximos a passar um pelo outro, gerando situação de risco (saída de qualquer dos veículos para o acostamento, para outra faixa, diminuição de velocidade, entre outras situações).",
"checks": "1. Quando o candidato com o veículo que ao realizar ultrapassagem, mesmo em local permitido, força a passagem entre veículos que estejam circulando em sentidos opostos e próximos a passar um pelo outro. 2. Veículo que ao iniciar a operação de ultrapassagem, mesmo em local permitido, força a passagem entre veículos que estejam circulando em sentidos opostos e próximos a passar um pelo outro, mesmo que não complete a manobra de ultrapassagem. Quando o veículo fizer ultrapassagem proibida e não forçar a passagem entre dois outros veículos, utilizar enquadramento específico de transitar na contramão de direção, art. 186, I. 1. Art. 29. O trânsito de veículos nas vias terrestres abertas à circulação obedecerá às seguintes normas: [...] X - todo condutor deverá, antes de efetuar uma ultrapassagem, certificar-se de que: [...] c) a faixa de trânsito que vai tomar esteja livre numa extensão suficiente para que sua manobra não ponha em perigo ou obstrua o trânsito que venha em sentido contrário. 2. Forçar passagem - veículo que ao realizar ou tentar realizar ultrapassagem, mesmo em local permitido, força a passagem entre veículos que estejam circulando em sentidos opostos e próximos a passar um pelo outro, gerando situação de risco (saída de qualquer dos veículos para o acostamento, para outra faixa, diminuição de velocidade, entre outras situações).",
"compl": "Não há.",
"enquad": {
"art": "191",
"ctb": "CTB Art. 191",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 192",
"art": "192",
"grav": "grave",
"pontos": 4,
"nome": "Deixar de guardar distância de segurança lateral e frontal entre o seu veículo e os demais, bem como em relação ao bordo da pista, considerando-se, no momento, a velocidade, as condições climáticas do local da circulação e do veículo.",
"desc": "Deixar o candidato na condução do veículo automotor, de guardar distância de segurança lateral e frontal entre o seu veículo e os demais, bem como em relação ao bordo da pista, considerando-se, no momento, a velocidade, as condições climáticas do local da circulação e do veículo.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Candidato que não manter distância frontal ou lateral, entre o seu veículo e os demais ou se aproxima do bordo da pista, colocando em risco a segurança do trânsito, considerando no momento a velocidade, as condições climáticas, do local e/ou do veículo. 2. Candidato que não manter distância lateral de veículos parados ou estacionados, colocando em risco a segurança do trânsito, considerando a geometria da via. 3. Candidato que não mantém distância de segurança frontal em relação a outros veículos imobilizados em paradas obrigatórias ou semafóricas. Veículo que passar ou ultrapassar bicicleta sem guardar distância regulamentada, utilizar enquadramento específico: art. 201. Veículo que transitar pela contramão, utilizar enquadramento específico: art. 186. Veículo que forçar passagem entre veículos que transitando em sentido opostos, estejam na iminência de passar um pelo outro, utilizar enquadramento específico: art. 191 Veículo que ultrapassar pela contramão outro veículo, utilizar enquadramento específico: art. 203, I a V",
"naoPontua": "1. Art. 29. O trânsito de veículos nas vias terrestres abertas à circulação obedecerá às seguintes normas: [...] II - o condutor deverá guardar distância de segurança lateral e frontal entre o seu e os demais veículos, bem como em relação ao bordo da pista, considerando- se, no momento, a velocidade e as condições do local, da circulação, do veículo e as condições climáticas. 2. Para avaliar se a distância é segura, considerar as condições que propiciam sinistros, como por exemplo: 2.1. pista molhada, neblina; 2.2. volume de tráfego; 2.3. geometria da via; 2.4. velocidade dos veículos; 2.5. largura das faixas de trânsito; 2.6. dimensões dos veículos.",
"definicoes": "",
"checks": "1. Candidato que não manter distância frontal ou lateral, entre o seu veículo e os demais ou se aproxima do bordo da pista, colocando em risco a segurança do trânsito, considerando no momento a velocidade, as condições climáticas, do local e/ou do veículo. 2. Candidato que não manter distância lateral de veículos parados ou estacionados, colocando em risco a segurança do trânsito, considerando a geometria da via. 3. Candidato que não mantém distância de segurança frontal em relação a outros veículos imobilizados em paradas obrigatórias ou semafóricas. Veículo que passar ou ultrapassar bicicleta sem guardar distância regulamentada, utilizar enquadramento específico: art. 201. Veículo que transitar pela contramão, utilizar enquadramento específico: art. 186. Veículo que forçar passagem entre veículos que transitando em sentido opostos, estejam na iminência de passar um pelo outro, utilizar enquadramento específico: art. 191 Veículo que ultrapassar pela contramão outro veículo, utilizar enquadramento específico: art. 203, I a V 1. Art. 29. O trânsito de veículos nas vias terrestres abertas à circulação obedecerá às seguintes normas: [...] II - o condutor deverá guardar distância de segurança lateral e frontal entre o seu e os demais veículos, bem como em relação ao bordo da pista, considerando- se, no momento, a velocidade e as condições do local, da circulação, do veículo e as condições climáticas. 2. Para avaliar se a distância é segura, considerar as condições que propiciam sinistros, como por exemplo: 2.1. pista molhada, neblina; 2.2. volume de tráfego; 2.3. geometria da via; 2.4. velocidade dos veículos; 2.5. largura das faixas de trânsito; 2.6. dimensões dos veículos.",
"compl": "Não há.",
"enquad": {
"art": "192",
"ctb": "CTB Art. 192",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 193",
"art": "193",
"grav": "gravissima",
"pontos": 6,
"nome": "Transitar com o veículo em calçadas, passeios, passarelas, ciclovias, ciclo faixas, ilhas, refúgios, ajardinamentos, canteiros centrais e divisores de pista de rolamento, acostamentos, marcas de canalização, gramados e jardins públicos.",
"desc": "No exame de direção veicular, transitar com o veículo em calçadas, passeios, passarelas, ciclovias, ciclofaixas, ilhas, refúgios, ajardinamentos, canteiros centrais e divisores de pista de rolamento, acostamentos, marcas de canalização, gramados e jardins públicos.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Veículo que transitar, total ou parcialmente, sobre calçada ou passeio. 2. Veículo que transitar no avanço do passeio delimitado por sinalização ou por elemento físico separador. 3. Veículo automotor que transitar sobre calçada ou passeio sinalizada como espaço partilhado ou compartilhado entre ciclistas e pedestres. 4. Avançar sobre o meio fio. 3. Retorno passando sobre calçada ou passeio, utilizar enquadramento específico: art. 206, III.",
"naoPontua": "1. Calçada - parte da via, normalmente segregada e em nível diferente, reservada ao trânsito de pedestres e, quando possível, à implantação de mobiliário urbano, sinalização, vegetação e outros fins. 2. Passeio - parte da calçada ou da pista de rolamento, neste último caso, separada por pintura ou elemento físico separador, livre de interferências, destinada à circulação exclusiva de pedestres e, excepcionalmente, de ciclistas. 3. Espaço compartilhado com pedestres - espaço da via pública destinado prioritariamente aos pedestres onde os ciclistas compartilham a mesma área de circulação, desde que devidamente sinalizado. 4.",
"definicoes": "Via - superfície por onde transitam veículos, pessoas e animais, compreendendo a pista, a calçada, o acostamento, ilha e canteiro central.",
"checks": "1. Veículo que transitar, total ou parcialmente, sobre calçada ou passeio. 2. Veículo que transitar no avanço do passeio delimitado por sinalização ou por elemento físico separador. 3. Veículo automotor que transitar sobre calçada ou passeio sinalizada como espaço partilhado ou compartilhado entre ciclistas e pedestres. 4. Avançar sobre o meio fio. 3. Retorno passando sobre calçada ou passeio, utilizar enquadramento específico: art. 206, III. 1. Calçada - parte da via, normalmente segregada e em nível diferente, reservada ao trânsito de pedestres e, quando possível, à implantação de mobiliário urbano, sinalização, vegetação e outros fins. 2. Passeio - parte da calçada ou da pista de rolamento, neste último caso, separada por pintura ou elemento físico separador, livre de interferências, destinada à circulação exclusiva de pedestres e, excepcionalmente, de ciclistas. 3. Espaço compartilhado com pedestres - espaço da via pública destinado prioritariamente aos pedestres onde os ciclistas compartilham a mesma área de circulação, desde que devidamente sinalizado. 4. Via - superfície por onde transitam veículos, pessoas e animais, compreendendo a pista, a calçada, o acostamento, ilha e canteiro central.",
"compl": "Não há.",
"enquad": {
"art": "193",
"ctb": "CTB Art. 193",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 194",
"art": "194",
"grav": "grave",
"pontos": 4,
"nome": "Transitar em marcha à ré, salvo na distância necessária a pequenas manobras e de forma a não causar riscos à segurança.",
"desc": "Transitar em marcha à ré, salvo na distância necessária a pequenas manobras e de forma a não causar riscos à segurança.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "",
"checks": "",
"compl": "Não há.",
"enquad": {
"art": "194",
"ctb": "CTB Art. 194",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 195",
"art": "195",
"grav": "grave",
"pontos": 4,
"nome": "Desobedecer às ordens emanadas da autoridade competente de trânsito ou de seus agentes.",
"desc": "No exame de direção veicular, desobedecer às ordens emanadas da autoridade competente de trânsito ou de seus agentes.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Candidato que desobedecer a ordem emanada da autoridade de trânsito e seus examinadores; ou 2. Candidato que desobedecer a ordem verbal ou sonora, dada pela autoridade de trânsito, seus agentes no papel de examinadores. Se o candidato deixar de reduzir a velocidade do veículo nos locais onde o trânsito esteja sendo controlado pelo agente, mediante sinais sonoros ou gestos, utilizar enquadramento específico: art. 220, inciso II.",
"naoPontua": "1. As ordens do agente de trânsito terão prevalência sobre as normas de circulação e outros sinais (art. 89, I). 2. Para caracterização da infração administrativa prevista no art. 195 são necessários 3 pressupostos: 2.1. que a ordem seja relativa à normatização do trânsito em geral; 2.2. que a ordem seja emanada da autoridade de trânsito ou do agente; ou examinadores; 2.3. a participação do destinatário da ordem em qualquer situação de trânsito, em sentido amplo. 3.",
"definicoes": "A ordem pode ser verbal, bem como através de gestos indicados pelos examinadores.",
"checks": "1. Candidato que desobedecer a ordem emanada da autoridade de trânsito e seus examinadores; ou 2. Candidato que desobedecer a ordem verbal ou sonora, dada pela autoridade de trânsito, seus agentes no papel de examinadores. Se o candidato deixar de reduzir a velocidade do veículo nos locais onde o trânsito esteja sendo controlado pelo agente, mediante sinais sonoros ou gestos, utilizar enquadramento específico: art. 220, inciso II. 1. As ordens do agente de trânsito terão prevalência sobre as normas de circulação e outros sinais (art. 89, I). 2. Para caracterização da infração administrativa prevista no art. 195 são necessários 3 pressupostos: 2.1. que a ordem seja relativa à normatização do trânsito em geral; 2.2. que a ordem seja emanada da autoridade de trânsito ou do agente; ou examinadores; 2.3. a participação do destinatário da ordem em qualquer situação de trânsito, em sentido amplo. 3. A ordem pode ser verbal, bem como através de gestos indicados pelos examinadores.",
"compl": "O rol de situações descritas no campo “condutas que pontuam” é meramente exemplificativo e não exaure e nem exclui outras situações que impliquem em desobedecer às ordens emanadas da autoridade de trânsito e do agente fiscalizador.",
"enquad": {
"art": "195",
"ctb": "CTB Art. 195",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 196",
"art": "196",
"grav": "grave",
"pontos": 4,
"nome": "Deixar de indicar com antecedência, mediante gesto regulamentar de braço ou luz indicadora de direção do veículo, o início da marcha, a realização da manobra de parar o veículo, a mudança de direção ou de faixa de circulação.",
"desc": "Deixar de indicar com antecedência, mediante gesto regulamentar de braço ou luz indicadora de direção do veículo, o início da marcha, a realização da manobra de parar o veículo, a mudança de direção ou de faixa de circulação.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Candidato com veículo estacionado/parado que inicia a marcha sem sinalizar, com antecedência, mediante luz indicadora ou gesto; 2. Candidato estacionado/parado, que sinaliza que vai iniciar a marcha em uma direção, mas que inicia a marcha pelo lado oposto; 3. Candidato que sinaliza que vai parar/estacionar em uma direção, mas que para/estaciona no lado oposto; 4. Candidato que não sinaliza com antecedência a manobra de: a) conversão à esquerda ou à direita; b) retorno à esquerda ou à direita; ou c) entrada/saída de lote lindeiro. 5. Candidato que sinaliza a mudança de direção contrária à sinalizada. 6. Candidato que não sinaliza com luz ou gesto com antecedência a manobra de mudança de faixa, inclusive para efetuar passagem ou ultrapassagem.",
"naoPontua": "1. Candidato que não sinaliza a manobra de conversão em entroncamento que tenha uma única direção a seguir. 2. Candidato que não sinaliza a manobra de saída de lote lindeiro quando a via for de mão única. 3. Candidato que não sinaliza uma manobra proibida, utilizar enquadramento específico para o movimento realizado. 1. Art. 35. Antes de iniciar qualquer manobra que implique um deslocamento lateral, o candidato deverá indicar seu propósito de forma clara e com a devida antecedência, por meio da luz indicadora de direção de seu veículo, ou fazendo gesto convencional de braço. 2. Gestos de condutores - movimentos convencionais de braço, adotados exclusivamente pelos candidatos, para orientar ou indicar que vão efetuar uma manobra de mudança de direção, redução brusca de velocidade ou parada. 3.",
"definicoes": "Faixas de trânsito - qualquer uma das áreas longitudinais em que a pista pode ser subdividida, sinalizada ou não por marcas viárias longitudinais, que tenham uma largura suficiente para permitir a circulação de veículos automotores.",
"checks": "1. Candidato com veículo estacionado/parado que inicia a marcha sem sinalizar, com antecedência, mediante luz indicadora ou gesto; 2. Candidato estacionado/parado, que sinaliza que vai iniciar a marcha em uma direção, mas que inicia a marcha pelo lado oposto; 3. Candidato que sinaliza que vai parar/estacionar em uma direção, mas que para/estaciona no lado oposto; 4. Candidato que não sinaliza com antecedência a manobra de: a) conversão à esquerda ou à direita; b) retorno à esquerda ou à direita; ou c) entrada/saída de lote lindeiro. 5. Candidato que sinaliza a mudança de direção contrária à sinalizada. 6. Candidato que não sinaliza com luz ou gesto com antecedência a manobra de mudança de faixa, inclusive para efetuar passagem ou ultrapassagem. 1. Candidato que não sinaliza a manobra de conversão em entroncamento que tenha uma única direção a seguir. 2. Candidato que não sinaliza a manobra de saída de lote lindeiro quando a via for de mão única. 3. Candidato que não sinaliza uma manobra proibida, utilizar enquadramento específico para o movimento realizado. 1. Art. 35. Antes de iniciar qualquer manobra que implique um deslocamento lateral, o candidato deverá indicar seu propósito de forma clara e com a devida antecedência, por meio da luz indicadora de direção de seu veículo, ou fazendo gesto convencional de braço. 2. Gestos de condutores - movimentos convencionais de braço, adotados exclusivamente pelos candidatos, para orientar ou indicar que vão efetuar uma manobra de mudança de direção, redução brusca de velocidade ou parada. 3. Faixas de trânsito - qualquer uma das áreas longitudinais em que a pista pode ser subdividida, sinalizada ou não por marcas viárias longitudinais, que tenham uma largura suficiente para permitir a circulação de veículos automotores.",
"compl": "A sinalização indicadora de direção deve permanecer acionada durante toda a execução da manobra pretendida. Caso o dispositivo desarme antes da conclusão, o candidato deverá reativá-lo imediatamente.",
"enquad": {
"art": "196",
"ctb": "CTB Art. 196",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 197",
"art": "197",
"grav": "media",
"pontos": 2,
"nome": "Deixar de deslocar, com antecedência, o veículo para a faixa mais à esquerda ou mais à direita, dentro da respectiva mão de direção, quando for manobrar para um desses lados.",
"desc": "Esta infração será verificada quando o candidato deixar de deslocar, com antecedência, o veículo para a faixa mais à esquerda ou mais à direita, dentro da respectiva mão de direção, quando for manobrar para um desses lados.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Veículo que não se desloca com antecedência para a faixa mais à esquerda quando for manobrar para a esquerda; ou Veículo que converge à esquerda utilizando qualquer uma das faixas, que não seja a mais à esquerda, em local não regulamentado com a permissão. Veículo de grande porte, que não se deslocou para a faixa mais à esquerda, por necessitar de mais de uma faixa de circulação para realizar a manobra de conversão. Manobra realizada sobre marcas de canalização, utilizar enquadramento específico: art. 193. Art. 35. Antes de iniciar qualquer manobra que implique um deslocamento lateral, o candidato deverá indicar seu propósito de forma clara e com a devida antecedência, por meio da luz indicadora de direção de seu veículo, ou fazendo gesto convencional de braço. Art. 38. Antes de entrar à direita ou à esquerda, em outra via ou em lotes lindeiros, o condutor deverá: II - ao sair da via pelo lado esquerdo, aproximar-se o máximo possível de seu eixo ou da linha divisória da pista, quando houver, caso se trate de uma pista com circulação nos dois sentidos, ou do bordo esquerdo, tratando-se de uma pista de um só sentido.",
"checks": "Veículo que não se desloca com antecedência para a faixa mais à esquerda quando for manobrar para a esquerda; ou Veículo que converge à esquerda utilizando qualquer uma das faixas, que não seja a mais à esquerda, em local não regulamentado com a permissão. Veículo de grande porte, que não se deslocou para a faixa mais à esquerda, por necessitar de mais de uma faixa de circulação para realizar a manobra de conversão. Manobra realizada sobre marcas de canalização, utilizar enquadramento específico: art. 193. Art. 35. Antes de iniciar qualquer manobra que implique um deslocamento lateral, o candidato deverá indicar seu propósito de forma clara e com a devida antecedência, por meio da luz indicadora de direção de seu veículo, ou fazendo gesto convencional de braço. Art. 38. Antes de entrar à direita ou à esquerda, em outra via ou em lotes lindeiros, o condutor deverá: II - ao sair da via pelo lado esquerdo, aproximar-se o máximo possível de seu eixo ou da linha divisória da pista, quando houver, caso se trate de uma pista com circulação nos dois sentidos, ou do bordo esquerdo, tratando-se de uma pista de um só sentido.",
"compl": "Não há.",
"enquad": {
"art": "197",
"ctb": "CTB Art. 197",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 198",
"art": "198",
"grav": "media",
"pontos": 2,
"nome": "Deixar de dar passagem pela esquerda, quando solicitado.",
"desc": "Deixar de dar passagem pela esquerda, quando solicitado.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Candidato que, sinalizando conversão à esquerda em local permitido, deixa de dar passagem. 2. Candidato que, aguardando para mudar para faixa mais à direita com segurança, deixa de dar passagem. 3. Candidato que não dá passagem em local com apenas duas faixas no mesmo sentido, sendo a da direita regulamentada para a circulação de determinado tipo de veículo que não o seu. 4. Deixar de dar passagem aos veículos precedidos de batedores, de socorro de incêndio e salvamento, de polícia, de operação e fiscalização de trânsito e às ambulâncias, quando em serviço de urgência, utilizar enquadramento específico: art. 189.",
"naoPontua": "1. Art. 29. O trânsito de veículos nas vias terrestres abertas à circulação obedecerá às seguintes normas: [....] IV -quando uma pista de rolamento comportar várias faixas de circulação no mesmo sentido, são as da direita destinadas ao deslocamento dos veículos mais lentos e de maior porte, quando não houver faixa especial a eles destinada, e as da esquerda, destinadas à ultrapassagem e ao deslocamento dos veículos de maior velocidade. 2.",
"definicoes": "Para indicar ao veículo que segue à frente a intenção de passá-lo, o condutor deverá acionar a luz baixa e alta, de forma intermitente e por curto período. Fora das áreas urbanas, é permitido o uso de buzina, desde que em toque breve.",
"checks": "Candidato que, transitando em quaisquer das faixas da esquerda, em local com duas ou mais faixas de circulação no mesmo sentido, não se deslocar para quaisquer das faixas da direita, quando receber a indicação de outro veículo que tem a intenção de passá-lo. 1. Candidato que, sinalizando conversão à esquerda em local permitido, deixa de dar passagem. 2. Candidato que, aguardando para mudar para faixa mais à direita com segurança, deixa de dar passagem. 3. Candidato que não dá passagem em local com apenas duas faixas no mesmo sentido, sendo a da direita regulamentada para a circulação de determinado tipo de veículo que não o seu. 4. Deixar de dar passagem aos veículos precedidos de batedores, de socorro de incêndio e salvamento, de polícia, de operação e fiscalização de trânsito e às ambulâncias, quando em serviço de urgência, utilizar enquadramento específico: art. 189. 1. Art. 29. O trânsito de veículos nas vias terrestres abertas à circulação obedecerá às seguintes normas: [....] IV -quando uma pista de rolamento comportar várias faixas de circulação no mesmo sentido, são as da direita destinadas ao deslocamento dos veículos mais lentos e de maior porte, quando não houver faixa especial a eles destinada, e as da esquerda, destinadas à ultrapassagem e ao deslocamento dos veículos de maior velocidade. 2. Para indicar ao veículo que segue à frente a intenção de passá-lo, o condutor deverá acionar a luz baixa e alta, de forma intermitente e por curto período. Fora das áreas urbanas, é permitido o uso de buzina, desde que em toque breve.",
"compl": "Não há.",
"enquad": {
"art": "198",
"ctb": "CTB Art. 198",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 199",
"art": "199",
"grav": "media",
"pontos": 2,
"nome": "Ultrapassar pela direita, salvo quando o veículo da frente estiver colocado na faixa apropriada e der sinal de que vai entrar à esquerda.",
"desc": "No exame de direção veicular, ultrapassar pela direita, salvo quando o veículo da frente estiver colocado na faixa apropriada e der sinal de que vai entrar à esquerda.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Veículo que ultrapassa outro pela direita, quando o veículo que está sendo ultrapassado estiver sinalizando o propósito de entrar à esquerda. 2. Veículo que passa por outro pela direita, onde houver duas ou mais faixas de circulação.",
"naoPontua": "1. Art. 29, IX - a ultrapassagem de outro veículo em movimento deverá ser feita pela esquerda, obedecida a sinalização regulamentar e as demais normas estabelecidas neste CTB, exceto quando o veículo a ser ultrapassado estiver sinalizando o propósito de entrar à esquerda. 2.",
"definicoes": "Ultrapassagem, para fins de exames, é o movimento de passar à frente de outros veículos que se deslocam no mesmo sentido e faixa de tráfego, necessitando sair e retornar à faixa de origem. Os veículos ultrapassados circulam em menor velocidade ou estão imobilizados por força de um obstáculo.",
"checks": "Veículo que ultrapassa outro pela direita. 1. Veículo que ultrapassa outro pela direita, quando o veículo que está sendo ultrapassado estiver sinalizando o propósito de entrar à esquerda. 2. Veículo que passa por outro pela direita, onde houver duas ou mais faixas de circulação. 1. Art. 29, IX - a ultrapassagem de outro veículo em movimento deverá ser feita pela esquerda, obedecida a sinalização regulamentar e as demais normas estabelecidas neste CTB, exceto quando o veículo a ser ultrapassado estiver sinalizando o propósito de entrar à esquerda. 2. Ultrapassagem, para fins de exames, é o movimento de passar à frente de outros veículos que se deslocam no mesmo sentido e faixa de tráfego, necessitando sair e retornar à faixa de origem. Os veículos ultrapassados circulam em menor velocidade ou estão imobilizados por força de um obstáculo.",
"compl": "Não há.",
"enquad": {
"art": "199",
"ctb": "CTB Art. 199",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 200",
"art": "200",
"grav": "gravissima",
"pontos": 6,
"nome": "Ultrapassar pela direita veículo de transporte coletivo ou escolar parado para embarque ou desembarque de passageiros.",
"desc": "Ultrapassar pela direita veículo de transporte coletivo ou escolar parado para embarque ou desembarque de passageiros.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato realiza a ultrapassagem pela direita de veículos coletivos parados, colocando pedestres em risco. Quando o candidato aguarda o momento seguro para seguir, respeitando o embarque e desembarque de passageiros. O examinador deve observar o comportamento do candidato ao se aproximar de veículos coletivos parados e registrar a infração se houver tentativa de ultrapassagem indevida.",
"checks": "Quando o candidato realiza a ultrapassagem pela direita de veículos coletivos parados, colocando pedestres em risco. Quando o candidato aguarda o momento seguro para seguir, respeitando o embarque e desembarque de passageiros. O examinador deve observar o comportamento do candidato ao se aproximar de veículos coletivos parados e registrar a infração se houver tentativa de ultrapassagem indevida.",
"compl": "Esta infração representa descumprimento de norma de circulação e risco direto aos pedestres, conforme o CTB e MBEDV.",
"enquad": {
"art": "200",
"ctb": "CTB Art. 200",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 201",
"art": "201",
"grav": "media",
"pontos": 2,
"nome": "Deixar de guardar a distância lateral de 1,5 m ao passar ou ultrapassar bicicleta.",
"desc": "Deixar de guardar a distância lateral de 1,5 m ao passar ou ultrapassar bicicleta.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato passa próximo demais do ciclista, sem guardar a distância de segurança exigida. Quando o candidato reduz a velocidade e mantém afastamento lateral adequado do ciclista. 1. O examinador deve observar atentamente se o candidato mantém a distância lateral de segurança mínima de 1,5m ao passar ou ultrapassar bicicletas, durante todo o percurso. 2. Se houver risco de sinistro, o examinador deve intervir imediatamente para garantir a segurança. 3. A inobservância da distância segura regulamentada, entre o veículo e a bicicleta, configura infração gravíssima, conforme o art. 201 do CTB, e deve ser registrada na ficha de avaliação.",
"checks": "Quando o candidato passa próximo demais do ciclista, sem guardar a distância de segurança exigida. Quando o candidato reduz a velocidade e mantém afastamento lateral adequado do ciclista. 1. O examinador deve observar atentamente se o candidato mantém a distância lateral de segurança mínima de 1,5m ao passar ou ultrapassar bicicletas, durante todo o percurso. 2. Se houver risco de sinistro, o examinador deve intervir imediatamente para garantir a segurança. 3. A inobservância da distância segura regulamentada, entre o veículo e a bicicleta, configura infração gravíssima, conforme o art. 201 do CTB, e deve ser registrada na ficha de avaliação.",
"compl": "Não há.",
"enquad": {
"art": "201",
"ctb": "CTB Art. 201",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 202-I",
"art": "202-I",
"grav": "gravissima",
"pontos": 6,
"nome": "Ultrapassar pelo acostamento.",
"desc": "Ultrapassar pelo acostamento.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Veículo que ultrapassa outro, utilizando-se do acostamento. Quando o candidato permanece na faixa de rolamento aguardando sua vez de avançar. O examinador deve intervir e orientar o candidato a retornar à faixa de rolamento de origem se identificar uma manobra em curso que seja irregular ou prejudicial.",
"checks": "Veículo que ultrapassa outro, utilizando-se do acostamento. Quando o candidato permanece na faixa de rolamento aguardando sua vez de avançar. O examinador deve intervir e orientar o candidato a retornar à faixa de rolamento de origem se identificar uma manobra em curso que seja irregular ou prejudicial.",
"compl": "O acostamento é destinado apenas a emergências; seu uso indevido é falta gravíssima.",
"enquad": {
"art": "202-I",
"ctb": "CTB Art. 202, I",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 202-II",
"art": "202-II",
"grav": "gravissima",
"pontos": 6,
"nome": "Ultrapassar outro veículo em interseções e passagens de nível.",
"desc": "Durante o exame de direção, é proibido ultrapassar outro veículo em cruzamentos, interseções ou passagens de nível (como trilhos de trem). Essa manobra é extremamente perigosa, pois nesses locais há alto risco de colisão lateral ou frontal, além de interferência com outros fluxos de tráfego.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato realiza a ultrapassagem em cruzamentos ou passagens de nível, sem observar o tráfego cruzado ou a sinalização existente. 2. Quando o candidato ignora a regra de proibição de ultrapassagem nesses locais, comprometendo a segurança dos demais usuários da via.",
"naoPontua": "1. Quando o candidato reduz a velocidade e mantém sua posição na via ao se aproximar de cruzamentos ou passagens de nível. 2.",
"definicoes": "Quando o candidato respeita a sinalização, os veículos à frente e aguarda o local adequado para ultrapassar com segurança. O examinador observará especialmente a aproximação do candidato a cruzamentos e o respeito à sinalização e prioridade de passagem. O examinador deve observar atentamente a aproximação do candidato a interseções e passagens de nível. Caso o candidato realize tentativa ou execução de ultrapassagem nesses locais, a infração deve ser registrada. O examinador deve anotar a ocorrência na ficha de avaliação imediatamente, descrevendo o contexto da manobra.",
"checks": "1. Quando o candidato realiza a ultrapassagem em cruzamentos ou passagens de nível, sem observar o tráfego cruzado ou a sinalização existente. 2. Quando o candidato ignora a regra de proibição de ultrapassagem nesses locais, comprometendo a segurança dos demais usuários da via. 1. Quando o candidato reduz a velocidade e mantém sua posição na via ao se aproximar de cruzamentos ou passagens de nível. 2. Quando o candidato respeita a sinalização, os veículos à frente e aguarda o local adequado para ultrapassar com segurança. O examinador observará especialmente a aproximação do candidato a cruzamentos e o respeito à sinalização e prioridade de passagem. O examinador deve observar atentamente a aproximação do candidato a interseções e passagens de nível. Caso o candidato realize tentativa ou execução de ultrapassagem nesses locais, a infração deve ser registrada. O examinador deve anotar a ocorrência na ficha de avaliação imediatamente, descrevendo o contexto da manobra.",
"compl": "Não há.",
"enquad": {
"art": "202-II",
"ctb": "CTB Art. 202, II",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 203-II",
"art": "203-II",
"grav": "gravissima",
"pontos": 6,
"nome": "Ultrapassar pela contramão outro veículo nas faixas de pedestre.",
"desc": "Durante o exame de direção, o candidato não deve ultrapassar pela contramão outro veículo que esteja próximo ou sobre faixas de pedestres. Essa conduta é extremamente perigosa, pois compromete a segurança dos pedestres e demonstra falta de direção defensiva e atenção à sinalização horizontal.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato ultrapassa pela contramão outro veículo sobre a faixa de pedestres ou nas proximidades dela. 2. Quando o candidato ignora pedestres aguardando a travessia e executa manobra de ultrapassagem.",
"naoPontua": "1. O examinador deve observar a conduta do candidato nas proximidades de faixas de pedestres e registrar a infração caso ocorra tentativa de ultrapassagem pela contramão. 2.",
"definicoes": "O registro deve conter a descrição da manobra, o momento em que ocorreu e se havia pedestres presentes.",
"checks": "1. Quando o candidato ultrapassa pela contramão outro veículo sobre a faixa de pedestres ou nas proximidades dela. 2. Quando o candidato ignora pedestres aguardando a travessia e executa manobra de ultrapassagem. 1. O examinador deve observar a conduta do candidato nas proximidades de faixas de pedestres e registrar a infração caso ocorra tentativa de ultrapassagem pela contramão. 2. O registro deve conter a descrição da manobra, o momento em que ocorreu e se havia pedestres presentes.",
"compl": "Não há.",
"enquad": {
"art": "203-II",
"ctb": "CTB Art. 203, II",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 203-III",
"art": "203-III",
"grav": "gravissima",
"pontos": 6,
"nome": "Ultrapassar pela contramão outro veículo nas pontes, viadutos ou túneis.",
"desc": "Durante o exame de direção veicular, o candidato não deve realizar ultrapassagem pela contramão em locais como pontes, viadutos ou túneis, pois são trechos de pista estreita e de fluxo confinado, sem áreas de escape e com baixa possibilidade de manobra evasiva. Essas condições tornam qualquer ultrapassagem extremamente perigosa e contrária às normas de circulação.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato realiza ou tenta iniciar ultrapassagem em ponte, viaduto ou túnel, mesmo sem completar a manobra. 2. Quando o candidato invade a faixa contrária em locais de pista estreita e com sinalização de proibição de ultrapassagem. 3. Quando o candidato desrespeita as condições de segurança e as normas de circulação nesses trechos.",
"naoPontua": "1. Quando o candidato mantém o veículo em sua faixa de rolamento, reduz a velocidade e respeita a sinalização de proibição de ultrapassagem. 2. Quando o candidato demonstra atenção redobrada ao cruzar pontes, viadutos ou túneis, mantendo o controle e o posicionamento adequado. 3. Quando o candidato mantém comportamento prudente, evitando manobras arriscadas. 1. O examinador deve observar atentamente o comportamento do candidato durante o percurso em trechos de pista confinada (pontes, viadutos e túneis). 2. Caso o candidato realize a ultrapassagem pela contramão nestes locais, a infração deve ser registrada imediatamente. 3.",
"definicoes": "O registro na ficha de avaliação deve detalhar o local e as circunstâncias exatas em que a manobra irregular foi cometida.",
"checks": "1. Quando o candidato realiza ou tenta iniciar ultrapassagem em ponte, viaduto ou túnel, mesmo sem completar a manobra. 2. Quando o candidato invade a faixa contrária em locais de pista estreita e com sinalização de proibição de ultrapassagem. 3. Quando o candidato desrespeita as condições de segurança e as normas de circulação nesses trechos. 1. Quando o candidato mantém o veículo em sua faixa de rolamento, reduz a velocidade e respeita a sinalização de proibição de ultrapassagem. 2. Quando o candidato demonstra atenção redobrada ao cruzar pontes, viadutos ou túneis, mantendo o controle e o posicionamento adequado. 3. Quando o candidato mantém comportamento prudente, evitando manobras arriscadas. 1. O examinador deve observar atentamente o comportamento do candidato durante o percurso em trechos de pista confinada (pontes, viadutos e túneis). 2. Caso o candidato realize a ultrapassagem pela contramão nestes locais, a infração deve ser registrada imediatamente. 3. O registro na ficha de avaliação deve detalhar o local e as circunstâncias exatas em que a manobra irregular foi cometida.",
"compl": "Não há.",
"enquad": {
"art": "203-III",
"ctb": "CTB Art. 203, III",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 203-IV",
"art": "203-IV",
"grav": "gravissima",
"pontos": 6,
"nome": "Ultrapassar pela contramão outro veículo parado em fila junto a sinais luminosos, porteiras, cancelas, cruzamentos ou qualquer outro impedimento à livre circulação.",
"desc": "Durante o exame de direção, o candidato não deve ultrapassar pela contramão veículos parados em fila em razão de semáforo, porteira, cancela, cruzamento ou qualquer outro bloqueio momentâneo.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato ultrapassa veículos parados em fila pela contramão, desrespeitando a sinalização ou o fluxo da via. 2. Quando o candidato tenta “cortar caminho” pela faixa contrária ou pela lateral da pista para adiantar-se indevidamente. 3. Quando o candidato demonstra impaciência e realiza manobra que coloque em risco os veículos à frente ou pedestres próximos.",
"naoPontua": "1. O examinador deve observar atentamente o comportamento do candidato em situações de parada obrigatória ou retenção de veículos. 2. Caso o candidato ultrapasse pela contramão veículos parados em fila, a infração deve ser registrada imediatamente como gravíssima (peso 6). 3.",
"definicoes": "O registro na ficha de avaliação deve detalhar o local da ocorrência (como semáforo, cruzamento, ou porteira) e as circunstâncias exatas em que a manobra irregular foi cometida.",
"checks": "1. Quando o candidato ultrapassa veículos parados em fila pela contramão, desrespeitando a sinalização ou o fluxo da via. 2. Quando o candidato tenta “cortar caminho” pela faixa contrária ou pela lateral da pista para adiantar-se indevidamente. 3. Quando o candidato demonstra impaciência e realiza manobra que coloque em risco os veículos à frente ou pedestres próximos. 1. O examinador deve observar atentamente o comportamento do candidato em situações de parada obrigatória ou retenção de veículos. 2. Caso o candidato ultrapasse pela contramão veículos parados em fila, a infração deve ser registrada imediatamente como gravíssima (peso 6). 3. O registro na ficha de avaliação deve detalhar o local da ocorrência (como semáforo, cruzamento, ou porteira) e as circunstâncias exatas em que a manobra irregular foi cometida.",
"compl": "Não há.",
"enquad": {
"art": "203-IV",
"ctb": "CTB Art. 203, IV",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 203-V",
"art": "203-V",
"grav": "gravissima",
"pontos": 6,
"nome": "Ultrapassar pela contramão outro veículo onde houver marcação viária longitudinal de divisão de fluxos opostos do tipo linha dupla contínua ou simples contínua amarela.",
"desc": "Durante o exame de direção, o candidato não deve realizar ultrapassagem pela contramão em trechos da via onde exista linha amarela contínua (simples ou dupla), que indica proibição de ultrapassar. Essas linhas delimitam áreas de risco e visibilidade reduzida, e sua desobediência representa falta grave de observância da sinalização horizontal e das normas de segurança viária.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato realiza ultrapassagem pela contramão transpondo linha amarela contínua. 2. Quando o candidato ignora a sinalização de proibição de ultrapassagem, mesmo sem completar a manobra. 3. Quando o candidato não respeita o fluxo oposto e compromete a segurança da via.",
"naoPontua": "1. Quando o candidato mantém o veículo dentro de sua faixa de rolamento e respeita a sinalização de proibição de ultrapassagem. 2. Quando o candidato aguarda o trecho permitido (linha seccionada) para realizar a manobra de forma segura. 3. Quando o candidato demonstra atenção às marcas viárias e adota conduta preventiva. 1. O examinador deve observar atentamente a reação do candidato diante da sinalização horizontal de linha contínua. 2. Caso o candidato execute a ultrapassagem pela contramão sobre a linha contínua, a infração deve ser registrada imediatamente como gravíssima. 3.",
"definicoes": "O registro na ficha de avaliação deve conter a descrição detalhada do trecho e especificar o tipo de marcação viária desrespeitada (simples contínua ou dupla contínua).",
"checks": "1. Quando o candidato realiza ultrapassagem pela contramão transpondo linha amarela contínua. 2. Quando o candidato ignora a sinalização de proibição de ultrapassagem, mesmo sem completar a manobra. 3. Quando o candidato não respeita o fluxo oposto e compromete a segurança da via. 1. Quando o candidato mantém o veículo dentro de sua faixa de rolamento e respeita a sinalização de proibição de ultrapassagem. 2. Quando o candidato aguarda o trecho permitido (linha seccionada) para realizar a manobra de forma segura. 3. Quando o candidato demonstra atenção às marcas viárias e adota conduta preventiva. 1. O examinador deve observar atentamente a reação do candidato diante da sinalização horizontal de linha contínua. 2. Caso o candidato execute a ultrapassagem pela contramão sobre a linha contínua, a infração deve ser registrada imediatamente como gravíssima. 3. O registro na ficha de avaliação deve conter a descrição detalhada do trecho e especificar o tipo de marcação viária desrespeitada (simples contínua ou dupla contínua).",
"compl": "Não há.",
"enquad": {
"art": "203-V",
"ctb": "CTB Art. 203, V",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 204",
"art": "204",
"grav": "grave",
"pontos": 4,
"nome": "Deixar de parar o veículo no acostamento à direita, para aguardar a oportunidade de cruzar a pista ou entrar à esquerda, onde não houver local apropriado para operação de retorno.",
"desc": "Durante o exame de direção, o candidato deve demonstrar capacidade de avaliar o local e o momento correto para cruzar a pista ou realizar conversão à esquerda. Quando não houver local apropriado para retorno, o condutor deve encostar e parar no acostamento à direita, aguardando o momento seguro para realizar a manobra.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato tenta cruzar a pista diretamente, sem parar no acostamento e sem aguardar o momento seguro. 2. Quando o candidato realiza manobra de conversão à esquerda com risco de colisão ou interferência no fluxo de veículos. 3. Quando o candidato não utiliza a sinalização corretamente antes da manobra.",
"naoPontua": "1. Quando o candidato encosta no acostamento à direita, sinaliza e aguarda a oportunidade segura de cruzar. 2. Quando o candidato realiza a conversão somente após garantir que a via está livre e o trânsito permite o movimento. 3. Quando o candidato demonstra controle, paciência e atenção antes de completar a manobra. 1. O examinador deve observar atentamente se o candidato adota o comportamento seguro de parar no acostamento e avaliar as condições de tráfego antes de cruzar a via. 2. Caso o candidato execute a manobra de cruzamento sem parar previamente no acostamento, a infração deve ser registrada imediatamente como grave. 3.",
"definicoes": "O registro na ficha de avaliação deve descrever o tipo de manobra executada, o local da ocorrência e se havia ou não possibilidade de parada segura no acostamento.",
"checks": "1. Quando o candidato tenta cruzar a pista diretamente, sem parar no acostamento e sem aguardar o momento seguro. 2. Quando o candidato realiza manobra de conversão à esquerda com risco de colisão ou interferência no fluxo de veículos. 3. Quando o candidato não utiliza a sinalização corretamente antes da manobra. 1. Quando o candidato encosta no acostamento à direita, sinaliza e aguarda a oportunidade segura de cruzar. 2. Quando o candidato realiza a conversão somente após garantir que a via está livre e o trânsito permite o movimento. 3. Quando o candidato demonstra controle, paciência e atenção antes de completar a manobra. 1. O examinador deve observar atentamente se o candidato adota o comportamento seguro de parar no acostamento e avaliar as condições de tráfego antes de cruzar a via. 2. Caso o candidato execute a manobra de cruzamento sem parar previamente no acostamento, a infração deve ser registrada imediatamente como grave. 3. O registro na ficha de avaliação deve descrever o tipo de manobra executada, o local da ocorrência e se havia ou não possibilidade de parada segura no acostamento.",
"compl": "Não há.",
"enquad": {
"art": "204",
"ctb": "CTB Art. 204",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 205",
"art": "205",
"grav": "leve",
"pontos": 1,
"nome": "Ultrapassar veículo em movimento que integre cortejo, préstito, desfile, e formações militares, salvo com autorização da autoridade de trânsito ou de seus agentes.",
"desc": "No exame de direção veicular, a condução do veículo de maneira segura é obrigatória, durante todo o percurso, para tanto o candidato não deve ultrapassar veículo em movimento que integre cortejo, préstito, desfile e formações militares, salvo com autorização da autoridade de trânsito ou de seus agentes.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato ao conduzir o veículo, ultrapasse veículo em movimento que integre cortejo, préstito, desfile e formações militares, durante todo o percurso. Quando autorizado pela autoridade de trânsito ou por seus agentes. 1. O examinador deve verificar se o candidato respeita as regras de circulação e não ultrapassa veículos em movimento que integrem cortejos, préstito, desfiles ou formações militares durante o percurso do exame. 2. A inobservância dessa regra demonstra desconhecimento e desrespeito às normas de trânsito. 3. Tal conduta configura infração grave prevista no art. 205 do CTB, e deve ser registrada imediatamente na ficha de avaliação como grave.",
"checks": "Quando o candidato ao conduzir o veículo, ultrapasse veículo em movimento que integre cortejo, préstito, desfile e formações militares, durante todo o percurso. Quando autorizado pela autoridade de trânsito ou por seus agentes. 1. O examinador deve verificar se o candidato respeita as regras de circulação e não ultrapassa veículos em movimento que integrem cortejos, préstito, desfiles ou formações militares durante o percurso do exame. 2. A inobservância dessa regra demonstra desconhecimento e desrespeito às normas de trânsito. 3. Tal conduta configura infração grave prevista no art. 205 do CTB, e deve ser registrada imediatamente na ficha de avaliação como grave.",
"compl": "Não há.",
"enquad": {
"art": "205",
"ctb": "CTB Art. 205",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 206-I",
"art": "206-I",
"grav": "gravissima",
"pontos": 6,
"nome": "Executar operação de retorno em local proibido pela sinalização.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato executar manobra de retorno em local onde a sinalização vertical ou horizontal proíbe expressamente essa manobra.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato ao realizar retorno ignorando a sinalização de proibição.",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato realizar o retorno mesmo havendo placa sinalizado que é proibido. A correta interpretação da sinalização é fundamental para a circulação segura. O candidato deve demonstrar atenção à sinalização vertical (R-5c, R-5d) e horizontal. O examinador deve observar se o candidato analisou o ambiente antes da manobra.",
"checks": "Quando o candidato realizar o retorno mesmo havendo placa sinalizado que é proibido. A correta interpretação da sinalização é fundamental para a circulação segura. O candidato deve demonstrar atenção à sinalização vertical (R-5c, R-5d) e horizontal. O examinador deve observar se o candidato analisou o ambiente antes da manobra.",
"compl": "Não há.",
"enquad": {
"art": "206-I",
"ctb": "CTB Art. 206, I",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 206-II",
"art": "206-II",
"grav": "gravissima",
"pontos": 6,
"nome": "Executar operação de retorno nas curvas, aclives, declives, pontes, viadutos e túneis.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato realizar manobra de retorno em locais que, pela geometria da via ou estrutura, oferecem risco à segurança e à visibilidade, como curvas, trechos elevados, túneis e áreas com baixa percepção de aproximação de outros veículos.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato ao tentar realizar retorno em trecho proibido em razão da falta de visibilidade ou risco elevado, mesmo sem haver sinalização.",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato inicia ou conclui operação de retorno em curva; Quando o candidato faz retorno em aclive ou declive impedindo visibilidade adequada; ou Quando realiza retorno em pontes, viadutos ou túneis. Quando o candidato opta por seguir até local adequado de conversão ou retorno. A manobra de retorno deve ser executada somente em locais com visibilidade plena, permitindo análise segura de tráfego em ambos os sentidos. O candidato deve avaliar o ambiente, a geometria da via e a segurança antes de iniciar a manobra. O examinador deve observar se o candidato demonstrou consciência situacional e respeito à segurança viária.",
"checks": "Quando o candidato inicia ou conclui operação de retorno em curva; Quando o candidato faz retorno em aclive ou declive impedindo visibilidade adequada; ou Quando realiza retorno em pontes, viadutos ou túneis. Quando o candidato opta por seguir até local adequado de conversão ou retorno. A manobra de retorno deve ser executada somente em locais com visibilidade plena, permitindo análise segura de tráfego em ambos os sentidos. O candidato deve avaliar o ambiente, a geometria da via e a segurança antes de iniciar a manobra. O examinador deve observar se o candidato demonstrou consciência situacional e respeito à segurança viária.",
"compl": "Não há.",
"enquad": {
"art": "206-II",
"ctb": "CTB Art. 206, II",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 206-III",
"art": "206-III",
"grav": "gravissima",
"pontos": 6,
"nome": "Executar operação de retorno passando por cima de calçada, passeio, ilhas, ajardinamento, canteiros divisores de pista, refúgios, faixas de pedestres ou faixas destinadas a veículos não motorizados.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato utiliza áreas não destinadas ao tráfego de veículos para realizar retorno, comprometendo a segurança e ultrapassando os limites físicos da pista de rolamento.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato, quando executar retorno utilizando áreas proibidas ou não destinadas à circulação veicular, como calçadas, passeios, canteiros, ilhas, refúgios e faixas específicas.",
"pontua": "1. Realizar retorno passando parcialmente ou totalmente sobre calçada ou passeio; 2. Efetuar retorno utilizando ilha, canteiro, refúgio ou área ajardinada como apoio; 3. Passar sobre faixa de pedestre ou faixa de ciclistas para completar retorno; ou 4. Utilizar área segregada ou faixa exclusiva como apoio para completar a manobra.",
"naoPontua": "1. Quando o candidato evita executar retorno ao perceber que exigiria subir em calçada ou área proibida; 2. Quando mantém trajetória dentro da pista de rolamento, suspendendo a manobra por falta de espaço seguro; ou 3. Quando faz a avaliação correta do ambiente e decide procurar um local apropriado. 1. Calçada, passeio e afins são áreas exclusivas de pedestres. 2. A utilização de faixas destinadas a modos não motorizados configura risco e desrespeito à legislação. 3.",
"definicoes": "O examinador deve observar trajetória, controle do veículo e respeito ao espaço exclusivo.",
"checks": "1. Realizar retorno passando parcialmente ou totalmente sobre calçada ou passeio; 2. Efetuar retorno utilizando ilha, canteiro, refúgio ou área ajardinada como apoio; 3. Passar sobre faixa de pedestre ou faixa de ciclistas para completar retorno; ou 4. Utilizar área segregada ou faixa exclusiva como apoio para completar a manobra. 1. Quando o candidato evita executar retorno ao perceber que exigiria subir em calçada ou área proibida; 2. Quando mantém trajetória dentro da pista de rolamento, suspendendo a manobra por falta de espaço seguro; ou 3. Quando faz a avaliação correta do ambiente e decide procurar um local apropriado. 1. Calçada, passeio e afins são áreas exclusivas de pedestres. 2. A utilização de faixas destinadas a modos não motorizados configura risco e desrespeito à legislação. 3. O examinador deve observar trajetória, controle do veículo e respeito ao espaço exclusivo.",
"compl": "Não há.",
"enquad": {
"art": "206-III",
"ctb": "CTB Art. 206, III",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 206-IV",
"art": "206-IV",
"grav": "gravissima",
"pontos": 6,
"nome": "Executar operação de retorno nas interseções, entrando na contramão de direção da via transversal.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato, ao tentar realizar retorno em interseção, ingressa na via transversal posicionando-se no sentido oposto ao correto, colocando em risco a circulação de veículos que trafegam naquela via.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato, quando realizar retorno em interseção de modo a ingressar na via transversal pela contramão de direção, ainda que de forma momentânea ou parcial.",
"pontua": "",
"naoPontua": "",
"definicoes": "1. Ingressar na via transversal pelo lado errado após tentar completar retorno; 2. Posicionar o veículo, mesmo que parcialmente, na faixa ou sentido contrário da via transversal; 3. Utilizar a contramão como apoio para completar a manobra de retorno; ou 4. Realizar retorno que obriga veículos da transversal a desviar, frear de forma brusca ou reduzir velocidade devido ao posicionamento indevido do candidato. Quando o candidato percebe que a manobra levaria à contramão e interrompe o retorno antes de ingressar na transversal; Quando realiza corretamente a conversão à direita ou esquerda dentro da via adequada, sem tentativa de retorno arriscado; ou Quando utiliza o cruzamento apenas para conversão regular, sem invadir o sentido oposto. Contramão de direção é a utilização do sentido oposto ao fluxo natural da via. O candidato deve antecipar leitura do tráfego da transversal antes de tentar qualquer manobra. Interseções exigem atenção redobrada pela presença de múltiplos fluxos e possíveis conflitos. O examinador deve observar trajetória, posicionamento e análise de risco feita pelo candidato.",
"checks": "1. Ingressar na via transversal pelo lado errado após tentar completar retorno; 2. Posicionar o veículo, mesmo que parcialmente, na faixa ou sentido contrário da via transversal; 3. Utilizar a contramão como apoio para completar a manobra de retorno; ou 4. Realizar retorno que obriga veículos da transversal a desviar, frear de forma brusca ou reduzir velocidade devido ao posicionamento indevido do candidato. Quando o candidato percebe que a manobra levaria à contramão e interrompe o retorno antes de ingressar na transversal; Quando realiza corretamente a conversão à direita ou esquerda dentro da via adequada, sem tentativa de retorno arriscado; ou Quando utiliza o cruzamento apenas para conversão regular, sem invadir o sentido oposto. Contramão de direção é a utilização do sentido oposto ao fluxo natural da via. O candidato deve antecipar leitura do tráfego da transversal antes de tentar qualquer manobra. Interseções exigem atenção redobrada pela presença de múltiplos fluxos e possíveis conflitos. O examinador deve observar trajetória, posicionamento e análise de risco feita pelo candidato.",
"compl": "Não há.",
"enquad": {
"art": "206-IV",
"ctb": "CTB Art. 206, IV",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 206-V",
"art": "206-V",
"grav": "gravissima",
"pontos": 6,
"nome": "Executar operação de retorno com prejuízo da livre circulação ou da segurança, ainda que em locais permitidos. Categoria: ACC, A, B, C, D e E.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato realiza manobra de retorno em local permitido, mas de forma insegura, causando risco, impedindo a fluidez do trânsito, obrigando outros veículos a parar, frear bruscamente ou desviar.",
"categorias": "",
"constatacao": "Será constatada durante a condução do veículo pelo candidato, quando executar retorno de modo a prejudicar a segurança ou a livre circulação, mesmo que a manobra seja realizada em local permitido.",
"pontua": "1. Retorno que obriga veículos que vêm atrás ou em sentido contrário a reduzirem a velocidade de forma brusca; 2. Retorno iniciado sem avaliação adequada do fluxo, causando risco aos demais usuários; 3. Retorno muito lento ou ampliado, invadindo faixas além do necessário; 4. Retorno que cria situação de conflito com pedestres, ciclistas ou outros veículos; ou 5. Parar indevidamente na pista para tentar completar o retorno sem análise de segurança.",
"naoPontua": "1. Quando o candidato inicia retorno apenas após garantir distância e tempo seguro em ambos os sentidos. 2. Quando evita a manobra ao perceber que afetaria a fluidez ou geraria risco. 3.",
"definicoes": "Quando realiza retorno de maneira fluida, contínua e segura, sem interferências. Local permitido não garante que a manobra seja segura — cabe ao candidato avaliar as condições. Segurança e fluidez são critérios essenciais: retorno só deve ocorrer quando não houver impacto no tráfego. O examinador deve observar:  controle do veículo;  leitura do ambiente;  respeito ao fluxo; e  decisão adequada do momento de executar a manobra. Manobras hesitantes, lentas ou arriscadas que gerem interferência configuram anotação da falta.",
"checks": "1. Retorno que obriga veículos que vêm atrás ou em sentido contrário a reduzirem a velocidade de forma brusca; 2. Retorno iniciado sem avaliação adequada do fluxo, causando risco aos demais usuários; 3. Retorno muito lento ou ampliado, invadindo faixas além do necessário; 4. Retorno que cria situação de conflito com pedestres, ciclistas ou outros veículos; ou 5. Parar indevidamente na pista para tentar completar o retorno sem análise de segurança. 1. Quando o candidato inicia retorno apenas após garantir distância e tempo seguro em ambos os sentidos. 2. Quando evita a manobra ao perceber que afetaria a fluidez ou geraria risco. 3. Quando realiza retorno de maneira fluida, contínua e segura, sem interferências. Local permitido não garante que a manobra seja segura — cabe ao candidato avaliar as condições. Segurança e fluidez são critérios essenciais: retorno só deve ocorrer quando não houver impacto no tráfego. O examinador deve observar:  controle do veículo;  leitura do ambiente;  respeito ao fluxo; e  decisão adequada do momento de executar a manobra. Manobras hesitantes, lentas ou arriscadas que gerem interferência configuram anotação da falta.",
"compl": "Não há.",
"enquad": {
"art": "206-V",
"ctb": "CTB Art. 206, V",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 207",
"art": "207",
"grav": "grave",
"pontos": 4,
"nome": "Executar operação de conversão à direita ou à esquerda em locais proibidos pela sinalização.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato realizar conversão à direita ou à esquerda em local onde exista sinalização proibitiva específica, desrespeitando a orientação indicada na via.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato, quando realizar conversão em local sinalizado como proibido, seja por sinalização vertical ou horizontal.",
"pontua": "1. Realizar conversão onde exista placa de proibido virar à direita ou à esquerda; 2. Executar conversão em local com marcas viárias que impeçam formalmente a manobra (linhas contínuas, direcionamento obrigatório etc.); ou 3. Realizar conversão que conflite com o fluxo permitido, conforme a sinalização existente.",
"naoPontua": "1. Quando o candidato percebe a sinalização de proibição e segue em frente sem tentar converter. 2. Quando opta por converter apenas no local permitido, mesmo que mais distante. 3. Quando ajusta corretamente a trajetória ao identificar mudança na organização da via. 1. A conversão deve obedecer rigorosamente à sinalização vertical (R-5a, R-5b) e horizontal. 2. O candidato deve demonstrar percepção antecipada da via e planejamento da manobra. 3.",
"definicoes": "O examinador deve atentar para a tomada de decisão, trajetória e respeito aos dispositivos regulamentares.",
"checks": "1. Realizar conversão onde exista placa de proibido virar à direita ou à esquerda; 2. Executar conversão em local com marcas viárias que impeçam formalmente a manobra (linhas contínuas, direcionamento obrigatório etc.); ou 3. Realizar conversão que conflite com o fluxo permitido, conforme a sinalização existente. 1. Quando o candidato percebe a sinalização de proibição e segue em frente sem tentar converter. 2. Quando opta por converter apenas no local permitido, mesmo que mais distante. 3. Quando ajusta corretamente a trajetória ao identificar mudança na organização da via. 1. A conversão deve obedecer rigorosamente à sinalização vertical (R-5a, R-5b) e horizontal. 2. O candidato deve demonstrar percepção antecipada da via e planejamento da manobra. 3. O examinador deve atentar para a tomada de decisão, trajetória e respeito aos dispositivos regulamentares.",
"compl": "Não há.",
"enquad": {
"art": "207",
"ctb": "CTB Art. 207",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 208",
"art": "208",
"grav": "gravissima",
"pontos": 6,
"nome": "Avançar o sinal vermelho do semáforo ou o de parada obrigatória, exceto onde houver sinalização que permita a livre conversão à direita prevista no art. 44-A.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato deixa de obedecer ao sinal vermelho do semáforo ou à placa de Parada Obrigatória (R-1), colocando em risco a segurança da circulação. Não se caracteriza a falta quando houver sinalização que autorize a livre conversão à direita nos termos do art. 44-A.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato, quando avançar o sinal vermelho ou deixar de parar totalmente na parada obrigatória, salvo nos locais especificamente autorizados para livre conversão à direita.",
"pontua": "1. Avançar o sinal vermelho; 2. Não efetuar a parada total diante de placa R-1 (Parada Obrigatória); 3.Realizar conversão ou seguir em frente sem respeitar a ordem de parada.",
"naoPontua": "1. Parar completamente antes da faixa de retenção ou linha de parada. 2. Aguardar a abertura do sinal mesmo sem fluxo imediato. Realizar a conversão livre à direita somente quando houver sinalização autorizando expressamente (art. 44-A). 3. Parar e depois avançar em cruzamento com R-1 corretamente. 1. A obediência aos dispositivos de controle de tráfego (semafóricos e sinalização de parada) é fundamental para segurança. 2.",
"definicoes": "A parada obrigatória deve ser completa, com o veículo totalmente imóvel. O examinador deve observar:  parada antes da faixa de retenção;  respeito ao pedestre;  tomada de decisão diante do semáforo.",
"checks": "1. Avançar o sinal vermelho; 2. Não efetuar a parada total diante de placa R-1 (Parada Obrigatória); 3.Realizar conversão ou seguir em frente sem respeitar a ordem de parada. 1. Parar completamente antes da faixa de retenção ou linha de parada. 2. Aguardar a abertura do sinal mesmo sem fluxo imediato. Realizar a conversão livre à direita somente quando houver sinalização autorizando expressamente (art. 44-A). 3. Parar e depois avançar em cruzamento com R-1 corretamente. 1. A obediência aos dispositivos de controle de tráfego (semafóricos e sinalização de parada) é fundamental para segurança. 2. A parada obrigatória deve ser completa, com o veículo totalmente imóvel. O examinador deve observar:  parada antes da faixa de retenção;  respeito ao pedestre;  tomada de decisão diante do semáforo.",
"compl": "Não há.",
"enquad": {
"art": "208",
"ctb": "CTB Art. 208",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 210",
"art": "210",
"grav": "gravissima",
"pontos": 6,
"nome": "Transpor, sem autorização, bloqueio viário policial.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato ignora, desrespeita ou ultrapassa ponto de bloqueio policial, barreira, fiscalização ou ordem de parada emanada da autoridade de trânsito ou policial.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato, quando ultrapassar ou ignorar bloqueio viário policial ou ordem clara de parada, independentemente da sinalização adicional utilizada.",
"pontua": "1. Transpor cone, barreira, viatura ou ponto de bloqueio policial sem autorização; 2. Seguir adiante após ordem de parada emitida por agente ou policial; 3. Utilizar acostamento, calçada ou qualquer outro espaço para desviar do bloqueio; 4. Avançar lentamente, tentando passar mesmo com ordem de retenção; ou 5. Movimentar o veículo antes da liberação por gesto ou sinal do agente.",
"naoPontua": "1. Quando o candidato reduz a velocidade e aguarda instrução do agente. 2. Quando para corretamente no local indicado pelo policial. 3. Quando avança somente após sinalização clara autorizando a continuidade da marcha. 4.Quando o candidato demonstra atenção, respeito e leitura correta das orientações. 1. Bloqueio viário policial tem caráter de segurança e fiscalização — deve ser respeitado integralmente. 2. A parada deve ocorrer antes da barreira, salvo instrução específica. 3.",
"definicoes": "O examinador deve observar:  reação do candidato ao bloqueio;  atenção às ordens do agente;  posicionamento e controle do veículo;  interpretação correta da sinalização manual.",
"checks": "1. Transpor cone, barreira, viatura ou ponto de bloqueio policial sem autorização; 2. Seguir adiante após ordem de parada emitida por agente ou policial; 3. Utilizar acostamento, calçada ou qualquer outro espaço para desviar do bloqueio; 4. Avançar lentamente, tentando passar mesmo com ordem de retenção; ou 5. Movimentar o veículo antes da liberação por gesto ou sinal do agente. 1. Quando o candidato reduz a velocidade e aguarda instrução do agente. 2. Quando para corretamente no local indicado pelo policial. 3. Quando avança somente após sinalização clara autorizando a continuidade da marcha. 4.Quando o candidato demonstra atenção, respeito e leitura correta das orientações. 1. Bloqueio viário policial tem caráter de segurança e fiscalização — deve ser respeitado integralmente. 2. A parada deve ocorrer antes da barreira, salvo instrução específica. 3. O examinador deve observar:  reação do candidato ao bloqueio;  atenção às ordens do agente;  posicionamento e controle do veículo;  interpretação correta da sinalização manual.",
"compl": "Não há.",
"enquad": {
"art": "210",
"ctb": "CTB Art. 210",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 211",
"art": "211",
"grav": "grave",
"pontos": 4,
"nome": "Ultrapassar veículos em fila, parados devido a semáforo, cancela, bloqueio viário parcial ou qualquer outro obstáculo, exceto veículos não motorizados. Categoria: ACC, A, B, C, D e E.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato ultrapassar pela esquerda ou pela direita veículos que aguardam em fila, parados em função de semáforo, cancelas (ferrovia, pedágio), bloqueios ou obstáculos temporários, criando risco ou vantagem indevida na circulação.",
"categorias": "",
"constatacao": "Será constatada durante a condução do veículo pelo candidato, quando ultrapassar veículos enfileirados em razão de interrupção momentânea de tráfego, independentemente do lado utilizado, salvo quando ultrapassar veículo não motorizado.",
"pontua": "",
"naoPontua": "",
"definicoes": "1. Ultrapassar pela esquerda veículos parados no semáforo em fila; 2. Ultrapassar pela direita veículos parados diante de cancela ou bloqueio; 3. Utilizar acostamento, calçada ou qualquer espaço lateral para avançar sobre a fila; 4. Realizar ultrapassagem em fila para transpor o bloqueio, entrada de túnel, pedágio ou passagem estreita; ou 5. Utilizar faixa exclusiva ou de pedestres como trajeto para ganhar posição. A fila caracteriza veículos aguardando impedimento temporário da circulação — não deve ser ultrapassada. O examinador deve observar:  tentativa de “furar fila”;  uso inadequado de áreas laterais;  risco gerado a pedestres ou veículos;  respeito ao fluxo interrompido. A avaliação deve levar em conta a trajetória, intenção e tomada de decisão do candidato.",
"checks": "1. Ultrapassar pela esquerda veículos parados no semáforo em fila; 2. Ultrapassar pela direita veículos parados diante de cancela ou bloqueio; 3. Utilizar acostamento, calçada ou qualquer espaço lateral para avançar sobre a fila; 4. Realizar ultrapassagem em fila para transpor o bloqueio, entrada de túnel, pedágio ou passagem estreita; ou 5. Utilizar faixa exclusiva ou de pedestres como trajeto para ganhar posição. A fila caracteriza veículos aguardando impedimento temporário da circulação — não deve ser ultrapassada. O examinador deve observar:  tentativa de “furar fila”;  uso inadequado de áreas laterais;  risco gerado a pedestres ou veículos;  respeito ao fluxo interrompido. A avaliação deve levar em conta a trajetória, intenção e tomada de decisão do candidato.",
"compl": "Não há.",
"enquad": {
"art": "211",
"ctb": "CTB Art. 211",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 212",
"art": "212",
"grav": "gravissima",
"pontos": 6,
"nome": "Deixar de parar o veículo antes de transpor linha férrea.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato deixa de realizar a parada obrigatória antes da passagem de nível com linha férrea, independentemente da presença ou não de barreiras, sinalização eletrônica, placas ou dispositivos de advertência adicionais.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato, quando deixar de parar totalmente antes de cruzar linha férrea, seja em passagem com cancela, sinalização ativa/inativa ou apenas sinalização estática.",
"pontua": "1. Transpor linha férrea sem parada total, mesmo sem aproximação de trem; Reduzir a velocidade, mas atravessar sem imobilizar o veículo; 2. Parar sobre os trilhos ou avançar parcialmente antes da parada; 3. Parar após a linha de retenção, impedindo a visão adequada do fluxo ferroviário; ou 4. Desobedecer às placas de advertência ou de parada referentes à passagem de nível.",
"naoPontua": "1. Quando o candidato realiza parada total antes dos trilhos, observando ambos os lados. 2. Quando aguarda abertura de cancela, sinal luminoso ou autorização sonora. 3. Quando avança somente após garantir desobstrução completa da via férrea. 4. Quando realiza controle adequado de velocidade e aproximação segura. 1. A parada antes da linha férrea é obrigatória em qualquer circunstância. 2. O candidato deve demonstrar:  parada total;  atenção ao entorno;  checagem visual para ambos os lados;  controle do veículo ao retomar a marcha. 3.",
"definicoes": "O examinador deve observar especialmente a imobilização completa do veículo.",
"checks": "1. Transpor linha férrea sem parada total, mesmo sem aproximação de trem; Reduzir a velocidade, mas atravessar sem imobilizar o veículo; 2. Parar sobre os trilhos ou avançar parcialmente antes da parada; 3. Parar após a linha de retenção, impedindo a visão adequada do fluxo ferroviário; ou 4. Desobedecer às placas de advertência ou de parada referentes à passagem de nível. 1. Quando o candidato realiza parada total antes dos trilhos, observando ambos os lados. 2. Quando aguarda abertura de cancela, sinal luminoso ou autorização sonora. 3. Quando avança somente após garantir desobstrução completa da via férrea. 4. Quando realiza controle adequado de velocidade e aproximação segura. 1. A parada antes da linha férrea é obrigatória em qualquer circunstância. 2. O candidato deve demonstrar:  parada total;  atenção ao entorno;  checagem visual para ambos os lados;  controle do veículo ao retomar a marcha. 3. O examinador deve observar especialmente a imobilização completa do veículo.",
"compl": "Não há.",
"enquad": {
"art": "212",
"ctb": "CTB Art. 212",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 213-I",
"art": "213-I",
"grav": "gravissima",
"pontos": 6,
"nome": "Deixar de parar o veículo sempre que a respectiva marcha for interceptada por agrupamento de pessoas, como préstitos, passeatas, desfiles e outros.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato não interrompe totalmente a marcha do veículo diante de um agrupamento de pessoas que impede a continuidade da circulação, independentemente de haver sinalização, agente ou indicação adicional.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato, quando deixar de parar totalmente o veículo ao ter sua marcha bloqueada, parcial ou totalmente, por agrupamento de pessoas.",
"pontua": "1. Não parar diante de passeata, desfile, grupo escolar, religioso ou comunitário que interfira no fluxo; 2. Avançar lentamente tentando cruzar o agrupamento; 3. Forçar passagem entre pessoas que estejam ocupando a via; ou 4. Contornar pela calçada, acostamento ou área proibida para evitar parar. 1.Quando o candidato interrompe completamente a marcha diante do agrupamento. 2. Quando mantém distância segura dos pedestres. 3.Quando aguarda calmamente até a liberação da via. 4. Quando posiciona o veículo corretamente antes da faixa ou limite seguro.",
"naoPontua": "1. Agrupamento de pessoas é qualquer reunião que impeça a continuidade natural do tráfego. 2. A prioridade absoluta é dos pedestres em situação de interseção de fluxo. 3.",
"definicoes": "O examinador deve observar:  parada total;  manutenção da distância segura;  controle emocional e do veículo;  ausência de pressão sobre pedestres.",
"checks": "1. Não parar diante de passeata, desfile, grupo escolar, religioso ou comunitário que interfira no fluxo; 2. Avançar lentamente tentando cruzar o agrupamento; 3. Forçar passagem entre pessoas que estejam ocupando a via; ou 4. Contornar pela calçada, acostamento ou área proibida para evitar parar. 1.Quando o candidato interrompe completamente a marcha diante do agrupamento. 2. Quando mantém distância segura dos pedestres. 3.Quando aguarda calmamente até a liberação da via. 4. Quando posiciona o veículo corretamente antes da faixa ou limite seguro. 1. Agrupamento de pessoas é qualquer reunião que impeça a continuidade natural do tráfego. 2. A prioridade absoluta é dos pedestres em situação de interseção de fluxo. 3. O examinador deve observar:  parada total;  manutenção da distância segura;  controle emocional e do veículo;  ausência de pressão sobre pedestres.",
"compl": "Não há.",
"enquad": {
"art": "213-I",
"ctb": "CTB Art. 213, I",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 213-II",
"art": "213-II",
"grav": "grave",
"pontos": 4,
"nome": "Deixar de parar o veículo sempre que a respectiva marcha for interceptada por agrupamento de veículos, como cortejos, formações militares e outros.",
"desc": "No exame de direção veicular, esta falta deverá ser anotada quando o candidato, ao se deparar com agrupamento organizado de veículos que impede a continuidade da circulação, deixa de interromper completamente a marcha, colocando em risco a segurança e o ordenamento do fluxo.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato, quando não realizar parada total ao ter sua marcha bloqueada por cortejo, comboio, formação militar ou qualquer agrupamento organizado de veículos.",
"pontua": "1. Não parar completamente diante de cortejo, comboio militar, comboio escolar ou procissão motorizada; 2. Tentar avançar entre veículos agrupados; 3. Contornar o bloqueio por calçada, acostamento ou área proibida; 4. Demonstrar pressão ou aproximação excessiva sobre o agrupamento; ou 5. Realizar manobra brusca, perigosa ou impaciente diante da interrupção da marcha.",
"naoPontua": "1. Quando o candidato para totalmente ao visualizar agrupamento interrompendo o fluxo. 2. Quando aguarda a liberação mantendo distância segura e postura adequada. 3. Quando respeita o ritmo e organização do comboio, sem interferir. 4. Quando identifica previamente o agrupamento e reduz de forma segura. 1. Agrupamento de veículos é qualquer conjunto organizado que ocupe a via e interrompa a circulação normal. 2.",
"definicoes": "O examinador deve observar:  parada total;  distância adequada;  respeito aos veículos do agrupamento;  controle da trajetória e velocidade;  ausência de tentativa de ultrapassagem ou de avanço.",
"checks": "1. Não parar completamente diante de cortejo, comboio militar, comboio escolar ou procissão motorizada; 2. Tentar avançar entre veículos agrupados; 3. Contornar o bloqueio por calçada, acostamento ou área proibida; 4. Demonstrar pressão ou aproximação excessiva sobre o agrupamento; ou 5. Realizar manobra brusca, perigosa ou impaciente diante da interrupção da marcha. 1. Quando o candidato para totalmente ao visualizar agrupamento interrompendo o fluxo. 2. Quando aguarda a liberação mantendo distância segura e postura adequada. 3. Quando respeita o ritmo e organização do comboio, sem interferir. 4. Quando identifica previamente o agrupamento e reduz de forma segura. 1. Agrupamento de veículos é qualquer conjunto organizado que ocupe a via e interrompa a circulação normal. 2. O examinador deve observar:  parada total;  distância adequada;  respeito aos veículos do agrupamento;  controle da trajetória e velocidade;  ausência de tentativa de ultrapassagem ou de avanço.",
"compl": "Não há.",
"enquad": {
"art": "213-II",
"ctb": "CTB Art. 213, II",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 214",
"art": "214",
"grav": "gravissima",
"pontos": 6,
"nome": "Deixar de dar preferência de passagem a pedestre e a veículo não motorizado: I - que se encontre na faixa a ele destinada.",
"desc": "A falta deverá ser anotada quando o candidato não respeitar a preferência do pedestre ou veículo não motorizado que esteja aguardando para iniciar a travessia.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato não parar o veículo para travessia de pedestre ou de veículo não motorizado. Quando pedestre ou o veículo não motorizado estavam longe da área de início da travessia; Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"checks": "Quando o candidato não parar o veículo para travessia de pedestre ou de veículo não motorizado. Quando pedestre ou o veículo não motorizado estavam longe da área de início da travessia; Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"compl": "Não há.",
"enquad": {
"art": "214",
"ctb": "CTB Art. 214",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 214 (2)",
"art": "214",
"grav": "gravissima",
"pontos": 6,
"nome": "Deixar de dar preferência de passagem a pedestre e a veículo não motorizado: II - que não haja concluído a travessia mesmo que ocorra sinal verde para o veículo.",
"desc": "A falta deverá ser anotada quando o candidato movimentar o veículo e o pedestre ou o veículo não motorizado não ter concluído a travessia.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "1. Quando o candidato avançar com o veículo enquanto pedestre ou veículo não motorizado estiver em travessia e ainda não a tiver concluído; 2. Quando, mesmo em sinal verde autorizado o candidato a seguir ele tiver movimentado o veículo sem que o pedestre ou o veículo não motorizado haja concluído a travessia. Quando pedestre ou o veículo não motorizado estiver concluído a travessia. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"checks": "1. Quando o candidato avançar com o veículo enquanto pedestre ou veículo não motorizado estiver em travessia e ainda não a tiver concluído; 2. Quando, mesmo em sinal verde autorizado o candidato a seguir ele tiver movimentado o veículo sem que o pedestre ou o veículo não motorizado haja concluído a travessia. Quando pedestre ou o veículo não motorizado estiver concluído a travessia. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"compl": "Não há.",
"enquad": {
"art": "214",
"ctb": "CTB Art. 214",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 214 (3)",
"art": "214",
"grav": "gravissima",
"pontos": 6,
"nome": "Deixar de dar preferência de passagem a pedestre e a veículo não motorizado: III - portadores de deficiência física, crianças, idosos e gestantes.",
"desc": "A falta deverá ser anotada quando o candidato movimentar o veículo não respeitando a preferência de pessoas com deficiência, crianças, idosos e gestantes.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato não der preferência a travessia de pessoas com deficiência, crianças, idosos e gestantes. Quando o as pessoas relacionadas não estiverem próximo a área de travessia ou em via. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"checks": "Quando o candidato não der preferência a travessia de pessoas com deficiência, crianças, idosos e gestantes. Quando o as pessoas relacionadas não estiverem próximo a área de travessia ou em via. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"compl": "Não há.",
"enquad": {
"art": "214",
"ctb": "CTB Art. 214",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 214 (4)",
"art": "214",
"grav": "grave",
"pontos": 4,
"nome": "Deixar de dar preferência de passagem a pedestre e a veículo não motorizado: IV - quando houver iniciado a travessia mesmo que não haja sinalização a ele destinada.",
"desc": "A falta deverá ser anotada quando o candidato movimentar o veículo não respeitando a passagem ou a travessia de pedestres ou veículos não motorizados mesmo que em locais onde não haja indicação de faixa destinada a travessia ou passagem.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato não der preferência a travessia mesmo em locais não destinados a travessia ou passagem. Quando o pedestre ou veículo não motorizado não estiver em local próximo à área de travessia ou em via. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"checks": "Quando o candidato não der preferência a travessia mesmo em locais não destinados a travessia ou passagem. Quando o pedestre ou veículo não motorizado não estiver em local próximo à área de travessia ou em via. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"compl": "Não há.",
"enquad": {
"art": "214",
"ctb": "CTB Art. 214",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 214 (5)",
"art": "214",
"grav": "grave",
"pontos": 4,
"nome": "Deixar de dar preferência de passagem a pedestre e a veículo não motorizado: V - que esteja atravessando a via transversal para onde se dirige o veículo.",
"desc": "A falta deverá ser anotada quando o candidato não der a preferência ao pedestre ou veículo que esteja em via transversal.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato não der preferência a passagem ou travessia de pedestre que esteja em direção transversal ao seu sentido de direção Quando o pedestre ou veículo não motorizado não estiver em local atravessando em via transversal. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"checks": "Quando o candidato não der preferência a passagem ou travessia de pedestre que esteja em direção transversal ao seu sentido de direção Quando o pedestre ou veículo não motorizado não estiver em local atravessando em via transversal. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"compl": "Não há.",
"enquad": {
"art": "214",
"ctb": "CTB Art. 214",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 215",
"art": "215",
"grav": "grave",
"pontos": 4,
"nome": "Deixar de dar preferência de passagem: I - em interseção não sinalizada: a) a veículo que estiver circulando por rodovia ou rotatória.",
"desc": "A falta deverá ser anotada quando o candidato não der a preferência ao veículo que já estiver circulando em rotatória, ou quando não respeitar a preferência de passagem ao circular ou entrar em outra via.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "1. Quando o candidato não respeitar a preferência de veículos que circulem vias de trânsito rápido; 2. Quando o candidato não respeitar a preferência em vias perpendiculares; 3. Quando não der preferência ao veículo que já estiver circulando na rotatória.",
"naoPontua": "1. Quando a preferência para a circulação na via for do candidato; 2. Quando a preferência para circulação na rotatória for do candidato; 3.",
"definicoes": "Quando o candidato não der preferência ao veículo que estiver a sua direita. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"checks": "1. Quando o candidato não respeitar a preferência de veículos que circulem vias de trânsito rápido; 2. Quando o candidato não respeitar a preferência em vias perpendiculares; 3. Quando não der preferência ao veículo que já estiver circulando na rotatória. 1. Quando a preferência para a circulação na via for do candidato; 2. Quando a preferência para circulação na rotatória for do candidato; 3. Quando o candidato não der preferência ao veículo que estiver a sua direita. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"compl": "Não há.",
"enquad": {
"art": "215",
"ctb": "CTB Art. 215",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 215 (2)",
"art": "215",
"grav": "grave",
"pontos": 4,
"nome": "Deixar de dar preferência de passagem: I - em interseção não sinalizada: b) a veículo que vier da direita;",
"desc": "A falta deverá ser anotada quando o candidato não der a preferência em momentos de intersecção ao veículo estiver à direita e desejar mudar de sentido de direção.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato não respeitar der preferência ao veículo que estiver à sua direita e desejar realizar a intersecção de direção. Quando a preferência para a intersecção for do candidato. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"checks": "Quando o candidato não respeitar der preferência ao veículo que estiver à sua direita e desejar realizar a intersecção de direção. Quando a preferência para a intersecção for do candidato. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"compl": "Não há.",
"enquad": {
"art": "215",
"ctb": "CTB Art. 215",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 215 (3)",
"art": "215",
"grav": "grave",
"pontos": 4,
"nome": "Deixar de dar preferência de passagem: II - nas interseções com sinalização de regulamentação de “Dê a Preferência”.",
"desc": "A falta deverá ser anotada quando o candidato não der a preferência onde houver sinalização indicativa.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato avançar desrespeitando a sinalização de “dê a preferência”. 1. Quando a preferência para a intersecção for do candidato; ou 2. Quando não houver sinalização indicativa. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"checks": "Quando o candidato avançar desrespeitando a sinalização de “dê a preferência”. 1. Quando a preferência para a intersecção for do candidato; ou 2. Quando não houver sinalização indicativa. Se houver risco iminente, o examinador deve, com cautela, solicitar que o candidato pare o veículo, podendo seguir quando for seguro. Não havendo perigo, o examinador deve anotar a ocorrência na ficha de avaliação e aplicar a pontuação correspondente.",
"compl": "Não há.",
"enquad": {
"art": "215",
"ctb": "CTB Art. 215",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 216",
"art": "216",
"grav": "media",
"pontos": 2,
"nome": "Entrar ou sair de áreas lindeiras sem estar adequadamente posicionado para ingresso na via e sem as precauções com a segurança de pedestres e de outros veículos.",
"desc": "No exame de direção veicular, a conduta infracional consiste em entrar ou sair de áreas lindeiras (que margeiam a via) sem cumprir duas exigências fundamentais de segurança e circulação, durante todo o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Veículo que entrar ou sair de áreas lindeiras sem dar preferência de passagem a veículos ou pedestres que circulem pela via. Quando a intenção do condutor for de ameaçar os pedestres ou outros veículos, pode configurar a infração do art. 170 do CTB. O termo área lindeira (ou lote lindeiro), conforme o Anexo I do CTB, refere-se a qualquer imóvel, estabelecimento ou terreno que se limita diretamente com a via pública (ruas, avenidas, rodovias). Exemplos comuns:  Garagens residenciais ou de edifícios;  Estacionamentos de supermercados e shoppings;  Postos de combustíveis; e  Empresas e terrenos com acesso direto à rua.",
"checks": "Veículo que entrar ou sair de áreas lindeiras sem dar preferência de passagem a veículos ou pedestres que circulem pela via. Quando a intenção do condutor for de ameaçar os pedestres ou outros veículos, pode configurar a infração do art. 170 do CTB. O termo área lindeira (ou lote lindeiro), conforme o Anexo I do CTB, refere-se a qualquer imóvel, estabelecimento ou terreno que se limita diretamente com a via pública (ruas, avenidas, rodovias). Exemplos comuns:  Garagens residenciais ou de edifícios;  Estacionamentos de supermercados e shoppings;  Postos de combustíveis; e  Empresas e terrenos com acesso direto à rua.",
"compl": "Não há.",
"enquad": {
"art": "216",
"ctb": "CTB Art. 216",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 217",
"art": "217",
"grav": "media",
"pontos": 2,
"nome": "Entrar ou sair de fila de veículos estacionados sem dar preferência de passagem a pedestres e a outros veículos.",
"desc": "No exame de direção veicular, a infração ocorre quando o condutor realiza o movimento de entrar ou sair de uma fila de veículos estacionados sem garantir a segurança e a fluidez dos outros usuários da via, durante todo o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "1. A infração para a falta de cautela e a inobservância da preferência ao iniciar ou finalizar uma manobra de estacionamento, envolvendo o deslocamento da fila de veículos. 2. A infração ocorre quando o condutor realiza o movimento de entrar ou sair de uma fila de veículos estacionados sem garantir a segurança e a fluidez dos outros usuários da via. 3. A infração se configura se o condutor não sinaliza a intenção ou realiza a manobra de forma abrupta, interceptando a trajetória de pedestres ou outros veículos em circulação.",
"naoPontua": "1. Entrar ou sair de fila de veículos estacionados: a) Entrar na fila: manobrar o veículo da faixa de circulação para ocupar uma vaga de estacionamento. b) Sair da fila: manobrar o veículo da vaga de estacionamento para ingressar na faixa de circulação. 2.",
"definicoes": "Sem dar preferência de passagem A infração se caracteriza quando, durante a manobra, o condutor deixa de ceder a preferência a: a) Pedestres: aqueles que circulam na calçada (passeio) ou que estão próximos à vaga. b) Outros veículos: aqueles que já estão transitando na via e têm a prioridade de circulação.",
"checks": "1. A infração para a falta de cautela e a inobservância da preferência ao iniciar ou finalizar uma manobra de estacionamento, envolvendo o deslocamento da fila de veículos. 2. A infração ocorre quando o condutor realiza o movimento de entrar ou sair de uma fila de veículos estacionados sem garantir a segurança e a fluidez dos outros usuários da via. 3. A infração se configura se o condutor não sinaliza a intenção ou realiza a manobra de forma abrupta, interceptando a trajetória de pedestres ou outros veículos em circulação. 1. Entrar ou sair de fila de veículos estacionados: a) Entrar na fila: manobrar o veículo da faixa de circulação para ocupar uma vaga de estacionamento. b) Sair da fila: manobrar o veículo da vaga de estacionamento para ingressar na faixa de circulação. 2. Sem dar preferência de passagem A infração se caracteriza quando, durante a manobra, o condutor deixa de ceder a preferência a: a) Pedestres: aqueles que circulam na calçada (passeio) ou que estão próximos à vaga. b) Outros veículos: aqueles que já estão transitando na via e têm a prioridade de circulação.",
"compl": "Não há.",
"enquad": {
"art": "217",
"ctb": "CTB Art. 217",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 218",
"art": "218",
"grav": "media",
"pontos": 2,
"nome": "Transitar em velocidade superior à máxima permitida para o local, medida por instrumento ou equipamento hábil, em rodovias, vias de trânsito rápido, vias arteriais e demais vias: I - quando a velocidade for superior à máxima em até 20%.",
"desc": "No exame de direção veicular, a infração ocorre quando o condutor é flagrado transitando em velocidade superior à máxima regulamentada para a via, mas o excesso não ultrapassa 20% desse limite, durante o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "1. Excesso de velocidade: A velocidade registrada no momento da fiscalização é superior à máxima estabelecida na sinalização (placa R- 19). 2. Limite de excesso: A velocidade aferida deve ser superior ao limite, mas não pode exceder 20% desse limite. Caso o excesso seja superior a 20%, pode configurar as infrações do art. 218, incisos II ou III. A verificação da velocidade se dá pelo acompanhamento do examinador ao painel do veículo ou pelo equipamento de medição de velocidade. Sendo configurada conforme tabela exemplificativa.",
"checks": "1. Excesso de velocidade: A velocidade registrada no momento da fiscalização é superior à máxima estabelecida na sinalização (placa R- 19). 2. Limite de excesso: A velocidade aferida deve ser superior ao limite, mas não pode exceder 20% desse limite. Caso o excesso seja superior a 20%, pode configurar as infrações do art. 218, incisos II ou III. A verificação da velocidade se dá pelo acompanhamento do examinador ao painel do veículo ou pelo equipamento de medição de velocidade. Sendo configurada conforme tabela exemplificativa.",
"compl": "Tabela exemplificativa:",
"enquad": {
"art": "218",
"ctb": "CTB Art. 218",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 218 (2)",
"art": "218",
"grav": "grave",
"pontos": 4,
"nome": "Transitar em velocidade superior à máxima permitida para o local, medida por instrumento ou equipamento hábil, em rodovias, vias de trânsito rápido, vias arteriais e demais vias: II - quando a velocidade for superior à máxima em mais de 20% até 50%.",
"desc": "No exame de direção veicular, a infração ocorre quando o condutor é flagrado transitando em velocidade superior à máxima regulamentada para a via, sendo 20% até 50% desse limite, durante o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "1. Excesso de velocidade: A velocidade registrada no momento da fiscalização é superior à máxima estabelecida na sinalização (placa R-19). 2. Limite de excesso: A velocidade aferida deve ser superior ao limite, sendo entre 20% e 50% desse limite. Caso o excesso de velocidade seja abaixo de 20% do limite, configura-se a infração do art. 218, inciso I; caso seja superior a 50%, configura a infração do art. 218, inciso III. A verificação da velocidade, se dá pelo acompanhamento do examinador ao painel do veículo ou pelo equipamento de medição de velocidade. Sendo configurada conforme tabela exemplificativa.",
"checks": "1. Excesso de velocidade: A velocidade registrada no momento da fiscalização é superior à máxima estabelecida na sinalização (placa R-19). 2. Limite de excesso: A velocidade aferida deve ser superior ao limite, sendo entre 20% e 50% desse limite. Caso o excesso de velocidade seja abaixo de 20% do limite, configura-se a infração do art. 218, inciso I; caso seja superior a 50%, configura a infração do art. 218, inciso III. A verificação da velocidade, se dá pelo acompanhamento do examinador ao painel do veículo ou pelo equipamento de medição de velocidade. Sendo configurada conforme tabela exemplificativa.",
"compl": "Tabela exemplificativa",
"enquad": {
"art": "218",
"ctb": "CTB Art. 218",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 218 (3)",
"art": "218",
"grav": "gravissima",
"pontos": 6,
"nome": "Transitar em velocidade superior à máxima permitida para o local, medida por instrumento ou equipamento hábil, em rodovias, vias de trânsito rápido, vias arteriais e demais vias: III - quando a velocidade for superior à máxima em mais de 50%.",
"desc": "No exame de direção veicular, a infração ocorre quando o condutor é flagrado transitando em velocidade superior à máxima regulamentada para a via, em mais de 50% desse limite, durante o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "1. Excesso de velocidade: A velocidade registrada no momento da fiscalização é superior à máxima estabelecida na sinalização (placa R- 19). 2. Limite de excesso: A velocidade aferida deve ser superior ao limite, em mais de 50% desse limite. Caso o excesso de velocidade seja abaixo de 20% do limite, configura-se a infração do art. 218, inciso I; caso seja entre 20% a 50%, configura a infração do art. 218, inciso II. A verificação da velocidade, se dá pelo acompanhamento do examinador ao painel do veículo ou pelo equipamento de medição de velocidade. Sendo configurada conforme tabela exemplificativa.",
"checks": "1. Excesso de velocidade: A velocidade registrada no momento da fiscalização é superior à máxima estabelecida na sinalização (placa R- 19). 2. Limite de excesso: A velocidade aferida deve ser superior ao limite, em mais de 50% desse limite. Caso o excesso de velocidade seja abaixo de 20% do limite, configura-se a infração do art. 218, inciso I; caso seja entre 20% a 50%, configura a infração do art. 218, inciso II. A verificação da velocidade, se dá pelo acompanhamento do examinador ao painel do veículo ou pelo equipamento de medição de velocidade. Sendo configurada conforme tabela exemplificativa.",
"compl": "Tabela exemplificativa:",
"enquad": {
"art": "218",
"ctb": "CTB Art. 218",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 219",
"art": "219",
"grav": "media",
"pontos": 2,
"nome": "Transitar com o veículo em velocidade inferior à metade da velocidade máxima estabelecida para a via, retardando ou obstruindo o trânsito, a menos que as condições de tráfego e meteorológicas não o permitam, salvo se estiver na faixa da direita.",
"desc": "No exame de direção veicular, pune o condutor que, sem justificativa válida, trafega de forma muito lenta, tornando-se um obstáculo e um fator de risco para o fluxo normal de veículos, durante o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "Será constatada durante a condução do veículo pelo candidato.",
"pontua": "",
"naoPontua": "",
"definicoes": "Veículo transitando em velocidade inferior à metade da velocidade máxima estabelecida para a via, retardando ou obstruindo o trânsito. 1. Quando as condições de tráfego e meteorológicas não o permitirem transitar na velocidade regulamentada; ou 2. Quando o veículo estiver na faixa da direita. A verificação da velocidade, se dá pelo acompanhamento do examinador ao painel do veículo ou pelo equipamento de medição de velocidade. Sendo configurada conforme tabela exemplificativa.",
"checks": "Veículo transitando em velocidade inferior à metade da velocidade máxima estabelecida para a via, retardando ou obstruindo o trânsito. 1. Quando as condições de tráfego e meteorológicas não o permitirem transitar na velocidade regulamentada; ou 2. Quando o veículo estiver na faixa da direita. A verificação da velocidade, se dá pelo acompanhamento do examinador ao painel do veículo ou pelo equipamento de medição de velocidade. Sendo configurada conforme tabela exemplificativa.",
"compl": "Tabela exemplificativa:",
"enquad": {
"art": "219",
"ctb": "CTB Art. 219",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 220",
"art": "220",
"grav": "grave",
"pontos": 4,
"nome": "Deixar de reduzir a velocidade do veículo de forma compatível com a segurança do trânsito.",
"desc": "No exame de direção veicular, deixar de reduzir a velocidade do veículo de forma compatível com a segurança do trânsito nas situações descritas abaixo.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Grave: II - nos locais onde o trânsito esteja sendo controlado pelo agente da autoridade de trânsito, mediante sinais sonoros ou gestos; III - ao aproximar-se da guia da calçada (meio-fio) ou acostamento; IV - ao aproximar-se de ou passar por interseção não sinalizada; V - nas vias rurais cuja faixa de domínio não esteja cercada; VI - nos trechos em curva de pequeno raio; VII - ao aproximar-se de locais sinalizados com advertência de obras ou trabalhadores na pista; VIII - sob chuva, neblina, cerração ou ventos fortes; IX - quando houver má visibilidade; X - quando o pavimento se apresentar escorregadio, defeituoso ou avariado; XI - à aproximação de animais na pista; XII - em declive. Gravíssima: I - quando se aproximar de passeatas, aglomerações, cortejos, préstitos e desfiles; XIII - ao ultrapassar ciclista; e XIV - nas proximidades de escolas, hospitais, estações de embarque e desembarque de passageiros ou onde haja intensa movimentação de pedestres. Observar se a conduta não se enquadra na infração prevista no art. 213, que é deixar de parar o veículo quando a marcha for interrompida por agrupamento de pessoas ou de veículos. Caso o candidato não observe a distância de 1,5 m ao ultrapassar um ciclista, se enquadra na infração prevista no art. 201. 1. A fiscalização deste dispositivo dispensa a utilização de medidor de velocidade. 2. Préstito: grupo de pessoas que caminham juntas, com determinada finalidade, tais como cortejo, procissão, entre outros. 3. Velocidade compatível: para fins deste dispositivo, a velocidade compatível com a segurança no trânsito é aquela em que o condutor reduz efetivamente a velocidade do veículo, de forma que fique claro ao agente a redução em relação à velocidade anterior de aproximação, de modo a se evitar o risco de um sinistro de trânsito.",
"checks": "Grave: II - nos locais onde o trânsito esteja sendo controlado pelo agente da autoridade de trânsito, mediante sinais sonoros ou gestos; III - ao aproximar-se da guia da calçada (meio-fio) ou acostamento; IV - ao aproximar-se de ou passar por interseção não sinalizada; V - nas vias rurais cuja faixa de domínio não esteja cercada; VI - nos trechos em curva de pequeno raio; VII - ao aproximar-se de locais sinalizados com advertência de obras ou trabalhadores na pista; VIII - sob chuva, neblina, cerração ou ventos fortes; IX - quando houver má visibilidade; X - quando o pavimento se apresentar escorregadio, defeituoso ou avariado; XI - à aproximação de animais na pista; XII - em declive. Gravíssima: I - quando se aproximar de passeatas, aglomerações, cortejos, préstitos e desfiles; XIII - ao ultrapassar ciclista; e XIV - nas proximidades de escolas, hospitais, estações de embarque e desembarque de passageiros ou onde haja intensa movimentação de pedestres. Observar se a conduta não se enquadra na infração prevista no art. 213, que é deixar de parar o veículo quando a marcha for interrompida por agrupamento de pessoas ou de veículos. Caso o candidato não observe a distância de 1,5 m ao ultrapassar um ciclista, se enquadra na infração prevista no art. 201. 1. A fiscalização deste dispositivo dispensa a utilização de medidor de velocidade. 2. Préstito: grupo de pessoas que caminham juntas, com determinada finalidade, tais como cortejo, procissão, entre outros. 3. Velocidade compatível: para fins deste dispositivo, a velocidade compatível com a segurança no trânsito é aquela em que o condutor reduz efetivamente a velocidade do veículo, de forma que fique claro ao agente a redução em relação à velocidade anterior de aproximação, de modo a se evitar o risco de um sinistro de trânsito.",
"compl": "Não há.",
"enquad": {
"art": "220",
"ctb": "CTB Art. 220",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 224",
"art": "224",
"grav": "leve",
"pontos": 1,
"nome": "Fazer uso do facho de luz alta dos faróis em vias providas de iluminação pública.",
"desc": "Fazer uso do facho de luz alta dos faróis em vias providas de iluminação pública.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Veículo transitando em via provida de iluminação pública com o facho de luz alta dos faróis. 2. Mesmo durante o dia, caso o candidato conduza o veículo em via pública sem observar a luz indicadora de farol alto acesa no painel.",
"naoPontua": "1. Farol de luz baixa: é um farol utilizado para iluminar a via, à frente do veículo, sem causar ofuscamento ou desconforto aos motoristas que se aproximam em sentido contrário e nem a outros usuários da via. 2. Farol de luz baixa principal: é um farol de luz baixa produzido sem a contribuição de emissor infravermelho (IR) e/ou fontes de luz adicionais para iluminação de curvas. 3.",
"definicoes": "Farol de luz alta: é o farol utilizado para iluminar a via a uma longa distância à frente do veículo. O farol de longo alcance, destinado a auxiliar a iluminação à distância à frente do veículo, deve ser considerado, para os fins desta ficha, como farol de luz alta.",
"checks": "1. Veículo transitando em via provida de iluminação pública com o facho de luz alta dos faróis. 2. Mesmo durante o dia, caso o candidato conduza o veículo em via pública sem observar a luz indicadora de farol alto acesa no painel. 1. Farol de luz baixa: é um farol utilizado para iluminar a via, à frente do veículo, sem causar ofuscamento ou desconforto aos motoristas que se aproximam em sentido contrário e nem a outros usuários da via. 2. Farol de luz baixa principal: é um farol de luz baixa produzido sem a contribuição de emissor infravermelho (IR) e/ou fontes de luz adicionais para iluminação de curvas. 3. Farol de luz alta: é o farol utilizado para iluminar a via a uma longa distância à frente do veículo. O farol de longo alcance, destinado a auxiliar a iluminação à distância à frente do veículo, deve ser considerado, para os fins desta ficha, como farol de luz alta.",
"compl": "Não há.",
"enquad": {
"art": "224",
"ctb": "CTB Art. 224",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 227",
"art": "227",
"grav": "leve",
"pontos": 1,
"nome": "Usar buzina: I - em situação que não a de simples toque breve como advertência ao pedestre ou a condutores de outros veículos; II - prolongada e sucessivamente a qualquer pretexto; III - entre as vinte e duas e as seis horas; IV - em locais e horários proibidos pela sinalização; V - em desacordo com os padrões e frequências estabelecidas pelo Contran.",
"desc": "No exame de direção veicular, o candidato usa a buzina nas situações descritas abaixo.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "1. Candidato de veículo que aciona buzina para qualquer finalidade, exceto advertir os usuários das vias a fim de evitar sinistros de trânsito, ou, fora das áreas urbanas, advertir a um candidato que se tem o propósito de ultrapassá-lo; 2. Candidato que acionar a buzina prolongada e sucessivamente a qualquer pretexto; 3. Candidato que aciona a buzina entre as vinte e duas e às seis horas; ou 4. Candidato que aciona a buzina em locais e horários proibidos pela sinalização. Candidato de veículo que usa a buzina, em toque breve, para advertir os demais usuários: a) de uma manobra que será efetuada; b) de um problema na via; c) nas vias rurais, para advertir a um condutor que se tem o propósito de ultrapassá-lo; e d) de qualquer motivo que possa representar risco de ocorrência de sinistro de trânsito. Art. 41. O candidato de veículo só poderá fazer uso de buzina, desde que em toque breve, nas seguintes situações: I - para fazer as advertências necessárias a fim de evitar sinistros; II - fora das áreas urbanas, quando for conveniente advertir a um candidato que se tem o propósito de ultrapassá-lo.",
"checks": "1. Candidato de veículo que aciona buzina para qualquer finalidade, exceto advertir os usuários das vias a fim de evitar sinistros de trânsito, ou, fora das áreas urbanas, advertir a um candidato que se tem o propósito de ultrapassá-lo; 2. Candidato que acionar a buzina prolongada e sucessivamente a qualquer pretexto; 3. Candidato que aciona a buzina entre as vinte e duas e às seis horas; ou 4. Candidato que aciona a buzina em locais e horários proibidos pela sinalização. Candidato de veículo que usa a buzina, em toque breve, para advertir os demais usuários: a) de uma manobra que será efetuada; b) de um problema na via; c) nas vias rurais, para advertir a um condutor que se tem o propósito de ultrapassá-lo; e d) de qualquer motivo que possa representar risco de ocorrência de sinistro de trânsito. Art. 41. O candidato de veículo só poderá fazer uso de buzina, desde que em toque breve, nas seguintes situações: I - para fazer as advertências necessárias a fim de evitar sinistros; II - fora das áreas urbanas, quando for conveniente advertir a um candidato que se tem o propósito de ultrapassá-lo.",
"compl": "Observar a Resolução Contran nº 764, de 2018.",
"enquad": {
"art": "227",
"ctb": "CTB Art. 227",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 230",
"art": "230",
"grav": "grave",
"pontos": 4,
"nome": "Conduzir o veículo: XIX – sem acionar o limpador de para-brisa sob chuva.",
"desc": "No exame de direção veicular, o uso correto do limpador de para-brisa sob chuva é obrigatório, a fim de garantir a visibilidade do percurso. O limpador de para-brisa deve ser utilizado sob chuva, com velocidade condizente com a intensidade da chuva, durante todo o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato não utilizar o limpador de para-brisa ou utilizá- lo incorretamente sob chuva, durante todo o percurso. Quando o percurso não for realizado sob chuva. 1. O examinador deve verificar o uso adequado do limpador de para-brisa antes de iniciar o percurso e durante toda a condução sob chuva. 2. A utilização do limpador é uma exigência legal e fundamental para a segurança no trânsito, pois assegura a visibilidade do percurso. 3. Caso a infração ocorra, ela deve ser registrada imediatamente na ficha de avaliação como média.",
"checks": "Quando o candidato não utilizar o limpador de para-brisa ou utilizá- lo incorretamente sob chuva, durante todo o percurso. Quando o percurso não for realizado sob chuva. 1. O examinador deve verificar o uso adequado do limpador de para-brisa antes de iniciar o percurso e durante toda a condução sob chuva. 2. A utilização do limpador é uma exigência legal e fundamental para a segurança no trânsito, pois assegura a visibilidade do percurso. 3. Caso a infração ocorra, ela deve ser registrada imediatamente na ficha de avaliação como média.",
"compl": "Não há.",
"enquad": {
"art": "230",
"ctb": "CTB Art. 230",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 231",
"art": "231",
"grav": "media",
"pontos": 2,
"nome": "Transitar com o veículo: IX – desligado ou desengrenado, em declive.",
"desc": "No exame de direção veicular, o veículo deve estar ligado e engrenado nos declives, durante todo o percurso.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato desengrenar o veículo nos declives. 1. O examinador deve verificar se o candidato utiliza o uso adequado da especificação do veículo e não desliga ou desengrena o motor nos declives durante o percurso do exame. 2. O veículo deve ser mantido ligado e engrenado nos declives, pois esta é uma exigência legal e fundamental para garantir a eficiência e o controle de velocidade e freios. 3. Caso a infração seja observada, ela deve ser registrada imediatamente na ficha de avaliação como gravíssima.",
"checks": "Quando o candidato desengrenar o veículo nos declives. 1. O examinador deve verificar se o candidato utiliza o uso adequado da especificação do veículo e não desliga ou desengrena o motor nos declives durante o percurso do exame. 2. O veículo deve ser mantido ligado e engrenado nos declives, pois esta é uma exigência legal e fundamental para garantir a eficiência e o controle de velocidade e freios. 3. Caso a infração seja observada, ela deve ser registrada imediatamente na ficha de avaliação como gravíssima.",
"compl": "Não há.",
"enquad": {
"art": "231",
"ctb": "CTB Art. 231",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 244",
"art": "244",
"grav": "gravissima",
"pontos": 6,
"nome": "Conduzir motocicleta, motoneta ou ciclomotor: I – sem usar capacete de segurança ou vestuário de acordo com as normas e as especificações aprovadas pelo Contran.",
"desc": "No exame de direção veicular, o uso do capacete devidamente ajustado à cabeça e vestuário adequado, de acordo com as normas e as especificações aprovadas pelo Contran, são obrigatórios para o candidato.",
"categorias": "ACC e A.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato não ajustar o capacete corretamente à cabeça e não estar com o vestuário adequado durante todo o percurso. 1. O examinador deve verificar o uso do capacete de segurança e do vestuário adequado do candidato antes de iniciar a avaliação, uma vez que são exigências legais e essenciais para a segurança no trânsito. 2. Especificamente, deve-se observar se o capacete está devidamente ajustado à cabeça e permanece corretamente afivelado durante todo o percurso. 3. Caso a infração seja observada, ela deve ser registrada imediatamente na ficha de avaliação como gravíssima.",
"checks": "Quando o candidato não ajustar o capacete corretamente à cabeça e não estar com o vestuário adequado durante todo o percurso. 1. O examinador deve verificar o uso do capacete de segurança e do vestuário adequado do candidato antes de iniciar a avaliação, uma vez que são exigências legais e essenciais para a segurança no trânsito. 2. Especificamente, deve-se observar se o capacete está devidamente ajustado à cabeça e permanece corretamente afivelado durante todo o percurso. 3. Caso a infração seja observada, ela deve ser registrada imediatamente na ficha de avaliação como gravíssima.",
"compl": "Utilizar o capacete com viseira ou óculos protetores é condição para o candidato conduzir o veículo, nos termos do art. 54 do CTB.",
"enquad": {
"art": "244",
"ctb": "CTB Art. 244",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 244 (2)",
"art": "244",
"grav": "gravissima",
"pontos": 6,
"nome": "Conduzir motocicleta, motoneta ou ciclomotor: III – fazendo malabarismo ou equilibrando-se apenas em uma roda.",
"desc": "No exame de direção veicular, a condução do veículo de maneira segura é obrigatória para o candidato durante todo o percurso. O candidato deve fazer o percurso pré-determinado para o exame de maneira segura e equilibrando-se nas duas rodas do veículo.",
"categorias": "ACC e A.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato não conduzir o veículo de maneira segura, realizando manobras perigosas/malabarismo e equilibrar-se no veículo apenas em uma roda (empinar o veículo). 1. O examinador deve verificar se a conduta do candidato gera perigo para si e/ou a terceiros por meio de manobras perigosas ou exibições/malabarismos durante todo o percurso. 2. Se houver risco iminente de sinistro de trânsito decorrente da manobra, o examinador deve intervir imediatamente para garantir a segurança de todos. 3. A infração deve ser registrada imediatamente na ficha de avaliação como gravíssima, com a descrição detalhada da manobra perigosa observada.",
"checks": "Quando o candidato não conduzir o veículo de maneira segura, realizando manobras perigosas/malabarismo e equilibrar-se no veículo apenas em uma roda (empinar o veículo). 1. O examinador deve verificar se a conduta do candidato gera perigo para si e/ou a terceiros por meio de manobras perigosas ou exibições/malabarismos durante todo o percurso. 2. Se houver risco iminente de sinistro de trânsito decorrente da manobra, o examinador deve intervir imediatamente para garantir a segurança de todos. 3. A infração deve ser registrada imediatamente na ficha de avaliação como gravíssima, com a descrição detalhada da manobra perigosa observada.",
"compl": "Não há.",
"enquad": {
"art": "244",
"ctb": "CTB Art. 244",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 244 (3)",
"art": "244",
"grav": "grave",
"pontos": 4,
"nome": "Conduzir motocicleta, motoneta ou ciclomotor: VII – sem segurar o guidom com ambas as mãos.",
"desc": "No exame de direção veicular, a condução do veículo de maneira segura é obrigatória para o candidato durante todo o percurso. O candidato deve conduzir o veículo segurando o guidom com as duas mãos, salvo eventualmente para indicação de manobras.",
"categorias": "ACC e A.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato não segurar o guidom com as duas mãos, salvo para indicar manobras. Se o condutor usar uma das mãos para sinalizar manobras. 1. O examinador deve observar atentamente se o candidato segura o guidom com as duas mãos durante todo o percurso, pois esta é uma exigência legal e essencial para a segurança no trânsito. 2. O uso de apenas uma das mãos é permitido somente quando for necessário sinalizar uma manobra. 3. Caso a infração seja observada, ela deve ser registrada imediatamente na ficha de avaliação como gravíssima.",
"checks": "Quando o candidato não segurar o guidom com as duas mãos, salvo para indicar manobras. Se o condutor usar uma das mãos para sinalizar manobras. 1. O examinador deve observar atentamente se o candidato segura o guidom com as duas mãos durante todo o percurso, pois esta é uma exigência legal e essencial para a segurança no trânsito. 2. O uso de apenas uma das mãos é permitido somente quando for necessário sinalizar uma manobra. 3. Caso a infração seja observada, ela deve ser registrada imediatamente na ficha de avaliação como gravíssima.",
"compl": "Não há.",
"enquad": {
"art": "244",
"ctb": "CTB Art. 244",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 244 (4)",
"art": "244",
"grav": "media",
"pontos": 2,
"nome": "Conduzir motocicleta, motoneta ou ciclomotor: X – com a utilização de capacete de segurança sem viseira ou óculos de proteção ou com viseira ou óculos de proteção em desacordo com a regulamentação do Contran.",
"desc": "No exame de direção veicular, o uso do capacete, devidamente ajustado à cabeça, com a viseira fechada ou óculos de proteção, de acordo com a regulamentação do Contran, é obrigatório para o candidato.",
"categorias": "ACC e A.",
"constatacao": "",
"pontua": "",
"naoPontua": "",
"definicoes": "Quando o candidato não utilizar o capacete de segurança com a viseira fechada ou óculos de proteção. 1. O examinador deve observar atentamente se o candidato utiliza o capacete afivelado e com a viseira fechada ou, na ausência desta, óculos de proteção, durante toda a condução, pois esta é uma exigência legal e essencial para a segurança no trânsito. 2. Se houver risco iminente de sinistro de trânsito decorrente da falta de visibilidade, o examinador deve intervir imediatamente para garantir a segurança de todos. 3. A infração deve ser registrada imediatamente na ficha de avaliação como gravíssima.",
"checks": "Quando o candidato não utilizar o capacete de segurança com a viseira fechada ou óculos de proteção. 1. O examinador deve observar atentamente se o candidato utiliza o capacete afivelado e com a viseira fechada ou, na ausência desta, óculos de proteção, durante toda a condução, pois esta é uma exigência legal e essencial para a segurança no trânsito. 2. Se houver risco iminente de sinistro de trânsito decorrente da falta de visibilidade, o examinador deve intervir imediatamente para garantir a segurança de todos. 3. A infração deve ser registrada imediatamente na ficha de avaliação como gravíssima.",
"compl": "Não há.",
"enquad": {
"art": "244",
"ctb": "CTB Art. 244",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 250",
"art": "250",
"grav": "media",
"pontos": 2,
"nome": "Quando o veículo estiver em movimento: I – Deixar de manter acesa a luz baixa: a) durante a noite; b) de dia, em túneis e sob chuva, neblina ou cerração; d) de dia, no caso de motocicletas, motonetas e ciclomotores; e) de dia, em rodovias de pista simples situadas fora dos perímetros urbanos, no caso de veículos desprovidos de luzes de rodagem diurna.",
"desc": "Durante o exame de direção, o candidato deve demonstrar atenção e responsabilidade no uso do sistema de iluminação do veículo. A luz baixa deve permanecer acesa:  Durante a noite, para garantir visibilidade adequada;  De dia, em túneis, sob chuva, neblina ou cerração;  De dia, em rodovias de pista simples fora dos perímetros urbanos, quando o veículo não possuir luzes de rodagem diurna. O uso correto da iluminação contribui para a segurança ativa e visibilidade mútua entre condutores e pedestres.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato inicia o percurso noturno sem acionar os faróis. 2. Quando o candidato deixa de ligar a luz baixa ao entrar em túnel ou ao conduzir sob chuva, neblina ou cerração. 3. Quando o candidato trafega em rodovia de pista simples, fora de perímetro urbano, sem acender a luz baixa (em veículo sem luzes de rodagem diurna).",
"naoPontua": "1. Quando o candidato aciona corretamente a luz baixa conforme o horário, o tipo de via e as condições de visibilidade. 2. Quando o candidato realiza o percurso noturno com os faróis devidamente acesos e ajustados. 3. Quando o candidato demonstra consciência preventiva ao utilizar a iluminação mesmo antes de condição obrigatória. 1. O examinador deve verificar se o candidato realiza a checagem prévia dos faróis antes do início do exame e se mantém o uso correto da luz baixa durante todo o percurso. 2. Caso o candidato deixe de utilizar as luzes nas condições exigidas (uso incorreto ou ausência), a infração deve ser registrada como média. 3. O registro na ficha de avaliação deve indicar o tipo de situação observada (noite, túnel, chuva, rodovia etc.) e o momento exato em que a infração ocorreu. 4.",
"definicoes": "Persistindo o erro, o examinador deve orientar o",
"checks": "1. Quando o candidato inicia o percurso noturno sem acionar os faróis. 2. Quando o candidato deixa de ligar a luz baixa ao entrar em túnel ou ao conduzir sob chuva, neblina ou cerração. 3. Quando o candidato trafega em rodovia de pista simples, fora de perímetro urbano, sem acender a luz baixa (em veículo sem luzes de rodagem diurna). 1. Quando o candidato aciona corretamente a luz baixa conforme o horário, o tipo de via e as condições de visibilidade. 2. Quando o candidato realiza o percurso noturno com os faróis devidamente acesos e ajustados. 3. Quando o candidato demonstra consciência preventiva ao utilizar a iluminação mesmo antes de condição obrigatória. 1. O examinador deve verificar se o candidato realiza a checagem prévia dos faróis antes do início do exame e se mantém o uso correto da luz baixa durante todo o percurso. 2. Caso o candidato deixe de utilizar as luzes nas condições exigidas (uso incorreto ou ausência), a infração deve ser registrada como média. 3. O registro na ficha de avaliação deve indicar o tipo de situação observada (noite, túnel, chuva, rodovia etc.) e o momento exato em que a infração ocorreu. 4. Persistindo o erro, o examinador deve orientar o",
"compl": "Não há.",
"enquad": {
"art": "250",
"ctb": "CTB Art. 250",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 251-I",
"art": "251-I",
"grav": "media",
"pontos": 2,
"nome": "Utilizar o pisca-alerta, exceto em imobilizações ou situações de emergência.",
"desc": "Durante o exame de direção, o candidato deve utilizar corretamente o sistema de iluminação e sinalização do veículo. O pisca-alerta é destinado exclusivamente a situações de imobilização ou emergência, e seu uso indevido pode confundir outros condutores e comprometer a segurança viária. Acioná-lo em movimento, sem necessidade, é considerado infração e demonstra falta de domínio sobre o uso dos dispositivos do veículo.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato aciona o pisca-alerta sem que o veículo esteja imobilizado. 2. Quando o candidato utiliza o pisca-alerta para sinalizar intenções diversas (como conversão, redução de velocidade ou travessia de cruzamentos). 3. Quando o candidato demonstra desconhecimento da função específica do dispositivo.",
"naoPontua": "1. Quando o candidato utiliza o pisca-alerta corretamente apenas em imobilizações ou situações de emergência. 2. Quando o candidato demonstra domínio sobre o painel e os comandos luminosos do veículo. 3. Quando o candidato não aciona o pisca-alerta indevidamente em nenhum momento do exame. 1. O examinador deve observar atentamente se o candidato utiliza corretamente os dispositivos luminosos, em especial o pisca-alerta. 2. Caso o candidato acione o pisca-alerta de forma indevida durante a condução, a infração deve ser registrada imediatamente como média. 3. O registro na ficha de avaliação deve indicar o momento exato e o motivo do acionamento incorreto. 4.",
"definicoes": "Após o registro e persistindo o erro, o examinador deve orientar o candidato a desabilitar o pisca- alerta para retomar a condução segura e regular do veículo.",
"checks": "1. Quando o candidato aciona o pisca-alerta sem que o veículo esteja imobilizado. 2. Quando o candidato utiliza o pisca-alerta para sinalizar intenções diversas (como conversão, redução de velocidade ou travessia de cruzamentos). 3. Quando o candidato demonstra desconhecimento da função específica do dispositivo. 1. Quando o candidato utiliza o pisca-alerta corretamente apenas em imobilizações ou situações de emergência. 2. Quando o candidato demonstra domínio sobre o painel e os comandos luminosos do veículo. 3. Quando o candidato não aciona o pisca-alerta indevidamente em nenhum momento do exame. 1. O examinador deve observar atentamente se o candidato utiliza corretamente os dispositivos luminosos, em especial o pisca-alerta. 2. Caso o candidato acione o pisca-alerta de forma indevida durante a condução, a infração deve ser registrada imediatamente como média. 3. O registro na ficha de avaliação deve indicar o momento exato e o motivo do acionamento incorreto. 4. Após o registro e persistindo o erro, o examinador deve orientar o candidato a desabilitar o pisca- alerta para retomar a condução segura e regular do veículo.",
"compl": "Não há.",
"enquad": {
"art": "251-I",
"ctb": "CTB Art. 251, I",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 251-II",
"art": "251-II",
"grav": "media",
"pontos": 2,
"nome": "Utilizar as luzes baixa e alta de forma intermitente, exceto nas seguintes situações: a) a curtos intervalos, quando for conveniente advertir a outro condutor que se tem o propósito de ultrapassá-lo; b) em imobilizações ou situação de emergência, como advertência, utilizando pisca-alerta; c) quando a sinalização de regulamentação da via determinar o uso do pisca- alerta.",
"desc": "Durante o exame de direção, o candidato deve utilizar corretamente o sistema de iluminação do veículo, evitando o acionamento intermitente das luzes alta e baixa sem necessidade. O uso incorreto dessas luzes pode causar ofuscamento, confusão e risco de sinistros, principalmente à noite ou em vias de mão dupla. As luzes intermitentes devem ser utilizadas somente em situações específicas de advertência ou segurança, conforme previsto no CTB.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato pisca repetidamente as luzes alta e baixa para fins de comunicação não prevista (como “abrir caminho” ou “apressar” outro condutor). 2. Quando o candidato utiliza as luzes intermitentes sem necessidade ou em locais inadequados, como cruzamentos, vias de mão dupla ou tráfego intenso. 3. Quando o candidato demonstra desconhecimento sobre as situações corretas de uso das luzes.",
"naoPontua": "1. Quando o candidato utiliza as luzes intermitentes de forma correta, apenas para advertir outro condutor em situação de risco ou ultrapassagem segura. 2. Quando o candidato mantém o farol baixo acionado conforme as condições de luminosidade e via. 3. Quando o candidato demonstra domínio e bom senso na utilização dos dispositivos de iluminação. 1. O examinador deve observar atentamente se o candidato utiliza os faróis com moderação e somente nas situações exigidas (uso correto do facho de luz). 2. Caso o uso das luzes intermitentes (pisca-pisca ou pisca- alerta) ocorra de forma indevida durante a condução, a infração deve ser registrada imediatamente como média. 3.",
"definicoes": "O registro na ficha de avaliação deve descrever o momento e o contexto exato em que a conduta incorreta foi observada.",
"checks": "1. Quando o candidato pisca repetidamente as luzes alta e baixa para fins de comunicação não prevista (como “abrir caminho” ou “apressar” outro condutor). 2. Quando o candidato utiliza as luzes intermitentes sem necessidade ou em locais inadequados, como cruzamentos, vias de mão dupla ou tráfego intenso. 3. Quando o candidato demonstra desconhecimento sobre as situações corretas de uso das luzes. 1. Quando o candidato utiliza as luzes intermitentes de forma correta, apenas para advertir outro condutor em situação de risco ou ultrapassagem segura. 2. Quando o candidato mantém o farol baixo acionado conforme as condições de luminosidade e via. 3. Quando o candidato demonstra domínio e bom senso na utilização dos dispositivos de iluminação. 1. O examinador deve observar atentamente se o candidato utiliza os faróis com moderação e somente nas situações exigidas (uso correto do facho de luz). 2. Caso o uso das luzes intermitentes (pisca-pisca ou pisca- alerta) ocorra de forma indevida durante a condução, a infração deve ser registrada imediatamente como média. 3. O registro na ficha de avaliação deve descrever o momento e o contexto exato em que a conduta incorreta foi observada.",
"compl": "Não há.",
"enquad": {
"art": "251-II",
"ctb": "CTB Art. 251, II",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 252-I",
"art": "252-I",
"grav": "media",
"pontos": 2,
"nome": "Dirigir o veículo com o braço do lado de fora.",
"desc": "Durante o exame de direção, o candidato deve manter ambos os braços dentro do veículo e posicionados corretamente para o controle da direção. Conduzir com o braço para fora da janela compromete a segurança, reduz a capacidade de reação em situações de risco e fere o princípio da direção defensiva. Além disso, essa atitude demonstra postura inadequada e falta de domínio sobre o veículo durante a condução.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato mantém o braço do lado de fora da janela enquanto dirige. 2. Quando o candidato realiza parte do percurso com o cotovelo apoiado na borda da porta ou na janela aberta. 3. Quando o candidato demonstra postura relaxada ou displicente, com o braço parcialmente projetado para fora do veículo.",
"naoPontua": "1. Quando o candidato mantém ambos os braços dentro do veículo, com as mãos corretamente posicionadas no volante (geralmente entre 9h e 3h). 2. Quando o candidato ajusta brevemente o vidro ou retrovisor, retornando de imediato à posição adequada. 3. Quando o candidato demonstra controle e postura correta durante todo o exame. 1. O examinador deve observar atentamente a postura do candidato desde o início até o término do exame. 2. Caso o candidato dirija com o braço para o lado de fora do veículo, a infração deve ser registrada imediatamente como média. 3.",
"definicoes": "O registro na ficha de avaliação deve conter a descrição do momento e do contexto da observação, com evidência direta e inequívoca da conduta.",
"checks": "1. Quando o candidato mantém o braço do lado de fora da janela enquanto dirige. 2. Quando o candidato realiza parte do percurso com o cotovelo apoiado na borda da porta ou na janela aberta. 3. Quando o candidato demonstra postura relaxada ou displicente, com o braço parcialmente projetado para fora do veículo. 1. Quando o candidato mantém ambos os braços dentro do veículo, com as mãos corretamente posicionadas no volante (geralmente entre 9h e 3h). 2. Quando o candidato ajusta brevemente o vidro ou retrovisor, retornando de imediato à posição adequada. 3. Quando o candidato demonstra controle e postura correta durante todo o exame. 1. O examinador deve observar atentamente a postura do candidato desde o início até o término do exame. 2. Caso o candidato dirija com o braço para o lado de fora do veículo, a infração deve ser registrada imediatamente como média. 3. O registro na ficha de avaliação deve conter a descrição do momento e do contexto da observação, com evidência direta e inequívoca da conduta.",
"compl": "Não há.",
"enquad": {
"art": "252-I",
"ctb": "CTB Art. 252, I",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 252-II",
"art": "252-II",
"grav": "media",
"pontos": 2,
"nome": "Dirigir o veículo transportando pessoas, animais ou volume à sua esquerda ou entre os braços e pernas.",
"desc": "Durante o exame de direção, o candidato deve manter o posicionamento correto das mãos e braços no volante e o interior do veículo livre de objetos, pessoas ou animais que possam interferir na condução. Transportar pessoas, animais ou volumes à esquerda ou entre os braços e pernas compromete o controle do veículo e a segurança da direção, configurando prática inadequada e infração média.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato dirige com objetos (como bolsas, mochilas, papéis ou volumes) apoiados entre as pernas ou sobre os braços. 2. Quando o candidato permite que passageiro, criança ou animal ocupe o espaço ao seu lado esquerdo ou entre os braços e o volante. 3. Quando o candidato demonstra falta de controle sobre o veículo devido à restrição de movimentos provocada por tais objetos.",
"naoPontua": "1. Quando o candidato mantém o interior do veículo organizado e livre de interferências que prejudiquem os comandos. 2. Quando o candidato utiliza corretamente o espaço de condução, garantindo ampla movimentação dos braços e pernas. 3. Quando o candidato demonstra postura segura e atenção total à direção. 1. O examinador deve observar atentamente o interior do veículo no início e durante o percurso, garantindo que o espaço do condutor esteja livre de volumes, animais ou pessoas em posição indevida. 2. Caso o candidato dirija com restrição de movimentos em função dessas interferências, a infração deve ser registrada imediatamente como média. 3.",
"definicoes": "O registro na ficha de avaliação deve indicar o tipo de interferência observada (objeto, pessoa ou animal) e o seu impacto direto na segurança e na condução do veículo.",
"checks": "1. Quando o candidato dirige com objetos (como bolsas, mochilas, papéis ou volumes) apoiados entre as pernas ou sobre os braços. 2. Quando o candidato permite que passageiro, criança ou animal ocupe o espaço ao seu lado esquerdo ou entre os braços e o volante. 3. Quando o candidato demonstra falta de controle sobre o veículo devido à restrição de movimentos provocada por tais objetos. 1. Quando o candidato mantém o interior do veículo organizado e livre de interferências que prejudiquem os comandos. 2. Quando o candidato utiliza corretamente o espaço de condução, garantindo ampla movimentação dos braços e pernas. 3. Quando o candidato demonstra postura segura e atenção total à direção. 1. O examinador deve observar atentamente o interior do veículo no início e durante o percurso, garantindo que o espaço do condutor esteja livre de volumes, animais ou pessoas em posição indevida. 2. Caso o candidato dirija com restrição de movimentos em função dessas interferências, a infração deve ser registrada imediatamente como média. 3. O registro na ficha de avaliação deve indicar o tipo de interferência observada (objeto, pessoa ou animal) e o seu impacto direto na segurança e na condução do veículo.",
"compl": "Não há.",
"enquad": {
"art": "252-II",
"ctb": "CTB Art. 252, II",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 252-IV",
"art": "252-IV",
"grav": "media",
"pontos": 2,
"nome": "Dirigir o veículo usando calçado que não se firme nos pés ou que comprometa a utilização dos pedais.",
"desc": "Durante o exame de direção, o candidato deve utilizar calçado adequado, que se firme aos pés e permita total controle dos pedais (embreagem, freio e acelerador). O uso de chinelos, sandálias frouxas, sapatos de salto alto ou calçados que se desprendam com facilidade põe em risco o controle do veículo e caracteriza infração média. Essa conduta demonstra falta de atenção à segurança e à preparação para condução veicular.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato realiza o exame com chinelos, sandálias sem tiras traseiras, tamancos, sapatos de salto alto ou qualquer calçado que se desprenda com facilidade. 2. Quando o calçado impede o acionamento rápido e preciso dos pedais. 3. Quando o candidato demonstra insegurança ou perda de tempo de resposta ao utilizar calçado inadequado.",
"naoPontua": "1. Quando o candidato utiliza calçado firme e fechado, que se ajusta bem aos pés e permite movimentação segura. 2. Quando o candidato demonstra controle total dos pedais, mesmo em manobras de precisão. 3. Quando o calçado é compatível com o uso veicular e não compromete a segurança. 1. O examinador deve verificar o calçado do candidato antes do início do exame de direção. 2. Se for identificado calçado inadequado (conforme a legislação vigente), o examinador deve orientar o candidato a substituí-lo antes do início da avaliação. 3. Caso o candidato inicie ou prossiga com a avaliação e o calçado venha a comprometer o controle do veículo durante o percurso, a infração deve ser registrada imediatamente como média. 4.",
"definicoes": "O registro na ficha de avaliação deve indicar o tipo de calçado e a interferência exata observada na utilização dos pedais.",
"checks": "1. Quando o candidato realiza o exame com chinelos, sandálias sem tiras traseiras, tamancos, sapatos de salto alto ou qualquer calçado que se desprenda com facilidade. 2. Quando o calçado impede o acionamento rápido e preciso dos pedais. 3. Quando o candidato demonstra insegurança ou perda de tempo de resposta ao utilizar calçado inadequado. 1. Quando o candidato utiliza calçado firme e fechado, que se ajusta bem aos pés e permite movimentação segura. 2. Quando o candidato demonstra controle total dos pedais, mesmo em manobras de precisão. 3. Quando o calçado é compatível com o uso veicular e não compromete a segurança. 1. O examinador deve verificar o calçado do candidato antes do início do exame de direção. 2. Se for identificado calçado inadequado (conforme a legislação vigente), o examinador deve orientar o candidato a substituí-lo antes do início da avaliação. 3. Caso o candidato inicie ou prossiga com a avaliação e o calçado venha a comprometer o controle do veículo durante o percurso, a infração deve ser registrada imediatamente como média. 4. O registro na ficha de avaliação deve indicar o tipo de calçado e a interferência exata observada na utilização dos pedais.",
"compl": "Não há.",
"enquad": {
"art": "252-IV",
"ctb": "CTB Art. 252, IV",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 252-V",
"art": "252-V",
"grav": "media",
"pontos": 2,
"nome": "Dirigir o veículo com apenas uma das mãos, exceto quando deva fazer sinais regulamentares de braço, mudar a marcha do veículo ou acionar equipamentos e acessórios do veículo.",
"desc": "Durante o exame de direção, o candidato deve manter ambas as mãos no volante, garantindo controle, estabilidade e segurança na condução. Dirigir com apenas uma das mãos, fora das exceções previstas (mudança de marcha, acionamento de equipamentos ou sinalização regulamentar), reduz a precisão e o tempo de resposta em situações de risco. Essa conduta demonstra postura inadequada e falta de atenção aos princípios de direção defensiva.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato dirige longos trechos com uma das mãos fora do volante. 2. Quando o candidato utiliza uma mão para apoiar o corpo ou gesticular, mantendo a outra no volante.",
"naoPontua": "1. Quando o candidato retira brevemente uma das mãos do volante para mudar a marcha, acionar equipamentos ou fazer sinal regulamentar. 2. Quando o candidato mantém as duas mãos firmes no volante durante a condução normal. 3. Quando o candidato demonstra controle, postura e atenção constante à via. 1. O examinador deve observar atentamente a posição das mãos do candidato desde o início do exame até o final do percurso. 2. Caso o candidato mantenha uma das mãos fora do volante sem necessidade, a infração deve ser registrada imediatamente como média. 3.",
"definicoes": "O registro na ficha de avaliação deve indicar a circunstância e o tempo aproximado em que a conduta incorreta foi observada.",
"checks": "1. Quando o candidato dirige longos trechos com uma das mãos fora do volante. 2. Quando o candidato utiliza uma mão para apoiar o corpo ou gesticular, mantendo a outra no volante. 1. Quando o candidato retira brevemente uma das mãos do volante para mudar a marcha, acionar equipamentos ou fazer sinal regulamentar. 2. Quando o candidato mantém as duas mãos firmes no volante durante a condução normal. 3. Quando o candidato demonstra controle, postura e atenção constante à via. 1. O examinador deve observar atentamente a posição das mãos do candidato desde o início do exame até o final do percurso. 2. Caso o candidato mantenha uma das mãos fora do volante sem necessidade, a infração deve ser registrada imediatamente como média. 3. O registro na ficha de avaliação deve indicar a circunstância e o tempo aproximado em que a conduta incorreta foi observada.",
"compl": "Não há.",
"enquad": {
"art": "252-V",
"ctb": "CTB Art. 252, V",
"mbedv": "MBEDV"
}
},
{
"code": "Art. 252-VI",
"art": "252-VI",
"grav": "media",
"pontos": 2,
"nome": "Dirigir o veículo utilizando-se de fones nos ouvidos conectados a aparelhagem sonora ou de telefone celular.",
"desc": "Durante o exame de direção, o candidato não deve utilizar fones de ouvido, fones bluetooth ou aparelhos de telefonia celular enquanto conduz o veículo. Essa conduta reduz a percepção auditiva e a atenção ao ambiente, comprometendo a segurança do condutor e dos demais usuários da via. O uso de fones ou celulares durante a condução demonstra distração e desrespeito às normas de segurança, contrariando os princípios de direção defensiva.",
"categorias": "ACC, A, B, C, D e E.",
"constatacao": "",
"pontua": "1. Quando o candidato realiza o exame com fones conectados a aparelho sonoro ou telefone celular. 2. Quando o candidato utiliza fones ou fala ao celular (mesmo em viva-voz) durante a condução. 3. Quando o candidato demonstra distração ou desatenção devido ao uso de equipamento eletrônico.",
"naoPontua": "1. Quando o candidato realiza o exame sem utilizar fones, mantendo total atenção à via e aos comandos do veículo. 2. Quando o candidato aguarda o término do exame para manusear aparelhos eletrônicos. 3. Quando o candidato demonstra comportamento atento, comunicando-se apenas com o examinador quando necessário. 1. O examinador deve observar o candidato antes da partida e durante todo o percurso, garantindo que nenhum fone de ouvido ou aparelho celular esteja sendo utilizado. 2. Caso o candidato seja flagrado utilizando fones de ouvido ou aparelho celular durante a condução, a infração deve ser registrada imediatamente como média. 3.",
"definicoes": "O registro na ficha de avaliação deve indicar o tipo de aparelho utilizado e o momento exato da constatação da infração.",
"checks": "1. Quando o candidato realiza o exame com fones conectados a aparelho sonoro ou telefone celular. 2. Quando o candidato utiliza fones ou fala ao celular (mesmo em viva-voz) durante a condução. 3. Quando o candidato demonstra distração ou desatenção devido ao uso de equipamento eletrônico. 1. Quando o candidato realiza o exame sem utilizar fones, mantendo total atenção à via e aos comandos do veículo. 2. Quando o candidato aguarda o término do exame para manusear aparelhos eletrônicos. 3. Quando o candidato demonstra comportamento atento, comunicando-se apenas com o examinador quando necessário. 1. O examinador deve observar o candidato antes da partida e durante todo o percurso, garantindo que nenhum fone de ouvido ou aparelho celular esteja sendo utilizado. 2. Caso o candidato seja flagrado utilizando fones de ouvido ou aparelho celular durante a condução, a infração deve ser registrada imediatamente como média. 3. O registro na ficha de avaliação deve indicar o tipo de aparelho utilizado e o momento exato da constatação da infração.",
"compl": "Não há.",
"enquad": {
"art": "252-VI",
"ctb": "CTB Art. 252, VI",
"mbedv": "MBEDV"
}
}
];

export default MBEDV_RULES;
