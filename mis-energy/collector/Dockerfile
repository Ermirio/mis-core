FROM python:3.9-slim

WORKDIR /app

# Instalar dependências do sistema necessárias para compilar pacotes (se houver)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Variáveis de ambiente padrão (podem ser sobrescritas no docker-compose)
ENV BACKEND_URL=http://mis-energy-backend:5005/api
ENV POLL_INTERVAL=10

CMD ["python", "-u", "main.py"]
