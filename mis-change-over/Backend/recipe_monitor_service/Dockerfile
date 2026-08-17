FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências de sistema mínimas (asyncua pode precisar de cryptography → build)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala deps primeiro para cachear layer
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

# Copia o código depois (mudanças no código não invalidam o cache de deps)
COPY app ./app

EXPOSE 8100

# Saúde — o orchestrator pode usar isso para readiness
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
