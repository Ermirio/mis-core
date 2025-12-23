#!/bin/sh
set -e

# Defaults seguros (caso env não venha)
INFLUXDB_HOST="${INFLUXDB_HOST:-influxdb}"
INFLUXDB_PORT="${INFLUXDB_PORT:-8086}"

DJANGO_HOST="${DJANGO_HOST:-django}"
DJANGO_PORT="${DJANGO_PORT:-8000}"

echo "🔄 Aguardando InfluxDB em ${INFLUXDB_HOST}:${INFLUXDB_PORT}..."
while ! nc -z "$INFLUXDB_HOST" "$INFLUXDB_PORT"; do
  sleep 1
done
echo "✅ InfluxDB está pronto!"

echo "🔄 Aguardando Django em ${DJANGO_HOST}:${DJANGO_PORT}..."
while ! nc -z "$DJANGO_HOST" "$DJANGO_PORT"; do
  sleep 1
done
echo "✅ Django está pronto!"

echo "🚀 Iniciando servidor Flask..."
exec "$@"
