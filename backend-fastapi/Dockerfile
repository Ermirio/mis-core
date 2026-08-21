# Dockerfile — mis-core FastAPI v2
# --------------------------------
# Build slim, não-root, com healthcheck.
# Usa uvicorn em modo produção (1 worker por container; escale horizontal via orchestrator).

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependências do sistema mínimas (build-essential só para compilar wheels de numpy/scipy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copia pyproject primeiro para aproveitar cache de camadas
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install "fastapi[standard]" uvicorn[standard] pydantic pydantic-settings \
    httpx pandas numpy scipy tenacity structlog pyjwt prometheus-fastapi-instrumentator

# Agora copia o resto
COPY app ./app
COPY tests ./tests

# Usuário não-root
RUN useradd --create-home --shell /bin/bash miscore && chown -R miscore:miscore /app
USER miscore

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl --fail http://localhost:8000/api/v2/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
