#!/usr/bin/env bash
# =============================================================================
# bootstrap-linux.sh - Recupera uma VM Linux nova para rodar o MIS Core offline
#
# Uso rapido, dentro da pasta mis-core-offline copiada para a VM:
#   sudo bash bootstrap-linux.sh
#
# Uso com IP fixo da rede OT:
#   sudo bash bootstrap-linux.sh --configure-network --interface ens18 \
#     --ip 192.168.70.160/24 --gateway 192.168.70.1 --dns 192.168.70.1
#
# O script:
#   1. Instala Docker Engine + Compose plugin, Python 3, Node.js e utilitarios.
#   2. Copia o pacote para /opt/mis-core-offline.
#   3. Cria .env se nao existir e gera senhas/chaves locais.
#   4. Carrega mis-core-images-<VERSION>.tar.gz e sobe o compose.
#   5. Cria um servico systemd para subir tudo automaticamente no boot.
#
# Observacao: restaurar imagens Docker nao restaura os dados do MySQL/InfluxDB.
# Se a VM antiga foi apagada sem backup dos volumes, o cadastro e historico
# precisam ser recriados.
# =============================================================================

set -euo pipefail

INSTALL_DIR="/opt/mis-core-offline"
SERVER_HOST="192.168.70.160"
CONFIGURE_NETWORK=0
STATIC_CIDR=""
GATEWAY="192.168.70.1"
DNS_SERVERS="192.168.70.1,8.8.8.8"
IFACE=""
SKIP_PREREQS=0
SKIP_DEPLOY=0
NO_SYSTEMD=0

usage() {
  cat <<'EOF'
MIS Core - bootstrap Linux

Uso:
  sudo bash bootstrap-linux.sh [opcoes]

Opcoes:
  --install-dir DIR       Diretorio final (padrao: /opt/mis-core-offline)
  --server-host IP        IP usado no .env e nos links (padrao: 192.168.70.160)
  --configure-network     Aplica IP fixo na VM (netplan ou NetworkManager)
  --interface IFACE       Interface de rede, ex: ens18, eth0
  --ip CIDR               IP/CIDR, ex: 192.168.70.160/24
  --gateway IP            Gateway principal, ex: 192.168.70.1
  --dns LISTA             DNS separado por virgula, ex: 192.168.70.1,8.8.8.8
  --skip-prereqs          Nao instala Docker/Python/Node
  --skip-deploy           Nao carrega imagens nem sobe containers
  --no-systemd            Nao cria servico de boot automatico
  -h, --help              Mostra esta ajuda

Exemplo VM OT:
  sudo bash bootstrap-linux.sh --configure-network --interface ens18 \
    --ip 192.168.70.160/24 --gateway 192.168.70.1 --dns 192.168.70.1
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --install-dir)
      INSTALL_DIR="${2:?valor obrigatorio para --install-dir}"
      shift 2
      ;;
    --server-host)
      SERVER_HOST="${2:?valor obrigatorio para --server-host}"
      shift 2
      ;;
    --configure-network)
      CONFIGURE_NETWORK=1
      shift
      ;;
    --interface|--iface)
      IFACE="${2:?valor obrigatorio para --interface}"
      shift 2
      ;;
    --ip)
      STATIC_CIDR="${2:?valor obrigatorio para --ip}"
      SERVER_HOST="${STATIC_CIDR%%/*}"
      shift 2
      ;;
    --gateway)
      GATEWAY="${2:?valor obrigatorio para --gateway}"
      shift 2
      ;;
    --dns)
      DNS_SERVERS="${2:?valor obrigatorio para --dns}"
      shift 2
      ;;
    --skip-prereqs)
      SKIP_PREREQS=1
      shift
      ;;
    --skip-deploy)
      SKIP_DEPLOY=1
      shift
      ;;
    --no-systemd)
      NO_SYSTEMD=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERRO: opcao desconhecida: $1" >&2
      usage
      exit 2
      ;;
  esac
done

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
    die "rode com sudo: sudo bash bootstrap-linux.sh"
  fi
}

run_systemctl() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl "$@"
  else
    return 1
  fi
}

docker_compose_ok() {
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1
}

install_prereqs_debian() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl gnupg lsb-release apt-transport-https \
    python3 python3-venv python3-pip jq tar gzip unzip rsync openssl iproute2 net-tools

  if ! docker_compose_ok; then
    install -m 0755 -d /etc/apt/keyrings
    . /etc/os-release
    docker_os="${ID}"
    docker_codename="${VERSION_CODENAME:-}"

    if [ -z "$docker_codename" ] && command -v lsb_release >/dev/null 2>&1; then
      docker_codename="$(lsb_release -cs)"
    fi
    [ -n "$docker_codename" ] || die "nao consegui detectar codename da distro para instalar Docker"

    curl -fsSL "https://download.docker.com/linux/${docker_os}/gpg" -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${docker_os} ${docker_codename} stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  fi

  if ! command -v node >/dev/null 2>&1; then
    if curl -fsSL https://deb.nodesource.com/setup_20.x -o /tmp/nodesource_setup.sh; then
      bash /tmp/nodesource_setup.sh
      apt-get install -y nodejs
    else
      apt-get install -y nodejs npm
    fi
  fi
}

install_prereqs_rhel() {
  dnf install -y ca-certificates curl gnupg python3 python3-pip jq tar gzip unzip rsync openssl iproute net-tools dnf-plugins-core

  if ! docker_compose_ok; then
    repo_os="centos"
    . /etc/os-release
    case "${ID:-}" in
      rhel) repo_os="rhel" ;;
      rocky|almalinux|centos|fedora) repo_os="centos" ;;
    esac
    dnf config-manager --add-repo "https://download.docker.com/linux/${repo_os}/docker-ce.repo"
    dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  fi

  if ! command -v node >/dev/null 2>&1; then
    dnf install -y nodejs npm
  fi
}

install_prereqs() {
  if [ "$SKIP_PREREQS" -eq 1 ]; then
    log "Pulando instalacao de pre-requisitos"
    return
  fi

  log "Instalando pre-requisitos da VM"
  if command -v apt-get >/dev/null 2>&1; then
    install_prereqs_debian
  elif command -v dnf >/dev/null 2>&1; then
    install_prereqs_rhel
  else
    die "distro sem apt-get/dnf suportado. Instale Docker Compose, Python 3 e Node.js manualmente."
  fi

  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now docker
  else
    service docker start || true
  fi

  if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    usermod -aG docker "$SUDO_USER" || true
  fi

  docker_compose_ok || die "Docker Compose plugin nao ficou disponivel"
  python3 --version
  node --version || true
  docker compose version
}

prepare_install_dir() {
  local src_dir
  src_dir="$(cd "$(dirname "$0")" && pwd)"

  log "Preparando pasta ${INSTALL_DIR}"
  mkdir -p "$INSTALL_DIR"

  if [ "$src_dir" != "$INSTALL_DIR" ]; then
    if command -v rsync >/dev/null 2>&1; then
      rsync -a "$src_dir"/ "$INSTALL_DIR"/
    else
      cp -a "$src_dir"/. "$INSTALL_DIR"/
    fi
  fi

  cd "$INSTALL_DIR"
  chmod +x import-images.sh scripts/check.sh scripts/install.sh bootstrap-linux.sh update-nodered-nodes.sh 2>/dev/null || true
}

latest_tarball() {
  ls -1t mis-core-images-*.tar.gz 2>/dev/null | head -n1 || true
}

version_from_tarball() {
  local tarball="$1"
  local version=""
  case "$tarball" in
    mis-core-images-*.tar.gz)
      version="${tarball#mis-core-images-}"
      version="${version%.tar.gz}"
      ;;
  esac
  echo "$version"
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  if grep -q "^${key}=" "$file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
}

generate_hex() {
  local bytes="${1:-32}"
  openssl rand -hex "$bytes"
}

replace_placeholder_secret() {
  local file="$1"
  local key="$2"
  local bytes="${3:-32}"
  local current=""
  current="$(grep "^${key}=" "$file" | head -n1 | cut -d= -f2- || true)"
  if [ -z "$current" ] || [[ "$current" == TROQUE* ]]; then
    set_env_value "$file" "$key" "$(generate_hex "$bytes")"
  fi
}

prepare_env() {
  log "Preparando .env"

  [ -f .env.example ] || die ".env.example nao encontrado em ${INSTALL_DIR}"

  if [ ! -f .env ]; then
    cp .env.example .env
    echo "  .env criado a partir de .env.example"
  else
    echo "  .env existente preservado"
  fi

  local tarball version
  tarball="$(latest_tarball)"
  version="$(version_from_tarball "$tarball")"
  if [ -n "$version" ]; then
    set_env_value .env MIS_VERSION "$version"
  fi

  local frontend_port
  frontend_port="$(grep '^FRONTEND_PORT=' .env | head -n1 | cut -d= -f2- || true)"
  frontend_port="${frontend_port:-8080}"

  set_env_value .env SERVER_HOST "$SERVER_HOST"
  set_env_value .env CSRF_TRUSTED_ORIGINS "http://${SERVER_HOST}:${frontend_port},http://localhost:${frontend_port},http://127.0.0.1:${frontend_port}"
  set_env_value .env CORS_ALLOWED_ORIGINS "http://${SERVER_HOST}:${frontend_port},http://localhost:${frontend_port},http://127.0.0.1:${frontend_port}"

  replace_placeholder_secret .env DJANGO_SECRET_KEY 40
  replace_placeholder_secret .env JWT_SECRET_KEY 40
  replace_placeholder_secret .env DJANGO_SUPERUSER_PASSWORD 18
  replace_placeholder_secret .env MYSQL_PASSWORD 18
  replace_placeholder_secret .env MYSQL_ROOT_PASSWORD 18
  replace_placeholder_secret .env INFLUXDB_PASSWORD 18
  bash ./scripts/ensure-portainer-password.sh .env

  chmod 600 .env || true

  echo "  SERVER_HOST=$(grep '^SERVER_HOST=' .env | cut -d= -f2-)"
  echo "  MIS_VERSION=$(grep '^MIS_VERSION=' .env | cut -d= -f2-)"
}

configure_network_netplan() {
  local iface="$1"
  local cidr="$2"
  local gateway="$3"
  local dns="$4"
  local dns_yaml=""
  local backup_dir="/etc/netplan/mis-core-backup-$(date +%Y%m%d%H%M%S)"

  mkdir -p "$backup_dir"
  cp -a /etc/netplan/*.yaml "$backup_dir"/ 2>/dev/null || true
  cp -a /etc/netplan/*.yml "$backup_dir"/ 2>/dev/null || true

  dns_yaml="$(printf '%s' "$dns" | sed 's/,/, /g')"
  cat > /etc/netplan/99-mis-core-ot.yaml <<EOF
network:
  version: 2
  ethernets:
    ${iface}:
      dhcp4: false
      addresses:
        - ${cidr}
      routes:
        - to: default
          via: ${gateway}
      nameservers:
        addresses: [${dns_yaml}]
EOF
  netplan apply
}

configure_network_nmcli() {
  local iface="$1"
  local cidr="$2"
  local gateway="$3"
  local dns="$4"
  local conn=""

  conn="$(nmcli -t -f NAME,DEVICE connection show --active | awk -F: -v iface="$iface" '$2 == iface {print $1; exit}')"
  [ -n "$conn" ] || conn="$iface"

  nmcli connection modify "$conn" ipv4.addresses "$cidr" ipv4.gateway "$gateway" ipv4.dns "${dns//,/ }" ipv4.method manual
  nmcli connection up "$conn"
}

configure_network() {
  if [ "$CONFIGURE_NETWORK" -ne 1 ]; then
    return
  fi

  STATIC_CIDR="${STATIC_CIDR:-${SERVER_HOST}/24}"
  IFACE="${IFACE:-$(ip route | awk '/^default/ {print $5; exit}')}"
  [ -n "$IFACE" ] || die "interface nao informada e nao detectei rota default"

  log "Configurando IP fixo ${STATIC_CIDR} na interface ${IFACE}"
  if command -v netplan >/dev/null 2>&1 && [ -d /etc/netplan ]; then
    configure_network_netplan "$IFACE" "$STATIC_CIDR" "$GATEWAY" "$DNS_SERVERS"
  elif command -v nmcli >/dev/null 2>&1; then
    configure_network_nmcli "$IFACE" "$STATIC_CIDR" "$GATEWAY" "$DNS_SERVERS"
  else
    die "nao encontrei netplan nem nmcli para aplicar rede automaticamente"
  fi
}

open_firewall_ports() {
  if command -v ufw >/dev/null 2>&1 && ufw status | grep -qi "Status: active"; then
    log "Liberando portas no UFW ativo"
    # shellcheck disable=SC1091
    [ -f .env ] && { set -a; source .env; set +a; }
    ufw allow "${FRONTEND_PORT:-8080}/tcp"
    ufw allow "${CHRONOGRAF_PORT:-8889}/tcp"
    ufw allow "${GRAFANA_PORT:-3001}/tcp"
    ufw allow "${NODE_RED_PORT:-1880}/tcp"
    ufw allow "${EMQX_MQTT_PORT:-1883}/tcp"
    ufw allow "${EMQX_WS_PORT:-8083}/tcp"
    ufw allow "${EMQX_DASHBOARD_PORT:-18083}/tcp"
  fi
}

install_systemd_unit() {
  if [ "$NO_SYSTEMD" -eq 1 ]; then
    log "Pulando servico systemd"
    return
  fi

  command -v systemctl >/dev/null 2>&1 || {
    echo "  systemd nao encontrado; pulando servico de boot"
    return
  }

  local docker_bin
  docker_bin="$(command -v docker)"

  log "Criando servico de boot automatico"
  cat > /etc/systemd/system/mis-core-offline.service <<EOF
[Unit]
Description=MIS Core Offline Docker Compose stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=${docker_bin} compose up -d
ExecStop=${docker_bin} compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable mis-core-offline.service
}

deploy_stack() {
  if [ "$SKIP_DEPLOY" -eq 1 ]; then
    log "Pulando deploy dos containers"
    return
  fi

  local tarball
  tarball="$(latest_tarball)"
  [ -n "$tarball" ] || die "nenhum mis-core-images-*.tar.gz encontrado em ${INSTALL_DIR}"
  [ -f docker-compose.yml ] || die "docker-compose.yml nao encontrado em ${INSTALL_DIR}"

  log "Carregando imagens e subindo MIS Core"
  bash import-images.sh
}

print_summary() {
  local frontend_port chronograf_port grafana_port nodered_port emqx_dash
  frontend_port="$(grep '^FRONTEND_PORT=' .env | cut -d= -f2- || echo 8080)"
  chronograf_port="$(grep '^CHRONOGRAF_PORT=' .env | cut -d= -f2- || echo 8889)"
  grafana_port="$(grep '^GRAFANA_PORT=' .env | cut -d= -f2- || echo 3001)"
  nodered_port="$(grep '^NODE_RED_PORT=' .env | cut -d= -f2- || echo 1880)"
  emqx_dash="$(grep '^EMQX_DASHBOARD_PORT=' .env | cut -d= -f2- || echo 18083)"

  echo ""
  echo "============================================================="
  echo "  MIS Core pronto para recadastro"
  echo "============================================================="
  echo "  Pasta:      ${INSTALL_DIR}"
  echo "  Interface:  http://${SERVER_HOST}:${frontend_port}/mis-core/"
  echo "  Admin:      http://${SERVER_HOST}:${frontend_port}/mis-core-admin/"
  echo "  FastAPI:    http://${SERVER_HOST}:${frontend_port}/api/v2/docs"
  echo "  Chronograf: http://${SERVER_HOST}:${chronograf_port}"
  echo "  Grafana:    http://${SERVER_HOST}:${grafana_port}"
  echo "  Node-RED:   http://${SERVER_HOST}:${nodered_port}"
  echo "  EMQX:       http://${SERVER_HOST}:${emqx_dash}"
  echo "  Portainer:  http://${SERVER_HOST}:${frontend_port}/mc-portainer/"
  echo "  Usuario inicial do Portainer: admin"
  echo "  Senha inicial: sudo awk -F= '/^PORTAINER_ADMIN_PASSWORD=/{print \$2}' ${INSTALL_DIR}/.env"
  echo ""
  echo "  Logs:       cd ${INSTALL_DIR} && docker compose logs -f"
  echo "  Status:     cd ${INSTALL_DIR} && docker compose ps"
  echo "  Smoke test: cd ${INSTALL_DIR} && bash scripts/check.sh ${SERVER_HOST}"
  echo ""
  echo "  Aviso: dados antigos nao voltam sem backup dos volumes MySQL/InfluxDB."
}

main() {
  require_root
  install_prereqs
  prepare_install_dir
  configure_network
  prepare_env
  open_firewall_ports
  install_systemd_unit
  deploy_stack
  print_summary
}

main "$@"
