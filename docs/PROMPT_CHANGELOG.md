# Changelog do Prompt — Diretrizes de Avaliação Val

Versionamento semântico ([SemVer](https://semver.org)) das `_DIRETRIZES_VAL` —
a camada de **interpretação Val** sobre a Matriz MBEDV, em
`backend/matriz/prompt_builder.py` — e dos **fragments de câmera** do preset v26
(`tooling/bench_demo/presets/v26/cat_B/*.md`), que compõem o system prompt do
motor de detecção. Ambos entram no prompt do motor (detecção v26 e fallback v25)
e do Comitê.

A versão reportada e gravada por análise é **composta**:
`<matriz_versao>+diretrizes-v<X.Y.Z>` (ex.: `matriz-nacional-v1.0+diretrizes-v1.4.0`),
separando a evolução da Matriz oficial (DB) da camada de interpretação Val (código).
A versão das diretrizes vive em `prompt_builder.DIRETRIZES_VAL_VERSAO`.

Regras: **MINOR** = nova diretriz ou mudança de comportamento de julgamento;
**PATCH** = ajuste de redação sem mudar a regra; **MAJOR** = remoção/inversão de
diretriz vigente. Bumpar a constante e adicionar a entrada AQUI no mesmo PR.

> **Campanha de correção de falsos positivos (25/06/2026).** A análise do dia
> 25/06 (cat B) achou 21,2% de divergência IA×examinador, concentrada em 4
> artigos. A correção foi quebrada em um PR por artigo, cada um com sua MINOR:
> **1.1.0** Art. 208 · **1.2.0** Art. 169 · **1.3.0** Art. 196 · **1.4.0** Art. 193.
> Como os PRs são independentes a partir de `main`, o CHANGELOG é aditivo e a
> ordem de merge reconcilia as entradas.

## [1.4.0] — 2026-06-29 — Art. 193: meio-fio/guia ≠ calçada/passeio
### Corrigido
- **Art. 193 (transitar sobre calçada, gravíssima)** — 8 falsos positivos no
  25/06 (examinador aprovou, IA INAPTO). A IA confundia **tocar/subir
  momentaneamente o meio-fio/guia** em manobra com **transitar sobre
  calçada/passeio** (6 pts), disparando inclusive por inferência fraca
  (solavanco, oscilação do horizonte, áudio "subiu na guia").
- **Fragments v26** (load-bearing — caminho de detecção de prod):
  `cam_lateral_direita.md` e `cam_frontal.md` reescritos para exigir roda
  apoiada e rodando sobre a superfície do passeio, excluir toque momentâneo da
  guia (→ Art. 181/192) e proibir disparo por sinal indireto isolado.
- **Defesa em profundidade:** `_DIRETRIZES_VAL["193"]` com a mesma distinção
  (alcança o Comitê e o caminho legado).
### Gate
- Reprocessar os 8 FPs do 25/06 + amostra de verdadeiros positivos de trânsito
  real sobre calçada antes de promover.

## [1.3.0] — 2026-06-29 — Art. 196: guard de áudio prevalece (anti-contradição)
### Corrigido
- **Art. 196 (não sinalizou seta, grave)** — 19 falsos positivos no 25/06, o
  campeão (examinador aprovou, IA INAPTO, confiança ~0,97). A IA marcava falta de
  seta pela **ausência do "tic-tac" do relé** — ausência sonora ≠ falta de
  sinalização (áudio baixo/ruído do motor).
- Causa-raiz (validada adversarialmente, veredito *refutado* da tese inicial): o
  guard "seta só se valida por áudio" **já existe** nos fragments de câmera, mas o
  bloco da Matriz é anexado por último, autoritativo, **sem repetir o guard** —
  contradição por recência. `_DIRETRIZES_VAL["196"]` reinsere o guard no bloco
  autoritativo, declarando que ele **PREVALECE** sobre a lista "Condutas que
  pontuam", e reafirma as exceções de via da ficha.
### Gate
- Reprocessar os 19 FPs do 25/06 + amostra de verdadeiros positivos (em especial
  os por verbalização do examinador "esqueceu a seta") antes de promover.

## [1.2.0] — 2026-06-29 — Art. 169: caráter residual, sem guarda-chuva
### Corrigido
- **Art. 169 (dirigir sem atenção, leve)** — 10 falsos positivos no 25/06
  (examinador aprovou, IA INAPTO, confiança ~0,93). A IA usava o 169 como
  guarda-chuva para erro de marcha/embreagem isolado, dificuldade pontual em
  aclive e ações executadas sob instrução verbal do examinador.
- Adicionada `_DIRETRIZES_VAL["169"]`: reforça o caráter **residual** (só pontua
  desatenção genuína, sem enquadramento específico) e exclui explicitamente erro
  mecânico isolado e conduta conduzida pelo examinador.
### Gate
- Reprocessar os 10 FPs do 25/06 + amostra de verdadeiros positivos de desatenção
  real antes de promover (efeito do prompt é probabilístico).

## [1.1.0] — 2026-06-29 — Art. 208: áudio do motor não prova falta de parada
### Corrigido
- **Art. 208 (parada obrigatória, gravíssima)** — 17 falsos positivos no 25/06
  (examinador aprovou, IA INAPTO, confiança ~0,96). A IA inferia "parada
  rolante" pelo **áudio do motor** ("som contínuo", "sem a pausa característica
  de uma parada") — premissa falsa (motor fica em marcha lenta numa parada de
  1–2 s).
- `_DIRETRIZES_VAL["208"]` passa a declarar o **áudio do motor IRRELEVANTE** e a
  exigir prova **VISUAL** (câmera frontal); descarta 208 cujo único suporte seja
  sonoro.
### Gate
- Reprocessar os 17 FPs do 25/06 + amostra de verdadeiros positivos de 208 antes
  de promover (efeito do prompt é probabilístico).

## [1.0.0] — base (origin/main)
- Estado inicial das Diretrizes Val: apenas `_DIRETRIZES_VAL["208"]` (benefício
  da dúvida na parada obrigatória + estratégia do frame congelado), sem
  versionamento explícito.
