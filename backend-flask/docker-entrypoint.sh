#!/bin/bash
set -e

echo "🔄 Aguardando InfluxDB..."
while ! nc -z $INFLUXDB_HOST $INFLUXDB_PORT; do
  sleep 1
done
echo "✅ InfluxDB está pronto!"

echo "🔄 Aguardando Django API..."
while ! nc -z django $DJANGO_PORT; do
  sleep 1
done
echo "✅ Django API está pronta!"

echo "🚀 Iniciando servidor Flask..."
exec "$@"
