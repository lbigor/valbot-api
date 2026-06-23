"""Fluxo humano de 4 níveis + Ordens de Serviço (spec §11-§12).

Toda divergência detectada pelo Motor de Comparação vira uma Ordem de Serviço
que percorre, sem atalhos, os níveis Auditor (3) → Supervisor (4). O módulo
``ordens`` concentra o ciclo de vida da OS e a trilha de auditoria append-only.
"""
