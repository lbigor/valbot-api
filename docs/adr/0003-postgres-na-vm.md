# ADR 0003 — Postgres no container da VM ao invés de Cloud SQL managed

- **Status:** aceito
- **Data:** 2026-05-05
- **Decisores:** Igor Lima

## Contexto

O valbot precisa persistir metadados de exames (candidato, status do pipeline, links pro GCS, layout detectado, pontuação). Volume previsto pra MVP: < 10.000 registros, < 100 inserts/dia. Duas opções:

### A. Postgres dentro do `docker-compose` da VM
- Imagem `postgres:16-alpine`, dados em volume Docker.
- Backup manual (ou cron de `pg_dump` para GCS).
- Escala vertical limitada à VM (e2-standard-2 = 8 GB RAM compartilhados com api + cloudflared + code-server).

### B. Cloud SQL Postgres managed
- Instance `db-f1-micro` (~$10/mês) ou `db-custom-1-3840` (~$15/mês).
- Backup automático, point-in-time recovery, alta disponibilidade opcional.
- Conexão via Unix socket no GCP ou IP privado.

## Decisão

Usar **Postgres no container da VM** (caminho A) para o MVP.

## Consequências

### Positivas
- Zero custo recorrente adicional ao MVP.
- Postgres na mesma rede Docker que a API — latência ~0.5ms.
- Setup local idêntico ao prod (mesmo `docker-compose`).
- Migrations em `migrations/*.sql` aplicam automaticamente via `docker-entrypoint-initdb.d`.

### Negativas
- Sem alta disponibilidade — se a VM cair, o banco cai junto.
- Backup é responsabilidade do dev (não automático).
- Escala vertical limitada à RAM da VM.
- Volume Docker pode crescer e ocupar disco da VM.

### Mitigações
- Implementar `cron` na VM rodando `pg_dump` diário para `gs://valbot-prod/backups/postgres-YYYYMMDD.sql.gz` — coberto pelo Service Account `valbot-vm` com role `storage.objectAdmin`.
- Monitorar tamanho do volume `postgres-data` via `df -h`.
- Migrar pra Cloud SQL quando: > 10.000 inserts/dia, ou requisito de uptime > 99.5%, ou time > 1 dev.

### Custo evitado durante o MVP
- Cloud SQL `db-f1-micro` × 12 meses ≈ **$120/ano**.
- Setup adicional de VPC/Private Service Connect.
