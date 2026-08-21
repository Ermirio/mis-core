#!/usr/bin/env bash
# =============================================================================
# update-django-admin-import.sh - Atualiza Django para corrigir import/export
#
# Uso no servidor OT, dentro de /opt/mis-core-offline:
#   sudo bash update-django-admin-import.sh ./mis-core-django-dev.tar.gz
#
# O script carrega a imagem Django nova, recria apenas o container Django e
# valida o healthcheck. Nao remove volumes nem apaga dados.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${MIS_INSTALL_DIR:-/opt/mis-core-offline}"

if [ ! -f "${INSTALL_DIR}/docker-compose.yml" ]; then
  INSTALL_DIR="$SCRIPT_DIR"
fi

cd "$INSTALL_DIR"

log() {
  echo ""
  echo "==> $*"
}

die() {
  echo "ERRO: $*" >&2
  exit 1
}

if [ "$(id -u)" -ne 0 ]; then
  die "rode com sudo: sudo bash update-django-admin-import.sh ./mis-core-django-dev.tar.gz"
fi

command -v docker >/dev/null 2>&1 || die "Docker nao encontrado"
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin nao encontrado"
[ -f docker-compose.yml ] || die "docker-compose.yml nao encontrado em ${INSTALL_DIR}"

TARBALL="${1:-./mis-core-django-dev.tar.gz}"
[ -f "$TARBALL" ] || die "imagem Django nao encontrada: ${TARBALL}"

if [ -f "${TARBALL%.tar.gz}.sha256" ]; then
  log "Validando checksum"
  sha256sum -c "${TARBALL%.tar.gz}.sha256"
fi

log "Carregando imagem Django"
docker load -i "$TARBALL"

MIS_VERSION_FROM_ENV=""
if [ -f .env ]; then
  MIS_VERSION_FROM_ENV="$(grep '^MIS_VERSION=' .env | head -n1 | cut -d= -f2- | tr -d '\r' || true)"
fi
MIS_VERSION="${MIS_VERSION:-${MIS_VERSION_FROM_ENV:-dev}}"
IMAGE="mis-core-django:${MIS_VERSION}"

docker image inspect "$IMAGE" >/dev/null 2>&1 || die "imagem ${IMAGE} nao encontrada apos docker load"

log "Aplicando migracoes pendentes, se houver"
docker compose up -d mysql influxdb >/dev/null || true
docker compose run --rm django python manage.py migrate --noinput

log "Recriando apenas o Django"
docker compose up -d --force-recreate django

log "Aguardando Django ficar saudavel"
deadline=$((SECONDS + 120))
while [ "$SECONDS" -lt "$deadline" ]; do
  status="$(docker inspect mis-core-django --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || true)"
  if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
    break
  fi
  echo "  ... status: ${status:-aguardando}"
  sleep 3
done

docker compose ps django
docker compose exec -T django python manage.py check

echo ""
echo "OK: Django atualizado. Teste o Admin em /mis-core-admin/ e importe a planilha novamente."
