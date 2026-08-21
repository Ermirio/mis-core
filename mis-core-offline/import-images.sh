#!/usr/bin/env bash
# =============================================================================
# import-images.sh - Importa imagens e sobe MIS Core no servidor OT Linux
#
# Uso no servidor offline:
#   bash import-images.sh
#
# Espera encontrar na mesma pasta:
#   docker-compose.yml
#   .env.example
#   mis-core-images-<VERSION>.tar.gz
#   mis-core-images-<VERSION>.sha256
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================="
echo "  MIS Core - Deploy Offline OT"
echo "============================================================="
echo ""

command -v docker >/dev/null 2>&1 || { echo "ERRO: docker nao encontrado."; exit 1; }
docker info >/dev/null 2>&1 || { echo "ERRO: Docker nao esta rodando."; exit 1; }

TARBALL_GZ="$(ls -1t mis-core-images-*.tar.gz 2>/dev/null | head -n1 || true)"
if [ -z "$TARBALL_GZ" ]; then
  echo "ERRO: nenhum mis-core-images-*.tar.gz encontrado nesta pasta."
  exit 1
fi

if [ ! -f docker-compose.yml ]; then
  echo "ERRO: docker-compose.yml nao encontrado."
  exit 1
fi

VERSION_FROM_FILE=""
case "$TARBALL_GZ" in
  mis-core-images-*.tar.gz)
    VERSION_FROM_FILE="${TARBALL_GZ#mis-core-images-}"
    VERSION_FROM_FILE="${VERSION_FROM_FILE%.tar.gz}"
    ;;
esac

if [ ! -f .env ]; then
  if [ ! -f .env.example ]; then
    echo "ERRO: .env nao existe e .env.example nao foi encontrado."
    exit 1
  fi
  cp .env.example .env
  if [ -n "$VERSION_FROM_FILE" ]; then
    sed -i "s/^MIS_VERSION=.*/MIS_VERSION=${VERSION_FROM_FILE}/" .env
  fi
  echo "ATENCAO: .env criado a partir de .env.example."
  echo "Revise senhas e parametros antes do uso definitivo em producao."
fi

bash ./scripts/ensure-portainer-password.sh .env

set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "${MIS_VERSION:-}" ]; then
  echo "ERRO: MIS_VERSION nao definido no .env."
  exit 1
fi

echo "[1/6] Arquivos"
echo "  Tarball: ${TARBALL_GZ}"
echo "  Version: ${MIS_VERSION}"
echo ""

echo "[2/6] Checksum"
SHA_FILE="${TARBALL_GZ%.tar.gz}.sha256"
if [ -f "$SHA_FILE" ]; then
  sha256sum -c "$SHA_FILE"
else
  echo "  Aviso: ${SHA_FILE} nao encontrado; pulando verificacao."
fi
echo ""

echo "[3/6] Docker load"
docker load -i "$TARBALL_GZ"

NODE_RED_TARBALL=""
if [ -f "mis-core-nodered-${MIS_VERSION}.tar.gz" ]; then
  NODE_RED_TARBALL="mis-core-nodered-${MIS_VERSION}.tar.gz"
elif [ -f "mis-core-nodered-dev.tar.gz" ]; then
  NODE_RED_TARBALL="mis-core-nodered-dev.tar.gz"
fi

if [ -n "$NODE_RED_TARBALL" ]; then
  echo ""
  echo "  Overlay Node-RED: ${NODE_RED_TARBALL}"
  NODE_RED_SHA="${NODE_RED_TARBALL%.tar.gz}.sha256"
  if [ -f "$NODE_RED_SHA" ]; then
    sha256sum -c "$NODE_RED_SHA"
  else
    echo "  Aviso: ${NODE_RED_SHA} nao encontrado; pulando verificacao."
  fi
  docker load -i "$NODE_RED_TARBALL"
fi

DJANGO_TARBALL=""
if [ -f "mis-core-django-${MIS_VERSION}.tar.gz" ]; then
  DJANGO_TARBALL="mis-core-django-${MIS_VERSION}.tar.gz"
elif [ -f "mis-core-django-dev.tar.gz" ]; then
  DJANGO_TARBALL="mis-core-django-dev.tar.gz"
fi

if [ -n "$DJANGO_TARBALL" ]; then
  echo ""
  echo "  Overlay Django: ${DJANGO_TARBALL}"
  DJANGO_SHA="${DJANGO_TARBALL%.tar.gz}.sha256"
  if [ -f "$DJANGO_SHA" ]; then
    sha256sum -c "$DJANGO_SHA"
  else
    echo "  Aviso: ${DJANGO_SHA} nao encontrado; pulando verificacao."
  fi
  docker load -i "$DJANGO_TARBALL"
fi
echo ""

echo "[4/6] Validando imagens exigidas pelo compose offline"
EXPECTED_IMAGES=(
  "mis-core-frontend:${MIS_VERSION}"
  "mis-core-django:${MIS_VERSION}"
  "mis-core-fastapi:${MIS_VERSION}"
  "mis-core-coletor:${MIS_VERSION}"
  "mis-core-nodered:${MIS_VERSION}"
  "mysql:8.0"
  "influxdb:1.8-alpine"
  "chronograf:1.8"
  "grafana/grafana:10.4.2"
  "emqx/emqx:5.6.1"
  "portainer/portainer-ce:2.39.5-alpine"
)

missing=0
for img in "${EXPECTED_IMAGES[@]}"; do
  if docker image inspect "$img" >/dev/null 2>&1; then
    echo "  OK $img"
  else
    echo "  X  $img nao encontrada"
    missing=$((missing + 1))
  fi
done

if [ "$missing" -gt 0 ]; then
  echo "ERRO: ${missing} imagem(ns) ausente(s). Confira MIS_VERSION e tarball."
  exit 2
fi
echo ""

echo "[5/6] Subindo containers"
docker compose down || true
docker compose up -d
echo ""

echo "[6/6] Aguardando healthchecks (ate 120s)"
EXPECTED_CONTAINERS=(
  "mis-core-mysql"
  "mis-core-influxdb"
  "mis-core-django"
  "mis-core-fastapi"
  "mis-core-coletor"
  "mis-core-frontend"
  "mis-core-chronograf"
  "mis-core-grafana"
  "mis-core-nodered"
  "mis-core-emqx"
  "mis-core-portainer"
)

ready=0
deadline=$((SECONDS + 120))
while [ "$SECONDS" -lt "$deadline" ]; do
  all_up=1
  running="$(docker ps --format '{{.Names}}' || true)"
  for c in "${EXPECTED_CONTAINERS[@]}"; do
    if ! printf '%s\n' "$running" | grep -qx "$c"; then
      all_up=0
      break
    fi
  done

  unhealthy="$(docker ps --filter "name=mis-core-" --filter "health=unhealthy" --format '{{.Names}}' || true)"
  starting="$(docker ps --filter "name=mis-core-" --filter "health=starting" --format '{{.Names}}' || true)"

  if [ "$all_up" -eq 1 ] && [ -z "$unhealthy" ] && [ -z "$starting" ]; then
    ready=1
    break
  fi

  sleep 3
  echo "  ... aguardando containers"
done

docker compose ps
if [ "$ready" -ne 1 ]; then
  echo ""
  echo "AVISO: nem todos os servicos ficaram saudaveis em 120s."
  echo "       Pode acontecer na primeira subida. Confira: docker compose logs -f"
fi
echo ""

HOST_IP="${SERVER_HOST:-192.168.70.160}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
CHRONOGRAF_PORT="${CHRONOGRAF_PORT:-8889}"

echo "============================================================="
echo "  DEPLOY CONCLUIDO - MIS Core ${MIS_VERSION}"
echo "============================================================="
echo "  Interface:   http://${HOST_IP}:${FRONTEND_PORT}/mis-core/"
echo "  Admin:       http://${HOST_IP}:${FRONTEND_PORT}/mis-core-admin/"
echo "  FastAPI:     http://${HOST_IP}:${FRONTEND_PORT}/api/v2/docs"
echo "  Chronograf:  http://${HOST_IP}:${CHRONOGRAF_PORT}"
echo ""
echo "  Logs:        docker compose logs -f"
echo "  Smoke test:  bash scripts/check.sh"
