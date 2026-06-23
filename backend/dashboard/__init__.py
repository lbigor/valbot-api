"""Dashboard Regulatório — camada de agregação de métricas (spec §15).

Reúne, sobre uma janela de N dias, os indicadores operacionais (volume,
erros, custo, tempo) e regulatórios (concordância, divergências, infrações)
a partir das tabelas/views do Postgres. Só leitura/agregação — sem UI.
"""
