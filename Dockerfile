# syntax=docker/dockerfile:1.7
# =============================================================================
# valbot-api — imagem API-only (FastAPI/uvicorn). O frontend vive no repo
# lbigor/valbot-web e é servido pelo Caddy (estático) com proxy de /api → aqui.
# =============================================================================
FROM python:3.12-slim AS runtime

ARG IMAGE_VERSION=dev
ARG GIT_SHA=unknown

# Deps de sistema (prod gemini-only): weasyprint runtime (PDF) + curl (healthcheck).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev \
        fontconfig fonts-liberation fonts-dejavu-core \
        libglib2.0-0 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Usuário não-root (UID 1000).
RUN groupadd --system --gid 1000 valbot \
    && useradd  --system --uid 1000 --gid valbot --shell /bin/bash --create-home valbot

WORKDIR /opt/valbot

# Layer cacheada de dependências Python (tudo pinado em requirements.txt).
COPY --chown=valbot:valbot requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação — TODOS os diretórios que o servidor importa.
COPY --chown=valbot:valbot backend/ ./backend/
COPY --chown=valbot:valbot src/ ./src/
COPY --chown=valbot:valbot tooling/ ./tooling/
COPY --chown=valbot:valbot migrations/ ./migrations/

RUN mkdir -p /opt/valbot/storage/analyses /opt/valbot/storage/uploads \
    && chown -R valbot:valbot /opt/valbot/storage

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_FORMAT=json \
    PORT=80 \
    VERTEX_PROJECT=valbot-497920 \
    VERTEX_LOCATION=global \
    VERTEX_MODEL=gemini-2.5-pro \
    GCS_BUCKET=valbot-prod-data

LABEL org.opencontainers.image.title="valbot-api" \
      org.opencontainers.image.description="VALBOT - Auditoria Inteligente de Exames Práticos (API)" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}"

EXPOSE 80
USER valbot

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD curl -fsS http://localhost:80/api/health || exit 1

# API-only: uvicorn direto na :80 (o Caddy faz o proxy de /api).
CMD ["uvicorn", "tooling.api_stub.server:app", \
     "--host", "0.0.0.0", "--port", "80", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips=*", "--log-level", "info"]
