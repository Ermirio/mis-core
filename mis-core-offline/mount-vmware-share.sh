#!/usr/bin/env bash
# =============================================================================
# mount-vmware-share.sh - Monta pasta compartilhada VMware dentro do Linux
#
# Antes de rodar este script, configure no VMware:
#   VM Settings -> Options -> Shared Folders -> Always enabled
#   Add... -> Host path: D:\migrations -> Name: migrations
#
# Uso padrao:
#   sudo bash mount-vmware-share.sh
#
# Depois do mount, a pasta do Windows fica em:
#   /mnt/windows-migrations
# =============================================================================

set -euo pipefail

SHARE_NAME="migrations"
MOUNT_POINT="/mnt/windows-migrations"
PERSIST=1
INSTALL_TOOLS=1
OWNER_USER="${SUDO_USER:-${USER:-root}}"

usage() {
  cat <<'EOF'
MIS Core - mount VMware shared folder

Uso:
  sudo bash mount-vmware-share.sh [opcoes]

Opcoes:
  --share NOME       Nome do compartilhamento VMware (padrao: migrations)
  --mount DIR        Ponto de montagem no Linux (padrao: /mnt/windows-migrations)
  --owner USER       Usuario dono dos arquivos montados (padrao: usuario do sudo)
  --no-persist       Monta agora, mas nao grava no /etc/fstab
  --skip-install     Nao instala open-vm-tools/fuse
  -h, --help         Mostra esta ajuda

Exemplo:
  sudo bash mount-vmware-share.sh --share migrations --mount /mnt/windows-migrations

No VMware, o Windows D:\migrations deve ser adicionado com Name=migrations.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --share)
      SHARE_NAME="${2:?valor obrigatorio para --share}"
      shift 2
      ;;
    --mount)
      MOUNT_POINT="${2:?valor obrigatorio para --mount}"
      shift 2
      ;;
    --owner)
      OWNER_USER="${2:?valor obrigatorio para --owner}"
      shift 2
      ;;
    --no-persist)
      PERSIST=0
      shift
      ;;
    --skip-install)
      INSTALL_TOOLS=0
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
    die "rode com sudo: sudo bash mount-vmware-share.sh"
  fi
}

owner_uid_gid() {
  if id "$OWNER_USER" >/dev/null 2>&1; then
    OWNER_UID="$(id -u "$OWNER_USER")"
    OWNER_GID="$(id -g "$OWNER_USER")"
  else
    OWNER_UID="0"
    OWNER_GID="0"
  fi
}

install_tools_debian() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y open-vm-tools fuse3 ca-certificates || apt-get install -y open-vm-tools fuse ca-certificates
}

install_tools_rhel() {
  dnf install -y open-vm-tools fuse3 fuse3-libs ca-certificates || dnf install -y open-vm-tools fuse ca-certificates
}

install_tools() {
  if [ "$INSTALL_TOOLS" -eq 0 ]; then
    log "Pulando instalacao de ferramentas VMware"
    return
  fi

  log "Instalando open-vm-tools e FUSE"
  if command -v apt-get >/dev/null 2>&1; then
    install_tools_debian
  elif command -v dnf >/dev/null 2>&1; then
    install_tools_rhel
  else
    die "distro sem apt-get/dnf suportado. Instale open-vm-tools e fuse manualmente."
  fi

  modprobe fuse 2>/dev/null || true

  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now open-vm-tools.service 2>/dev/null || true
    systemctl restart open-vm-tools.service 2>/dev/null || true
    systemctl restart vmtoolsd.service 2>/dev/null || true
  fi
}

enable_allow_other() {
  if [ -f /etc/fuse.conf ]; then
    if grep -q '^#user_allow_other' /etc/fuse.conf; then
      sed -i 's/^#user_allow_other/user_allow_other/' /etc/fuse.conf
    elif ! grep -q '^user_allow_other' /etc/fuse.conf; then
      echo 'user_allow_other' >> /etc/fuse.conf
    fi
  fi
}

check_share_available() {
  command -v vmhgfs-fuse >/dev/null 2>&1 || die "vmhgfs-fuse nao encontrado. open-vm-tools nao foi instalado corretamente."

  log "Verificando compartilhamento VMware"
  if command -v vmware-hgfsclient >/dev/null 2>&1; then
    shares="$(vmware-hgfsclient 2>/dev/null || true)"
    if [ -n "$shares" ]; then
      echo "$shares" | sed 's/^/  - /'
      if ! printf '%s\n' "$shares" | grep -qx "$SHARE_NAME"; then
        echo ""
        echo "Nao encontrei o share '${SHARE_NAME}'."
        echo "No VMware configure:"
        echo "  Host path: D:\\migrations"
        echo "  Name:      ${SHARE_NAME}"
        echo "  Shared Folders: Always enabled"
        die "compartilhamento VMware ainda nao esta visivel para o Linux"
      fi
    else
      echo "  Nenhum share listado. Confira se Shared Folders esta habilitado na VM."
      die "compartilhamento VMware nao esta visivel"
    fi
  else
    echo "  vmware-hgfsclient nao encontrado; vou tentar montar direto."
  fi
}

mount_share() {
  log "Montando .host:/${SHARE_NAME} em ${MOUNT_POINT}"
  mkdir -p "$MOUNT_POINT"

  if findmnt -rn "$MOUNT_POINT" >/dev/null 2>&1; then
    echo "  ${MOUNT_POINT} ja esta montado."
    return
  fi

  vmhgfs-fuse ".host:/${SHARE_NAME}" "$MOUNT_POINT" \
    -o "allow_other,uid=${OWNER_UID},gid=${OWNER_GID},umask=022"

  findmnt "$MOUNT_POINT" >/dev/null 2>&1 || die "mount nao apareceu em findmnt"
}

persist_mount() {
  if [ "$PERSIST" -eq 0 ]; then
    log "Persistencia desativada (--no-persist)"
    return
  fi

  log "Gravando montagem no /etc/fstab"
  cp /etc/fstab "/etc/fstab.mis-core-backup.$(date +%Y%m%d%H%M%S)"

  if grep -q "[[:space:]]${MOUNT_POINT//\//\\/}[[:space:]]" /etc/fstab; then
    sed -i "\|[[:space:]]${MOUNT_POINT//\//\\/}[[:space:]]|s|^|# desativado pelo MIS Core restore: |" /etc/fstab
  fi

  echo ".host:/${SHARE_NAME} ${MOUNT_POINT} fuse.vmhgfs-fuse defaults,allow_other,uid=${OWNER_UID},gid=${OWNER_GID},umask=022 0 0" >> /etc/fstab
}

print_summary() {
  echo ""
  echo "============================================================="
  echo "  Compartilhamento VMware montado"
  echo "============================================================="
  echo "  Windows: D:\\migrations"
  echo "  VMware:  ${SHARE_NAME}"
  echo "  Linux:   ${MOUNT_POINT}"
  echo ""
  echo "  Teste:"
  echo "    ls -lah ${MOUNT_POINT}"
  echo ""
  echo "  Para subir o pacote MIS Core se ele estiver nessa pasta:"
  echo "    cd ${MOUNT_POINT}/pacote-vm-linux-dev"
  echo "    sudo bash bootstrap-linux.sh"
}

main() {
  require_root
  owner_uid_gid
  install_tools
  enable_allow_other
  check_share_available
  mount_share
  persist_mount
  ls -lah "$MOUNT_POINT" || true
  print_summary
}

main "$@"
