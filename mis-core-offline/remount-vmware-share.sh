#!/usr/bin/env bash
# =============================================================================
# remount-vmware-share.sh - Remonta a pasta compartilhada VMware do Windows
#
# Use quando /mnt/windows-migrations sumiu, ficou vazio, travou, ou nao mostra
# a pasta pacote-vm-linux-dev corretamente.
#
# Antes, no VMware:
#   VM Settings -> Options -> Shared Folders -> Always enabled
#   Host path: D:\migrations
#   Name: migrations
#
# Uso:
#   sudo bash remount-vmware-share.sh
# =============================================================================

set -euo pipefail

SHARE_NAME="migrations"
MOUNT_POINT="/mnt/windows-migrations"
OWNER_USER="${SUDO_USER:-${USER:-root}}"
INSTALL_TOOLS=1

usage() {
  cat <<'EOF'
MIS Core - remontar VMware Shared Folder

Uso:
  sudo bash remount-vmware-share.sh [opcoes]

Opcoes:
  --share NOME       Nome do compartilhamento VMware (padrao: migrations)
  --mount DIR        Ponto de montagem Linux (padrao: /mnt/windows-migrations)
  --owner USER       Dono dos arquivos montados (padrao: usuario do sudo)
  --skip-install     Nao tenta instalar open-vm-tools/fuse
  -h, --help         Mostra esta ajuda

Exemplo:
  sudo bash remount-vmware-share.sh
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
    die "rode com sudo: sudo bash remount-vmware-share.sh"
  fi
}

resolve_owner() {
  if id "$OWNER_USER" >/dev/null 2>&1; then
    OWNER_UID="$(id -u "$OWNER_USER")"
    OWNER_GID="$(id -g "$OWNER_USER")"
  else
    OWNER_UID="0"
    OWNER_GID="0"
  fi
}

install_tools() {
  if [ "$INSTALL_TOOLS" -eq 0 ]; then
    return
  fi

  if command -v vmhgfs-fuse >/dev/null 2>&1 && command -v fusermount3 >/dev/null 2>&1; then
    return
  fi

  log "Instalando ferramentas VMware/FUSE, se faltarem"
  export DEBIAN_FRONTEND=noninteractive

  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y open-vm-tools fuse3 ca-certificates || apt-get install -y open-vm-tools fuse ca-certificates
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y open-vm-tools fuse3 fuse3-libs ca-certificates || dnf install -y open-vm-tools fuse ca-certificates
  else
    die "distro sem apt-get/dnf suportado. Instale open-vm-tools e fuse manualmente."
  fi
}

prepare_services() {
  modprobe fuse 2>/dev/null || true

  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now open-vm-tools.service 2>/dev/null || true
    systemctl restart open-vm-tools.service 2>/dev/null || true
    systemctl restart vmtoolsd.service 2>/dev/null || true
  fi

  if [ -f /etc/fuse.conf ]; then
    if grep -q '^#user_allow_other' /etc/fuse.conf; then
      sed -i 's/^#user_allow_other/user_allow_other/' /etc/fuse.conf
    elif ! grep -q '^user_allow_other' /etc/fuse.conf; then
      echo 'user_allow_other' >> /etc/fuse.conf
    fi
  fi
}

show_shares() {
  log "Compartilhamentos VMware visiveis"
  if command -v vmware-hgfsclient >/dev/null 2>&1; then
    shares="$(vmware-hgfsclient 2>/dev/null || true)"
    if [ -n "$shares" ]; then
      echo "$shares" | sed 's/^/  - /'
      if ! printf '%s\n' "$shares" | grep -qx "$SHARE_NAME"; then
        echo ""
        echo "Nao encontrei o share '${SHARE_NAME}'. No VMware confira:"
        echo "  Shared Folders: Always enabled"
        echo "  Host path: D:\\migrations"
        echo "  Name: ${SHARE_NAME}"
        die "share VMware nao visivel para o Linux"
      fi
      return
    fi
  fi

  echo "  Nao consegui listar shares; vou tentar montar direto."
}

force_unmount() {
  log "Limpando mount antigo em ${MOUNT_POINT}"
  mkdir -p "$MOUNT_POINT"

  if findmnt -rn "$MOUNT_POINT" >/dev/null 2>&1; then
    umount "$MOUNT_POINT" 2>/dev/null || true
    fusermount3 -u "$MOUNT_POINT" 2>/dev/null || true
    fusermount -u "$MOUNT_POINT" 2>/dev/null || true
    umount -lf "$MOUNT_POINT" 2>/dev/null || true
  fi

  pkill -f "vmhgfs-fuse.*${MOUNT_POINT}" 2>/dev/null || true
  sleep 1

  if findmnt -rn "$MOUNT_POINT" >/dev/null 2>&1; then
    die "nao consegui desmontar ${MOUNT_POINT}. Reinicie a VM ou confira processos usando a pasta."
  fi
}

mount_share() {
  log "Montando .host:/${SHARE_NAME} em ${MOUNT_POINT}"
  command -v vmhgfs-fuse >/dev/null 2>&1 || die "vmhgfs-fuse nao encontrado"

  vmhgfs-fuse ".host:/${SHARE_NAME}" "$MOUNT_POINT" \
    -o "allow_other,uid=${OWNER_UID},gid=${OWNER_GID},umask=022"

  findmnt "$MOUNT_POINT" >/dev/null 2>&1 || die "mount nao apareceu em findmnt"
}

validate_mount() {
  log "Validando conteudo montado"
  ls -lah "$MOUNT_POINT"

  if [ ! -d "${MOUNT_POINT}/pacote-vm-linux-dev" ]; then
    echo ""
    echo "A pasta ${MOUNT_POINT}/pacote-vm-linux-dev nao apareceu."
    echo "Confira no Windows se existe:"
    echo "  D:\\migrations\\pacote-vm-linux-dev"
    die "mount existe, mas o pacote nao esta visivel"
  fi

  echo ""
  echo "OK: mount restaurado."
  echo "Agora voce pode atualizar o OT com:"
  echo "  sudo bash ${MOUNT_POINT}/pacote-vm-linux-dev/update-ot.sh"
}

main() {
  require_root
  resolve_owner
  install_tools
  prepare_services
  show_shares
  force_unmount
  mount_share
  validate_mount
}

main "$@"
