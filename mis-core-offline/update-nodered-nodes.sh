#!/usr/bin/env bash
# =============================================================================
# update-nodered-nodes.sh - Atualiza os nos Node-RED em VM ja restaurada
#
# Uso no servidor OT, dentro de /opt/mis-core-offline:
#   sudo bash update-nodered-nodes.sh
#
# Uso quando voce levou apenas uma imagem nova do Node-RED:
#   sudo bash update-nodered-nodes.sh ./mis-core-nodered-dev.tar.gz
#
# O script:
#   1. Carrega uma imagem nova, se um tar.gz for informado.
#   2. Descobre o volume /data usado pelo container mis-core-nodered.
#   3. Faz backup do volume atual.
#   4. Copia node_modules/package.json da imagem para o volume existente.
#   5. Reinicia apenas o Node-RED.
#
# Assim os flows/projetos atuais ficam preservados, mas os nos industriais
# passam a existir no Palette Manager sem depender de internet no OT.
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

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    die "rode com sudo: sudo bash update-nodered-nodes.sh"
  fi
}

compose() {
  docker compose "$@"
}

env_value() {
  local key="$1"
  local value=""
  if [ -f .env ]; then
    value="$(grep -E "^${key}=" .env | head -n1 | cut -d= -f2- | tr -d '\r' || true)"
    value="${value%\"}"
    value="${value#\"}"
  fi
  printf '%s' "$value"
}

require_root

command -v docker >/dev/null 2>&1 || die "Docker nao encontrado"
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin nao encontrado"
[ -f docker-compose.yml ] || die "docker-compose.yml nao encontrado em ${INSTALL_DIR}"

VERSION="${MIS_VERSION:-$(env_value MIS_VERSION)}"
VERSION="${VERSION:-dev}"
IMAGE="mis-core-nodered:${VERSION}"
CONTAINER="mis-core-nodered"
IMAGE_TARBALL="${1:-}"

if [ -n "$IMAGE_TARBALL" ]; then
  [ -f "$IMAGE_TARBALL" ] || die "imagem informada nao encontrada: ${IMAGE_TARBALL}"
  log "Carregando imagem ${IMAGE_TARBALL}"
  docker load -i "$IMAGE_TARBALL"
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  die "imagem ${IMAGE} nao encontrada. Rode import-images.sh ou informe o tar.gz da imagem Node-RED."
fi

log "Validando imagem ${IMAGE}"
docker run --rm --entrypoint sh "$IMAGE" -c 'test -d /data/node_modules && test -f /data/package.json'

VOLUME="$(docker inspect "$CONTAINER" --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' 2>/dev/null || true)"

if [ -z "$VOLUME" ]; then
  log "Container ainda nao existe. Subindo Node-RED com a imagem atual."
  compose up -d node-red
  compose ps node-red
  exit 0
fi

BACKUP_DIR="${INSTALL_DIR}/backups"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="nodered_data_${TS}.tar.gz"
mkdir -p "$BACKUP_DIR"

log "Fazendo backup do volume ${VOLUME}"
docker run --rm -u root --entrypoint sh \
  -v "${VOLUME}:/source-data:ro" \
  -v "${BACKUP_DIR}:/backup" \
  "$IMAGE" \
  -c "cd /source-data && tar czf /backup/${BACKUP_FILE} ."
echo "  Backup: ${BACKUP_DIR}/${BACKUP_FILE}"

log "Parando Node-RED"
compose stop node-red >/dev/null || true

log "Sincronizando node_modules da imagem para o volume existente"
docker run --rm -u root --entrypoint sh \
  -v "${VOLUME}:/target-data" \
  "$IMAGE" \
  -c '
    set -e
    rm -rf /target-data/node_modules /target-data/package.json /target-data/package-lock.json
    cp -a /data/node_modules /target-data/node_modules
    cp -a /data/package.json /target-data/package.json
    if [ -f /data/package-lock.json ]; then
      cp -a /data/package-lock.json /target-data/package-lock.json
    fi
    chown -R node-red:node-red /target-data/node_modules /target-data/package.json /target-data/package-lock.json 2>/dev/null || true
  '

log "Subindo Node-RED"
compose up -d node-red
sleep 8
compose ps node-red

log "Nos principais instalados"
docker exec "$CONTAINER" sh -lc 'npm ls --depth=0 node-red-contrib-modbus node-red-contrib-influxdb node-red-node-mysql node-red-dashboard @flowfuse/node-red-dashboard || true'

echo ""
echo "OK: Node-RED atualizado. Abra o editor e confira Palette Manager -> Installed."
