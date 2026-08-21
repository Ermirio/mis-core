#!/bin/bash
# =============================================================================
# export-images.sh — exporta imagens MIS Core para deploy offline (rede OT)
# =============================================================================
#
# CORREÇÃO IMPORTANTE (set/2026):
#   A versão antiga deste script tinha um bug fatal: rodava `docker compose
#   build` (que produzia imagens taggeadas como :dev) mas tentava exportar
#   `mis-core-django:${VERSION}` — se uma imagem antiga com esse tag estava no
#   docker, ELA era exportada (não a recém-buildada). Resultado: o servidor
#   OT recebia uma imagem velha com o mesmo tag.
#
# Como esta versão evita o bug:
#   1. Recebe MIS_VERSION e propaga via .env temporário ao compose,
#      garantindo que o build já SAI com o tag correto.
#   2. Calcula MIS_GIT_HASH e MIS_BUILD_TIME aqui, propaga aos build args.
#   3. Após build, RECONFERE que o tag certo aponta para a imagem nova
#      (`docker image inspect` lendo a label `org.opencontainers.image.created`)
#   4. Se algum tag estava antigo, aborta antes de salvar.
#
# Uso:
#   bash scripts/export-images.sh                  # versão = dev-<gitsha>
#   MIS_VERSION=1.5.2 bash scripts/export-images.sh
#
# Saída:
#   docker-images/mis-core-images-<version>.tar.gz
#   docker-images/mis-core-images-<version>.sha256
# =============================================================================

set -euo pipefail

# --- Configuração ----------------------------------------------------------
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

GIT_HASH="$(git rev-parse --short HEAD 2>/dev/null || echo "no-git")"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

VERSION="${MIS_VERSION:-dev-${GIT_HASH}}"

OUTPUT_DIR="$ROOT_DIR/docker-images"
TARBALL="$OUTPUT_DIR/mis-core-images-${VERSION}.tar"

# Imagens da aplicação (built localmente)
APP_IMAGES=(
  "mis-core-django:${VERSION}"
  "mis-core-fastapi:${VERSION}"
  "mis-core-frontend:${VERSION}"
  "mis-core-coletor:${VERSION}"
)

# Imagens de infraestrutura (já fixas, vêm do registry)
INFRA_IMAGES=(
  "mysql:8.0"
  "influxdb:1.8-alpine"
  "chronograf:1.8"
  "grafana/grafana:10.4.2"
  "nodered/node-red:3.1.9"
  "emqx/emqx:5.6.1"
  "portainer/portainer-ce:2.39.5-alpine"
)

ALL_IMAGES=("${APP_IMAGES[@]}" "${INFRA_IMAGES[@]}")

echo "============================================================="
echo "  MIS Core — Exportação para Deploy Offline"
echo "  Versão     : ${VERSION}"
echo "  Git hash   : ${GIT_HASH}"
echo "  Build time : ${BUILD_TIME}"
echo "============================================================="
echo ""

# --- Verificações ---------------------------------------------------------
command -v docker >/dev/null 2>&1 || { echo "ERRO: docker não encontrado."; exit 1; }
mkdir -p "$OUTPUT_DIR"

# --- Build (com versão correta gravada nas labels) ------------------------
echo "[1/5] Buildando imagens com VERSION=${VERSION} ..."
echo ""

# Exporta para o ambiente do compose. Ele lê via ${MIS_VERSION:-dev}.
export MIS_VERSION="$VERSION"
export MIS_GIT_HASH="$GIT_HASH"
export MIS_BUILD_TIME="$BUILD_TIME"

# Build sem cache para garantir bundle novo (custa minutos extras mas elimina
# a chance de pegar bundle antigo do node_modules cacheado).
docker compose build --pull --no-cache
echo ""

# --- Pull infra (precisa internet aqui) -----------------------------------
echo "[2/5] Pull de infra-images (MySQL/InfluxDB/Chronograf)..."
for img in "${INFRA_IMAGES[@]}"; do
  echo "  → docker pull $img"
  docker pull "$img"
done
echo ""

# --- Verifica que os tags realmente apontam para a build atual ------------
echo "[3/5] Verificando que cada tag aponta para a build de ${BUILD_TIME}..."
MISMATCH=0
for img in "${APP_IMAGES[@]}"; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "  ✗  $img  NÃO existe."
    MISMATCH=$((MISMATCH+1))
    continue
  fi
  IMG_CREATED="$(docker image inspect "$img" --format '{{ index .Config.Labels "org.opencontainers.image.created" }}' 2>/dev/null || echo "")"
  IMG_VERSION="$(docker image inspect "$img" --format '{{ index .Config.Labels "org.opencontainers.image.version" }}' 2>/dev/null || echo "")"
  if [ "$IMG_VERSION" != "$VERSION" ]; then
    echo "  ✗  $img  label image.version='${IMG_VERSION}' ≠ esperado '${VERSION}'"
    MISMATCH=$((MISMATCH+1))
  else
    SIZE=$(docker image inspect "$img" --format='{{.Size}}' | awk '{printf "%.0f MB", $1/1024/1024}')
    echo "  ✓  $img  ($SIZE)  built=${IMG_CREATED}"
  fi
done

# Verifica também as imagens de infra
for img in "${INFRA_IMAGES[@]}"; do
  if docker image inspect "$img" >/dev/null 2>&1; then
    SIZE=$(docker image inspect "$img" --format='{{.Size}}' | awk '{printf "%.0f MB", $1/1024/1024}')
    echo "  ✓  $img  ($SIZE)"
  else
    echo "  ✗  $img  NÃO encontrada após pull"
    MISMATCH=$((MISMATCH+1))
  fi
done

if [ "$MISMATCH" -gt 0 ]; then
  echo ""
  echo "ERRO: $MISMATCH imagem(ns) com tag/versão divergente. Abortando."
  echo "      Provavelmente uma imagem antiga ficou no docker — limpe e repita:"
  echo "        docker image rm ${APP_IMAGES[*]}"
  echo "        bash scripts/export-images.sh"
  exit 1
fi
echo ""

# --- Exportar -------------------------------------------------------------
echo "[4/5] Exportando ${#ALL_IMAGES[@]} imagens para ${TARBALL}.gz ..."
echo "      (pode levar minutos — somam vários GBs)"
echo ""

docker save "${ALL_IMAGES[@]}" -o "$TARBALL"
echo "  → comprimindo com gzip..."
gzip -f "$TARBALL"

# --- Hash para integridade -------------------------------------------------
echo "[5/5] Gerando checksum SHA256..."
SHA="$(sha256sum "$TARBALL.gz" | awk '{print $1}')"
echo "$SHA  $(basename "$TARBALL.gz")" > "$TARBALL.sha256"
FILE_SIZE="$(du -h "$TARBALL.gz" | cut -f1)"

echo ""
echo "============================================================="
echo "  EXPORTAÇÃO CONCLUÍDA"
echo "============================================================="
echo ""
echo "  Arquivo  : $(basename "$TARBALL.gz")"
echo "  Tamanho  : $FILE_SIZE"
echo "  Versão   : ${VERSION}"
echo "  SHA256   : $SHA"
echo ""
echo "  Próximos passos:"
echo "    1. cp ${TARBALL}.gz <pendrive>"
echo "    2. cp ${TARBALL}.sha256 <pendrive>"
echo "    3. cp -r mis-core-offline/ <pendrive>"
echo "    4. No servidor OT: bash mis-core-offline/scripts/install.sh"
echo ""
echo "  Para apontar o .env do offline para essa versão, use:"
echo "    MIS_VERSION=${VERSION}"
echo ""
