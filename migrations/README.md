# Migrations

SQL versionado do schema do Valbot. Numeração sequencial `NNN_descricao.sql`.

## Como são aplicadas

- **1º boot do Postgres** (banco vazio): o `docker-entrypoint-initdb.d` roda todos
  os `.sql` em ordem automaticamente.
- **Deploys seguintes** (banco já existente): o runner `deploy/scripts/migrate.sh`
  aplica, em ordem e uma única vez, as migrations ainda não registradas na tabela
  de controle `schema_migrations`. É disparado pelo CI antes de subir a API
  (`docker compose run --rm migrate`) e é seguro rodar a cada deploy (no-op quando
  não há pendência).

Na **primeira** execução do runner sobre um banco já provisionado, ele faz
*auto-baseline*: registra como já-aplicada toda migration cujo objeto (tabela
criada / coluna adicionada) já existe, **sem reexecutá-la** — porque migrations
antigas não são necessariamente idempotentes.

## Escrevendo uma migration nova

1. Crie `migrations/NNN_descricao.sql` com o próximo número.
2. **Escreva idempotente**: `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`,
   `INSERT ... ON CONFLICT DO NOTHING`. Assim ela é segura mesmo se reexecutada.
3. Abra PR. Ao mergear na `main`, o deploy aplica a migration automaticamente.

Não edite migrations já aplicadas — crie uma nova que ajuste o schema.
