#!/bin/bash
set -e

echo "[entrypoint] Starting MIS Change Over backend..."

# Aguardar MySQL
echo "[entrypoint] Waiting for MySQL at ${DB_HOST}:${DB_PORT}..."
while ! nc -z "${DB_HOST:-mysql}" "${DB_PORT:-3306}" 2>/dev/null; do
    echo "[entrypoint] MySQL not ready, retrying in 2s..."
    sleep 2
done
echo "[entrypoint] MySQL is up."

# Rodar migrations
echo "[entrypoint] Running migrations..."
python manage.py migrate --noinput

# Coleta de arquivos estáticos
echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || true

# Criar superuser se não existir
echo "[entrypoint] Creating superuser if not exists..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='${DJANGO_SUPERUSER_USERNAME:-admin}').exists():
    User.objects.create_superuser('${DJANGO_SUPERUSER_USERNAME:-admin}', '${DJANGO_SUPERUSER_EMAIL:-admin@example.com}', '${DJANGO_SUPERUSER_PASSWORD:-admin123}')
    print('Superuser created.')
else:
    print('Superuser already exists.')
" 2>/dev/null || echo "[entrypoint] Superuser creation skipped."

# Iniciar servidor
echo "[entrypoint] Starting gunicorn..."
exec gunicorn digitalfactory.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
