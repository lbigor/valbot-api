# Changelog do Prompt — Diretrizes de Avaliação Val

Versionamento semântico ([SemVer](https://semver.org)) das `_DIRETRIZES_VAL` —
a camada de **interpretação Val** sobre a Matriz MBEDV, em
`backend/matriz/prompt_builder.py`. Essas diretrizes entram no prompt do motor
(detecção v26 e fallback v25) e do Comitê via `construir_bloco`.

A versão reportada e gravada por análise é **composta**:
`<matriz_versao>+diretrizes-v<X.Y.Z>` (ex.: `matriz-nacional-v1.0+diretrizes-v1.1.0`),
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
