# =============================================================================
# Backend Django — versionamento determinístico para deploy offline
# =============================================================================
#
# Build args:
#   MIS_VERSION       — versão semântica (ex: 1.5.2)
#   MIS_GIT_HASH      — git rev-parse --short HEAD
#   MIS_BUILD_TIME    — date -u +%Y-%m-%dT%H:%M:%SZ
#
# Disponível em:
#   GET /api/version/  → JSON com versão real do container rodando
#   docker exec ... cat /etc/mis-version
#   docker inspect → labels org.opencontainers.image.*
# =============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Sistema
RUN apt-get update && apt-get install -y \
    gcc \
    default-mysql-client \
    netcat-openbsd \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

# Versionamento — vem por --build-arg
ARG MIS_VERSION=0.0.0-dev
ARG MIS_GIT_HASH=no-git
ARG MIS_BUILD_TIME=unknown

ENV MIS_VERSION=$MIS_VERSION \
    MIS_GIT_HASH=$MIS_GIT_HASH \
    MIS_BUILD_TIME=$MIS_BUILD_TIME

RUN echo "version=${MIS_VERSION}"   > /etc/mis-version && \
    echo "git=${MIS_GIT_HASH}"      >> /etc/mis-version && \
    echo "build_time=${MIS_BUILD_TIME}" >> /etc/mis-version

LABEL org.opencontainers.image.version="${MIS_VERSION}" \
      org.opencontainers.image.revision="${MIS_GIT_HASH}" \
      org.opencontainers.image.created="${MIS_BUILD_TIME}" \
      org.opencontainers.image.title="mis-core-django"

# Diretório para arquivos estáticos
RUN mkdir -p /app/staticfiles

EXPOSE 8000

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN dos2unix /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "config.wsgi:application"]
