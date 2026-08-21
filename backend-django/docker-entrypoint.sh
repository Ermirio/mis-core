#!/bin/sh
set -e

echo "[entrypoint] Starting Django entrypoint..."

# Defaults seguros (caso env não exista)
MYSQL_HOST="${MYSQL_HOST:-mysql}"
MYSQL_PORT="${MYSQL_PORT:-3306}"

INFLUXDB_HOST="${INFLUXDB_HOST:-influxdb}"
INFLUXDB_PORT="${INFLUXDB_PORT:-8086}"

echo "[entrypoint] Waiting for MySQL at ${MYSQL_HOST}:${MYSQL_PORT}..."
until nc -z "$MYSQL_HOST" "$MYSQL_PORT"; do
  echo "[entrypoint] MySQL not ready yet..."
  sleep 2
done
echo "[entrypoint] MySQL is up."

echo "[entrypoint] Waiting for InfluxDB at ${INFLUXDB_HOST}:${INFLUXDB_PORT}..."
until nc -z "$INFLUXDB_HOST" "$INFLUXDB_PORT"; do
  echo "[entrypoint] InfluxDB not ready yet..."
  sleep 2
done
echo "[entrypoint] InfluxDB is up."

echo "[entrypoint] Running migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Creating superuser..."
python manage.py createsuperuser --noinput || echo "Superuser already exists or failed to create"

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput || true

# Em modo DEMO, popula topologia idempotentemente (somente adiciona dados,
# nunca apaga). Em modo PRODUCTION, NADA é apagado automaticamente — para
# limpar dados de simulação que possam ter restado, rode manualmente:
#
#   docker compose exec django python manage.py clean_demo --backup
#
# O flag --backup faz dump SQL antes da remoção, em /app/backups/.
if [ "${MIS_MODE:-production}" = "demo" ]; then
  echo "[entrypoint] MIS_MODE=demo — executando seed_demo..."
  python manage.py seed_demo || echo "[entrypoint] seed_demo falhou (continuando)"
else
  echo "[entrypoint] MIS_MODE=${MIS_MODE:-production} — nenhuma manutenção automática de dados."
  echo "[entrypoint]   Para limpar resquícios de demo: python manage.py clean_demo --backup"
fi

echo "[entrypoint] Starting server..."
exec "$@"
