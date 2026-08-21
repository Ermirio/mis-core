#!/usr/bin/env bash
# =============================================================================
# update-ot.sh - Atualizacao padrao do MIS Core em servidor OT ja instalado
#
# Uso recomendado, direto da pasta montada do Windows:
#   sudo bash /mnt/windows-migrations/pacote-vm-linux-dev/update-ot.sh
#
# Uso se a pasta ja estiver em /opt/mis-core-offline:
#   cd /opt/mis-core-offline
#   sudo bash update-ot.sh
#
# O script:
#   1. Sincroniza o pacote para /opt/mis-core-offline sem sobrescrever .env.
#   2. Valida checksum dos tar.gz.
#   3. Carrega somente imagens ainda nao aplicadas, comparando SHA256.
#   4. Aplica migrations quando Django mudou.
#   5. Reinicia apenas os servicos afetados.
#
# Nao remove volumes Docker e nao apaga dados de MySQL/InfluxDB.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PACKAGE_DIR="${MIS_PACKAGE_DIR:-$SCRIPT_DIR}"
INSTALL_DIR="${MIS_INSTALL_DIR:-/opt/mis-core-offline}"
STATE_DIR="${INSTALL_DIR}/.update-state"
BACKUP_DIR="${INSTALL_DIR}/backups"
TS="$(date +%Y%m%d-%H%M%S)"

log() {
  echo ""
  echo "==> $*"
}

warn() {
  echo "AVISO: $*" >&2
}

die() {
  echo "ERRO: $*" >&2
  exit 1
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    die "rode com sudo: sudo bash update-ot.sh"
  fi
}

abs_path() {
  readlink -f "$1"
}

env_value() {
  local key="$1"
  local value=""
  if [ -f "${INSTALL_DIR}/.env" ]; then
    value="$(grep -E "^${key}=" "${INSTALL_DIR}/.env" | head -n1 | cut -d= -f2- | tr -d '\r' || true)"
    value="${value%\"}"
    value="${value#\"}"
  fi
  printf '%s' "$value"
}

latest_matching() {
  local pattern="$1"
  # shellcheck disable=SC2086
  ls -1t $pattern 2>/dev/null | head -n1 || true
}

checksum_file_for() {
  local tarball="$1"
  printf '%s' "${tarball%.tar.gz}.sha256"
}

expected_hash_for() {
  local tarball="$1"
  local sha_file
  sha_file="$(checksum_file_for "$tarball")"
  if [ -f "$sha_file" ]; then
    awk '{print tolower($1); exit}' "$sha_file"
  else
    sha256sum "$tarball" | awk '{print tolower($1); exit}'
  fi
}

state_file_for() {
  local tarball="$1"
  printf '%s/%s.sha256' "$STATE_DIR" "$(basename "$tarball")"
}

verify_tarball() {
  local tarball="$1"
  local sha_file
  sha_file="$(checksum_file_for "$tarball")"
  if [ -f "$sha_file" ]; then
    (cd "$(dirname "$tarball")" && sha256sum -c "$(basename "$sha_file")")
  else
    warn "checksum nao encontrado para $(basename "$tarball"); calculando hash local."
    sha256sum "$tarball" >/dev/null
  fi
}

already_applied() {
  local tarball="$1"
  local expected state_file current
  expected="$(expected_hash_for "$tarball")"
  state_file="$(state_file_for "$tarball")"
  [ -f "$state_file" ] || return 1
  current="$(awk '{print tolower($1); exit}' "$state_file")"
  [ "$current" = "$expected" ]
}

mark_applied() {
  local tarball="$1"
  local expected
  expected="$(expected_hash_for "$tarball")"
  mkdir -p "$STATE_DIR"
  printf '%s  %s\n' "$expected" "$(basename "$tarball")" >"$(state_file_for "$tarball")"
}

load_tarball_if_needed() {
  local tarball="$1"
  local label="$2"
  local force="${3:-0}"

  [ -f "$tarball" ] || die "arquivo nao encontrado: $tarball"

  if [ "$force" != "1" ] && already_applied "$tarball"; then
    echo "  = $(basename "$tarball") ja aplicado; pulando."
    return 1
  fi

  echo "  -> aplicando ${label}: $(basename "$tarball")"
  verify_tarball "$tarball"
  docker load -i "$tarball"
  mark_applied "$tarball"
  return 0
}

backup_current_config() {
  [ -d "$INSTALL_DIR" ] || return 0
  mkdir -p "${BACKUP_DIR}/config-${TS}"

  for item in docker-compose.yml .env .env.example import-images.sh update-ot.sh update-nodered-nodes.sh update-django-admin-import.sh; do
    if [ -f "${INSTALL_DIR}/${item}" ]; then
      cp -a "${INSTALL_DIR}/${item}" "${BACKUP_DIR}/config-${TS}/"
    fi
  done

  if [ -d "${INSTALL_DIR}/node-red" ]; then
    mkdir -p "${BACKUP_DIR}/config-${TS}/node-red"
    cp -a "${INSTALL_DIR}/node-red/." "${BACKUP_DIR}/config-${TS}/node-red/" 2>/dev/null || true
  fi
}

sync_package() {
  mkdir -p "$INSTALL_DIR"

  local src dst
  src="$(abs_path "$PACKAGE_DIR")"
  dst="$(abs_path "$INSTALL_DIR")"

  if [ "$src" = "$dst" ]; then
    echo "  Pacote ja esta em ${INSTALL_DIR}; sincronizacao dispensada."
    return 0
  fi

  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude='.env' \
      --exclude='.update-state/' \
      --exclude='backups/' \
      --exclude='*.rar' \
      --exclude='*.log' \
      "${PACKAGE_DIR}/" "${INSTALL_DIR}/"
  else
    warn "rsync nao encontrado; usando copia simples."
    cp -a "${PACKAGE_DIR}/." "$INSTALL_DIR/"
    if [ -f "${BACKUP_DIR}/config-${TS}/.env" ]; then
      cp -a "${BACKUP_DIR}/config-${TS}/.env" "${INSTALL_DIR}/.env"
    fi
  fi
}

ensure_env() {
  if [ ! -f "${INSTALL_DIR}/.env" ]; then
    [ -f "${INSTALL_DIR}/.env.example" ] || die ".env nao existe e .env.example nao foi encontrado."
    cp "${INSTALL_DIR}/.env.example" "${INSTALL_DIR}/.env"
    die ".env foi criado em ${INSTALL_DIR}/.env. Preencha as senhas e rode o update novamente."
  fi
}

wait_containers() {
  local deadline status unhealthy starting
  deadline=$((SECONDS + 120))
  while [ "$SECONDS" -lt "$deadline" ]; do
    unhealthy="$(docker ps --filter "name=mis-core-" --filter "health=unhealthy" --format '{{.Names}}' || true)"
    starting="$(docker ps --filter "name=mis-core-" --filter "health=starting" --format '{{.Names}}' || true)"
    if [ -z "$unhealthy" ] && [ -z "$starting" ]; then
      status="ok"
      break
    fi
    echo "  ... aguardando healthchecks"
    sleep 3
  done

  docker compose ps
  if [ "${status:-}" != "ok" ]; then
    warn "alguns servicos ainda podem estar iniciando. Confira: docker compose logs -f"
  fi
}

require_root

command -v docker >/dev/null 2>&1 || die "Docker nao encontrado."
docker info >/dev/null 2>&1 || die "Docker nao esta rodando."
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin nao encontrado."

[ -d "$PACKAGE_DIR" ] || die "pasta do pacote nao encontrada: ${PACKAGE_DIR}"
[ -f "${PACKAGE_DIR}/docker-compose.yml" ] || die "docker-compose.yml nao encontrado no pacote: ${PACKAGE_DIR}"

echo "============================================================="
echo "  MIS Core - Atualizacao Padrao OT"
echo "============================================================="
echo "  Pacote:  ${PACKAGE_DIR}"
echo "  Destino: ${INSTALL_DIR}"

log "Backup de configuracoes atuais"
backup_current_config
echo "  Backup em: ${BACKUP_DIR}/config-${TS}"

log "Sincronizando pacote padrao"
sync_package

ensure_env

cd "$INSTALL_DIR"
chmod +x ./*.sh scripts/*.sh 2>/dev/null || true
bash ./scripts/ensure-portainer-password.sh .env

MIS_VERSION_FROM_ENV="$(env_value MIS_VERSION)"
MIS_VERSION="${MIS_VERSION:-${MIS_VERSION_FROM_ENV:-dev}}"

echo "  MIS_VERSION: ${MIS_VERSION}"

MAIN_TARBALL=""
if [ -f "mis-core-images-${MIS_VERSION}.tar.gz" ]; then
  MAIN_TARBALL="mis-core-images-${MIS_VERSION}.tar.gz"
else
  MAIN_TARBALL="$(latest_matching 'mis-core-images-*.tar.gz')"
fi

DJANGO_TARBALL=""
if [ -f "mis-core-django-${MIS_VERSION}.tar.gz" ]; then
  DJANGO_TARBALL="mis-core-django-${MIS_VERSION}.tar.gz"
elif [ -f "mis-core-django-dev.tar.gz" ]; then
  DJANGO_TARBALL="mis-core-django-dev.tar.gz"
fi

NODERED_TARBALL=""
if [ -f "mis-core-nodered-${MIS_VERSION}.tar.gz" ]; then
  NODERED_TARBALL="mis-core-nodered-${MIS_VERSION}.tar.gz"
elif [ -f "mis-core-nodered-dev.tar.gz" ]; then
  NODERED_TARBALL="mis-core-nodered-dev.tar.gz"
fi

main_loaded=0
django_loaded=0
nodered_loaded=0

log "Aplicando imagens alteradas"
if [ -n "$MAIN_TARBALL" ]; then
  if load_tarball_if_needed "$MAIN_TARBALL" "pacote geral" 0; then
    main_loaded=1
  fi
else
  warn "nenhum mis-core-images-*.tar.gz encontrado. Usando apenas overlays, se existirem."
fi

if [ -n "$DJANGO_TARBALL" ]; then
  if [ "$main_loaded" -eq 1 ] && [ "$DJANGO_TARBALL" -ot "$MAIN_TARBALL" ]; then
    warn "overlay Django mais antigo que o pacote geral; ignorando ${DJANGO_TARBALL}."
  else
    force_overlay=0
    [ "$main_loaded" -eq 1 ] && force_overlay=1
    if load_tarball_if_needed "$DJANGO_TARBALL" "overlay Django" "$force_overlay"; then
      django_loaded=1
    fi
  fi
fi

if [ -n "$NODERED_TARBALL" ]; then
  if [ "$main_loaded" -eq 1 ] && [ "$NODERED_TARBALL" -ot "$MAIN_TARBALL" ]; then
    warn "overlay Node-RED mais antigo que o pacote geral; ignorando ${NODERED_TARBALL}."
  else
    force_overlay=0
    [ "$main_loaded" -eq 1 ] && force_overlay=1
    if load_tarball_if_needed "$NODERED_TARBALL" "overlay Node-RED" "$force_overlay"; then
      nodered_loaded=1
    fi
  fi
fi

if [ "$main_loaded" -eq 1 ]; then
  django_loaded=1
  nodered_loaded=1
fi

log "Validando imagens do compose"
expected_images=(
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
for img in "${expected_images[@]}"; do
  if docker image inspect "$img" >/dev/null 2>&1; then
    echo "  OK $img"
  else
    echo "  X  $img nao encontrada"
    missing=$((missing + 1))
  fi
done
[ "$missing" -eq 0 ] || die "${missing} imagem(ns) ausente(s). Confira MIS_VERSION e pacote."

log "Subindo dependencias"
docker compose up -d mysql influxdb >/dev/null

if [ "$django_loaded" -eq 1 ]; then
  log "Aplicando migrations Django"
  docker compose run --rm django python manage.py migrate --noinput
fi

if [ "$main_loaded" -eq 1 ]; then
  log "Recriando servicos da aplicacao"
  docker compose up -d --force-recreate django fastapi coletor frontend chronograf grafana emqx portainer
elif [ "$django_loaded" -eq 1 ]; then
  log "Recriando Django"
  docker compose up -d --force-recreate django
else
  log "Garantindo stack ativa"
  docker compose up -d
fi

if [ "$nodered_loaded" -eq 1 ]; then
  if [ -f "./update-nodered-nodes.sh" ]; then
    log "Sincronizando volume Node-RED"
    bash ./update-nodered-nodes.sh
  else
    log "Recriando Node-RED"
    docker compose up -d --force-recreate node-red
  fi
fi

log "Healthcheck"
wait_containers

if docker compose ps django >/dev/null 2>&1; then
  log "Validacao Django"
  docker compose exec -T django python manage.py check
fi

HOST_IP="${SERVER_HOST:-$(env_value SERVER_HOST)}"
HOST_IP="${HOST_IP:-192.168.70.160}"
FRONTEND_PORT="${FRONTEND_PORT:-$(env_value FRONTEND_PORT)}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"

echo ""
echo "============================================================="
echo "  UPDATE OT CONCLUIDO"
echo "============================================================="
echo "  Interface: http://${HOST_IP}:${FRONTEND_PORT}/mis-core/"
echo "  Admin:     http://${HOST_IP}:${FRONTEND_PORT}/mis-core-admin/"
echo "  Portainer: http://${HOST_IP}:${FRONTEND_PORT}/mc-portainer/"
echo "  Usuario inicial do Portainer: admin"
echo "  Senha inicial: sudo awk -F= '/^PORTAINER_ADMIN_PASSWORD=/{print \$2}' ${INSTALL_DIR}/.env"
echo ""
echo "  Proximo update padrao:"
echo "    sudo bash /mnt/windows-migrations/pacote-vm-linux-dev/update-ot.sh"
