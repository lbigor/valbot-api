#!/bin/sh
# =============================================================================
# Runner de migrations do Valbot — aplica migrations/*.sql pendentes no deploy.
#
# Problema que resolve: as migrations só rodavam no 1º boot do Postgres
# (docker-entrypoint-initdb.d). Banco já existente nunca recebia migration nova.
# Este runner roda a CADA deploy e aplica, em ordem e uma única vez, o que ainda
# não foi aplicado — controlado pela tabela `schema_migrations`.
#
# 1ª execução sobre banco já provisionado (auto-baseline): várias migrations
# legadas NÃO são idempotentes (004 faz INSERT sem ON CONFLICT; 007 faz
# RENAME/DROP). Reexecutá-las quebraria/duplicaria dados. Então, na adoção, o
# runner registra como já-aplicada toda migration cujo objeto-sentinela (a
# tabela que ela cria ou a coluna que adiciona) JÁ existe no banco — sem
# reexecutar. As demais são aplicadas normalmente.
#
# Idempotente e seguro rodar repetidamente. Fail-fast: para no 1º erro com
# código ≠0, abortando o deploy antes de subir a API nova.
#
# Conexão: PGHOST/PGUSER/PGDATABASE/PGPASSWORD via ambiente (compose injeta).
# =============================================================================
set -eu

export PGHOST="${PGHOST:-postgres}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-valbot}"
export PGDATABASE="${PGDATABASE:-valbot}"
# PGPASSWORD vem do ambiente (compose passa ${POSTGRES_PASSWORD}).

MIG_DIR="${MIG_DIR:-/migrations}"

# Query escalar: -X (sem .psqlrc), -A -t (unaligned, tuples-only), ON_ERROR_STOP.
q() { psql -X -A -t -v ON_ERROR_STOP=1 -c "$1"; }

echo "[migrate] garantindo tabela de controle schema_migrations…"
q "CREATE TABLE IF NOT EXISTS schema_migrations (
     version    TEXT PRIMARY KEY,
     applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
   );" >/dev/null

# Adoção = tabela de controle vazia E banco já tem dados (tabela exams existe,
# sinal de que o initdb rodou as migrations legadas no 1º boot).
control_count=$(q "SELECT count(*) FROM schema_migrations;" | tr -d '[:space:]')
legacy=$(q "SELECT (to_regclass('public.exams') IS NOT NULL);" | tr -d '[:space:]')
adopt=0
if [ "$control_count" = "0" ] && [ "$legacy" = "t" ]; then
  adopt=1
  echo "[migrate] adoção: banco legado detectado — auto-baseline ativo"
fi

applied=0; baselined=0; already=0

for f in $(ls "$MIG_DIR"/[0-9]*.sql 2>/dev/null | sort); do
  ver=$(basename "$f" .sql)

  reg=$(q "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE version='$ver');" | tr -d '[:space:]')
  if [ "$reg" = "t" ]; then
    already=$((already + 1))
    continue
  fi

  if [ "$adopt" = "1" ]; then
    # Normaliza o SQL antes de extrair o sentinela: remove comentários de linha
    # (-- …, que podem citar "CREATE TABLE" em prosa) e colapsa quebras de linha,
    # para o nome do objeto ficar contíguo ao CREATE/ALTER mesmo se quebrado.
    norm=$(sed -e 's/--.*$//' "$f" | tr '\n' ' ' | tr -s '[:space:]' ' ')
    # Sentinela: tabela criada OU primeira coluna adicionada por esta migration.
    tbl=$(printf '%s' "$norm" | grep -ioE "create table (if not exists )?[a-z0-9_]+" \
            | head -1 | grep -ioE "[a-z0-9_]+$" || true)
    sentinel=""
    if [ -n "$tbl" ]; then
      sentinel=$(q "SELECT (to_regclass('public.$tbl') IS NOT NULL);" | tr -d '[:space:]')
    else
      atbl=$(printf '%s' "$norm" | grep -ioE "alter table [a-z0-9_]+" | head -1 \
               | grep -ioE "[a-z0-9_]+$" || true)
      acol=$(printf '%s' "$norm" | grep -ioE "add column (if not exists )?[a-z0-9_]+" \
               | head -1 | grep -ioE "[a-z0-9_]+$" || true)
      if [ -n "$atbl" ] && [ -n "$acol" ]; then
        sentinel=$(q "SELECT EXISTS(SELECT 1 FROM information_schema.columns
                       WHERE table_name='$atbl' AND column_name='$acol');" | tr -d '[:space:]')
      fi
    fi
    if [ "$sentinel" = "t" ]; then
      # Objeto já existe → migration já aplicada no 1º boot. Registra sem rodar.
      q "INSERT INTO schema_migrations(version) VALUES('$ver') ON CONFLICT DO NOTHING;" >/dev/null
      echo "[migrate]   baseline (já aplicada): $ver"
      baselined=$((baselined + 1))
      continue
    fi
    # sentinel vazio (ex.: 006, só troca CHECK constraint — idempotente) ou "f"
    # (objeto ausente) → segue para aplicar de fato abaixo.
  fi

  echo "[migrate]   aplicando: $ver"
  psql -X -v ON_ERROR_STOP=1 --single-transaction -f "$f"
  q "INSERT INTO schema_migrations(version) VALUES('$ver') ON CONFLICT DO NOTHING;" >/dev/null
  applied=$((applied + 1))
done

echo "[migrate] concluído — aplicadas=$applied baseline=$baselined já-registradas=$already"
