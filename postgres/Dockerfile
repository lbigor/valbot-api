# Postgres 16 + pg_cron extension.
#
# pg_cron exige `shared_preload_libraries='pg_cron'` no postgresql.conf
# ANTES do boot. Se setar via SQL após start, NÃO funciona (a extensão
# não engata).
#
# Build:
#   docker build -t valbot-postgres:16-cron postgres/
# Usage:
#   image: valbot-postgres:16-cron
#   command: ["postgres", "-c", "shared_preload_libraries=pg_cron",
#                          "-c", "cron.database_name=valbot",
#                          "-c", "cron.use_background_workers=on"]

FROM postgres:16

# Instala extensão via pacote oficial do Postgres.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-cron \
    && rm -rf /var/lib/apt/lists/*

# Default shared_preload_libraries vem do command: no compose,
# mas deixamos aqui também pra dev local sem -c args.
RUN echo "shared_preload_libraries='pg_cron'" >> /usr/share/postgresql/postgresql.conf.sample
