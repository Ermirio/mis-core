#!/bin/bash
# =============================================================================
# install.sh — instala MIS Core no servidor OT (offline)
# =============================================================================
#
# Espera encontrar no diretório-pai:
#   mis-core-images-<VERSION>.tar.gz
#   mis-core-images-<VERSION>.sha256
#   .env  (já preenchido — copiado de .env.example)
#
# O que faz:
#   1. Verifica integridade do tarball (sha256)
#   2. Importa as imagens via `docker load`
#   3. Lista o que entrou e CONFRONTA com MIS_VERSION do .env
#   4. Aborta se houver mismatch (evita o bug histórico)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "============================================================="
echo "  MIS Core — Install Offline"
echo "============================================================="
echo ""

# --- Pré-condições ---------------------------------------------------------
command -v docker >/dev/null 2>&1 || {
  echo "ERRO: docker não está instalado." >&2
  exit 1
}

if [ ! -f .env ]; then
  echo "ERRO: arquivo .env não encontrado em $ROOT_DIR" >&2
  echo "      Copie e preencha:  cp .env.example .env && nano .env" >&2
  exit 1
fi

bash "$SCRIPT_DIR/ensure-portainer-password.sh" .env

# Carrega o MIS_VERSION
set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "${MIS_VERSION:-}" ]; then
  echo "ERRO: MIS_VERSION não definido no .env" >&2
  exit 1
fi

# Procura o tarball
TARBALL_GZ="$(ls -1 mis-core-images-*.tar.gz 2>/dev/null | head -n1 || true)"
if [ -z "$TARBALL_GZ" ]; then
  echo "ERRO: nenhum mis-core-images-*.tar.gz encontrado em $ROOT_DIR" >&2
  echo "      Copie do pendrive antes de rodar este script." >&2
  exit 1
fi

echo "  Tarball  : $TARBALL_GZ"
echo "  Versão   : $MIS_VERSION"
echo ""

# --- Verifica SHA256 -------------------------------------------------------
SHA_FILE="${TARBALL_GZ%.tar.gz}.sha256"
if [ -f "$SHA_FILE" ]; then
  echo "[1/4] Verificando integridade (sha256)..."
  if sha256sum -c "$SHA_FILE" >/dev/null 2>&1; then
    echo "  ✓ checksum válido"
  else
    echo "  ✗ checksum INVÁLIDO — arquivo corrompido. Abortando." >&2
    exit 2
  fi
else
  echo "[1/4] Aviso: $SHA_FILE não encontrado — pulando verificação de integridade."
fi
echo ""

# --- Carrega imagens -------------------------------------------------------
echo "[2/4] docker load (pode levar minutos)..."
docker load -i "$TARBALL_GZ"
echo ""

# --- Confronto entre tag carregada e MIS_VERSION do .env ------------------
echo "[3/4] Confrontando tags carregadas com MIS_VERSION=${MIS_VERSION}..."
EXPECTED_IMAGES=(
  "mis-core-django:${MIS_VERSION}"
  "mis-core-fastapi:${MIS_VERSION}"
  "mis-core-frontend:${MIS_VERSION}"
  "mis-core-coletor:${MIS_VERSION}"
  "mis-core-nodered:${MIS_VERSION}"
  "mysql:8.0"
  "influxdb:1.8-alpine"
  "chronograf:1.8"
  "grafana/grafana:10.4.2"
  "emqx/emqx:5.6.1"
  "portainer/portainer-ce:2.39.5-alpine"
)
MISSING=0
for img in "${EXPECTED_IMAGES[@]}"; do
  if docker image inspect "$img" >/dev/null 2>&1; then
    CREATED="$(docker image inspect "$img" --format '{{ index .Config.Labels "org.opencontainers.image.created" }}' 2>/dev/null || echo "")"
    VERSION_LABEL="$(docker image inspect "$img" --format '{{ index .Config.Labels "org.opencontainers.image.version" }}' 2>/dev/null || echo "")"
    if [ "$VERSION_LABEL" = "$MIS_VERSION" ]; then
      echo "  ✓ $img    (built $CREATED)"
    else
      echo "  ✗ $img    label.version='$VERSION_LABEL' ≠ esperado '$MIS_VERSION'"
      MISSING=$((MISSING+1))
    fi
  else
    echo "  ✗ $img    NÃO encontrada após docker load"
    MISSING=$((MISSING+1))
  fi
done
if [ "$MISSING" -gt 0 ]; then
  echo "" >&2
  echo "ERRO: $MISSING imagem(ns) divergente(s)." >&2
  echo "      Verifique se o tarball foi gerado com MIS_VERSION=$MIS_VERSION" >&2
  exit 3
fi
echo ""

# --- Pronto para subir ----------------------------------------------------
echo "[4/4] Imagens prontas. Próximos passos:"
echo ""
echo "  docker compose up -d"
echo "  docker compose ps"
echo "  bash scripts/check.sh        # smoke test"
echo ""
echo "Acessar:"
echo "  Frontend  http://<IP>:${FRONTEND_PORT:-8080}/mis-core/"
echo "  Admin     http://<IP>:${FRONTEND_PORT:-8080}/mis-core-admin/"
echo "  Versão    curl http://<IP>:${FRONTEND_PORT:-8080}/version.json"
echo ""
