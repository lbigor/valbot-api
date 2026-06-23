"""Matriz Nacional de Regras (spec §4) — fonte canônica do MBEDV.

A Matriz é o ativo central do produto: vincula cada conduta a artigo CTB +
ficha MBEDV + natureza + peso + exceções, versionada. O conteúdo vem das 84
fichas reais do MBEDV (``configs/references/mbedv_fichas.json``, extraídas do
PDF oficial), não de catálogos derivados.

Submódulos:
    seed_mbedv      — carrega as fichas e popula ``exam_rules`` + ``matriz_versoes``
    correspondencia — ponte IDs de detecção (R1020-*) → código canônico (Art. CTB)
    prompt_builder  — gera o bloco de regras do prompt a partir da Matriz vigente
"""
