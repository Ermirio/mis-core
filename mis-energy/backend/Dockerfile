# Dockerfile - Backend Flask (MIS-Energy)
# Build for energy monitoring application

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs database

# Expose port
EXPOSE 5005

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5005/api/health')" || exit 1

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5005", "--workers", "2", "--timeout", "120", "main:app"]
