# syntax=docker/dockerfile:1.7
# =============================================================================
# Valbot — imagem all-in-one (frontend buildado + FastAPI + nginx no mesmo pod).
# Multi-arch (linux/amd64 alvo prod). Multi-stage para enxugar a imagem final.
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1 — frontend build (pnpm + Vite)
# -----------------------------------------------------------------------------
FROM node:22-slim AS frontend-build
WORKDIR /build
RUN npm install -g pnpm@9

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml frontend/tsconfig.base.json frontend/tsconfig.json ./frontend/
COPY frontend/artifacts/valbot/package.json ./frontend/artifacts/valbot/

# `--no-frozen-lockfile` evita falha por mismatch de plataforma do lockfile gerado em arm64.
# `--ignore-scripts` pula preinstall que checa `npm_config_user_agent` (env vazio em Docker).
# Glibc-base (slim) evita problema do binding `@rollup/rollup-linux-x64-musl` faltante.
RUN cd frontend && pnpm install --no-frozen-lockfile --ignore-scripts

COPY frontend/ ./frontend/
RUN cd frontend && pnpm --filter @workspace/valbot build

# -----------------------------------------------------------------------------
# Stage 2 — runtime Python + nginx
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ARG IMAGE_VERSION=dev
ARG GIT_SHA=unknown

# Dependências de sistema (prod gemini-only):
#   weasyprint runtime    — libpango, libcairo, libgdk-pixbuf, fontconfig (PDF)
#   libglib2.0-0          — dep transitiva do glib usada por cairo/pango (mantém)
#   nginx                 — reverse proxy + serve frontend estático
#   curl                  — healthcheck
# REMOVIDOS: libgl1 (era pra opencv), ffmpeg (era pra transcoding local).
# Pipeline prod (Gemini 3.1 Pro Preview) lê vídeo direto do GCS via Vertex.
RUN apt-get update && apt-get install -y --no-install-recommends \
        nginx \
        curl \
        libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev \
        fontconfig fonts-liberation fonts-dejavu-core \
        libglib2.0-0 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Usuário não-root (UID 1000) por segurança.
RUN groupadd --system --gid 1000 valbot \
    && useradd  --system --uid 1000 --gid valbot --shell /bin/bash --create-home valbot

WORKDIR /opt/valbot

# Layer cacheada de dependências Python.
COPY --chown=valbot:valbot requirements.txt requirements-prod.txt* ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        fastapi \
        uvicorn[standard] \
        python-multipart \
        structlog \
        google-cloud-aiplatform \
        google-cloud-storage \
        psycopg2-binary

# Código + frontend buildado.
COPY --chown=valbot:valbot src/ ./src/
COPY --chown=valbot:valbot tooling/ ./tooling/
COPY --chown=valbot:valbot migrations/ ./migrations/
COPY --chown=valbot:valbot deploy/start.sh /usr/local/bin/start.sh
COPY --chown=valbot:valbot deploy/nginx.conf /etc/nginx/sites-enabled/default
COPY --from=frontend-build --chown=valbot:valbot /build/frontend/artifacts/valbot/dist /opt/valbot/frontend-dist

RUN chmod +x /usr/local/bin/start.sh \
    && rm -f /etc/nginx/sites-enabled/default.dpkg-dist \
    && mkdir -p /var/log/nginx /var/lib/nginx/body \
    && mkdir -p /opt/valbot/storage/analyses /opt/valbot/storage/analyses_demo /opt/valbot/storage/uploads \
    && sed -i 's|/run/nginx.pid|/tmp/nginx.pid|g' /etc/nginx/nginx.conf \
    && sed -i 's|^user .*|# user diretiva removida — container roda como valbot (UID 1000) via USER do Dockerfile|' /etc/nginx/nginx.conf \
    && chown -R valbot:valbot /var/log/nginx /var/lib/nginx /etc/nginx /tmp /opt/valbot/storage

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_FORMAT=json \
    PORT=80 \
    VERTEX_PROJECT=project-308f1fa8-a301-49e6-a69 \
    VERTEX_LOCATION=global \
    VERTEX_MODEL=gemini-3.1-pro-preview \
    GCS_BUCKET=valbot-prod

LABEL org.opencontainers.image.title="valbot-api" \
      org.opencontainers.image.description="VALBOT - Auditoria Inteligente de Exames Práticos" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}"

EXPOSE 80
USER valbot

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD curl -fsS http://localhost:80/api/health || exit 1

CMD ["/usr/local/bin/start.sh"]
