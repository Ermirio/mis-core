#!/usr/bin/env bash
# =============================================================================
# export_images.sh - Builda e exporta imagens MIS Core para deploy offline OT
#
# Executar na maquina de desenvolvimento:
#   bash mis-core-offline/export_images.sh
#   MIS_VERSION=2026.05.09 bash mis-core-offline/export_images.sh
#
# Saida gerada dentro de mis-core-offline:
#   mis-core-images-<VERSION>.tar.gz
#   mis-core-images-<VERSION>.sha256
#   mis-core-images-<VERSION>.manifest.txt
# =============================================================================

set -euo pipefail

OFFLINE_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$OFFLINE_DIR/.." && pwd)"
cd "$ROOT_DIR"

GIT_HASH="$(git rev-parse --short HEAD 2>/dev/null || echo "no-git")"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
VERSION="${MIS_VERSION:-dev}"

export MIS_VERSION="$VERSION"
export MIS_GIT_HASH="$GIT_HASH"
export MIS_BUILD_TIME="$BUILD_TIME"

APP_IMAGES=(
  "mis-core-frontend:${VERSION}"
  "mis-core-django:${VERSION}"
  "mis-core-fastapi:${VERSION}"
  "mis-core-coletor:${VERSION}"
  "mis-core-nodered:${VERSION}"
)

INFRA_IMAGES=(
  "mysql:8.0"
  "influxdb:1.8-alpine"
  "chronograf:1.8"
  "grafana/grafana:10.4.2"
  "emqx/emqx:5.6.1"
  "portainer/portainer-ce:2.39.5-alpine"
)

ALL_IMAGES=("${APP_IMAGES[@]}" "${INFRA_IMAGES[@]}")
TARBALL="${OFFLINE_DIR}/mis-core-images-${VERSION}.tar"
TARBALL_GZ="${TARBALL}.gz"
SHA_FILE="${OFFLINE_DIR}/mis-core-images-${VERSION}.sha256"
MANIFEST_FILE="${OFFLINE_DIR}/mis-core-images-${VERSION}.manifest.txt"
OBSOLETE_OVERLAYS=(
  "${OFFLINE_DIR}/mis-core-django-${VERSION}.tar.gz"
  "${OFFLINE_DIR}/mis-core-django-${VERSION}.sha256"
  "${OFFLINE_DIR}/mis-core-nodered-${VERSION}.tar.gz"
  "${OFFLINE_DIR}/mis-core-nodered-${VERSION}.sha256"
)

echo "============================================================="
echo "  MIS Core - Build e Export Offline OT"
echo "  Version    : ${VERSION}"
echo "  Git hash   : ${GIT_HASH}"
echo "  Build time : ${BUILD_TIME}"
echo "============================================================="
echo ""

command -v docker >/dev/null 2>&1 || { echo "ERRO: docker nao encontrado."; exit 1; }

write_nodered_baseline_package() {
  cat > "$1" <<'JSON'
{
  "name": "node-red-project",
  "description": "MIS Core Node-RED - gerado por export_images.sh",
  "version": "0.0.1",
  "private": true,
  "dependencies": {
    "@aaqu/node-red-modbus-tcp": "~0.4.1",
    "@energyweb/node-red-contrib-green-proof-worker": "~2.5.1",
    "@flowfuse/node-red-dashboard": "~1.30.2",
    "industrialcomm": "~1.1.6",
    "node-red-contrib-cip-st-ethernet-ip": "~2.0.3",
    "node-red-contrib-consecutive-queue-gate": "~1.1.1",
    "node-red-contrib-cron-plus": "~2.2.4",
    "node-red-contrib-float": "~1.0.3",
    "node-red-contrib-influxdb": "~0.7.0",
    "node-red-contrib-modbus": "~5.45.2",
    "node-red-contrib-mssql": "~0.0.7",
    "node-red-contrib-omron-fins": "~0.5.0",
    "node-red-contrib-opcua": "~0.2.348",
    "node-red-contrib-originalpid": "~0.3.1",
    "node-red-contrib-pccc": "~1.0.2",
    "node-red-contrib-postgresql": "~0.15.4",
    "node-red-contrib-s7": "~3.1.1",
    "node-red-contrib-ui-led": "~0.4.11",
    "node-red-contrib-ui-level": "~0.1.46",
    "node-red-contrib-ui-navbar": "~1.0.11",
    "node-red-contrib-ui-state-trail": "~1.0.2",
    "node-red-dashboard": "~3.6.6",
    "node-red-mysql-r2": "~1.3.0",
    "node-red-node-mysql": "~3.0.0",
    "node-red-node-sqlite": "~1.1.1",
    "node-red-node-ui-table": "~0.4.5",
    "plcindustry": "~2.1.1"
  }
}
JSON
}

echo "[1/6] Buildando imagens da aplicacao..."
docker compose build frontend django fastapi coletor
echo ""

echo "[2/6] Sincronizando config Node-RED e buildando imagem custom..."
NR_SRC_SETTINGS="${ROOT_DIR}/node-red/settings.js"
NR_DST_DIR="${OFFLINE_DIR}/node-red"
NR_DST_SETTINGS="${NR_DST_DIR}/settings.js"
NR_DST_PACKAGE="${NR_DST_DIR}/package.json"

if [ ! -f "$NR_SRC_SETTINGS" ]; then
  echo "ERRO: settings.js fonte nao encontrado em ${NR_SRC_SETTINGS}"
  exit 1
fi

mkdir -p "$NR_DST_DIR"
cp "$NR_SRC_SETTINGS" "$NR_DST_SETTINGS"
echo "  OK settings.js copiado"

write_nodered_baseline_package "${NR_DST_PACKAGE}.baseline"

if docker exec mis-core-nodered cat /data/package.json > "${NR_DST_PACKAGE}.tmp" 2>/dev/null; then
  if command -v jq >/dev/null 2>&1; then
    jq -s '
      .[0] as $baseline |
      ($baseline.dependencies // {}) as $baseDeps |
      (.[1].dependencies // {}) as $devDeps |
      $baseline
      | .description = "MIS Core Node-RED - gerado por export_images.sh"
      | .dependencies = ($baseDeps + ($devDeps | with_entries(select($baseDeps[.key] == null))))
    ' "${NR_DST_PACKAGE}.baseline" "${NR_DST_PACKAGE}.tmp" > "$NR_DST_PACKAGE"
    rm -f "${NR_DST_PACKAGE}.tmp"
    deps="$(jq '.dependencies | length' "$NR_DST_PACKAGE" 2>/dev/null || echo "?")"
    echo "  OK package.json final (${deps} dependencia(s), baseline + extras DEV)"
  else
    cp "${NR_DST_PACKAGE}.baseline" "$NR_DST_PACKAGE"
    rm -f "${NR_DST_PACKAGE}.tmp"
    echo "  AVISO: jq nao encontrado; usando baseline industrial sem mesclar extras DEV."
  fi
else
  rm -f "${NR_DST_PACKAGE}.tmp"
  cp "${NR_DST_PACKAGE}.baseline" "$NR_DST_PACKAGE"
  echo "  AVISO: container mis-core-nodered nao esta rodando; usando baseline industrial."
fi
rm -f "${NR_DST_PACKAGE}.baseline"

docker build -t "mis-core-nodered:${VERSION}" "$NR_DST_DIR"
echo "  OK mis-core-nodered:${VERSION}"
echo ""

echo "[3/6] Verificando imagens de infraestrutura..."
for img in "${INFRA_IMAGES[@]}"; do
  if docker image inspect "$img" >/dev/null 2>&1; then
    echo "  OK $img"
  else
    echo "  Baixando $img..."
    docker pull "$img"
  fi
done
echo ""

echo "[4/6] Validando tags da aplicacao..."
missing=0
for img in "${APP_IMAGES[@]}"; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "  X $img nao encontrada"
    missing=$((missing + 1))
    continue
  fi
  label_version="$(docker image inspect "$img" --format '{{ index .Config.Labels "org.opencontainers.image.version" }}' 2>/dev/null || true)"
  if [ -n "$label_version" ] && [ "$label_version" != "$VERSION" ]; then
    echo "  X $img label=${label_version} esperado=${VERSION}"
    missing=$((missing + 1))
  else
    echo "  OK $img"
  fi
done
if [ "$missing" -gt 0 ]; then
  echo "ERRO: ${missing} imagem(ns) divergente(s). Abortando."
  exit 2
fi
echo ""

echo "[5/6] Salvando pacote em ${TARBALL_GZ}..."
rm -f "$TARBALL" "$TARBALL_GZ"
docker save "${ALL_IMAGES[@]}" -o "$TARBALL"
gzip -f "$TARBALL"
echo ""

echo "[6/6] Gerando checksum e manifesto..."
hash="$(sha256sum "$TARBALL_GZ" | awk '{print $1}')"
echo "${hash}  $(basename "$TARBALL_GZ")" > "$SHA_FILE"
{
  echo "MIS Core Offline Image Pack"
  echo "version=${VERSION}"
  echo "git_hash=${GIT_HASH}"
  echo "build_time=${BUILD_TIME}"
  echo "host_target=192.168.70.160:8080"
  echo ""
  echo "images:"
  for img in "${ALL_IMAGES[@]}"; do
    id="$(docker image inspect "$img" --format '{{.Id}}')"
    size="$(docker image inspect "$img" --format '{{.Size}}')"
    echo "- ${img} id=${id} size_bytes=${size}"
  done
} > "$MANIFEST_FILE"

# O pacote completo torna overlays incrementais anteriores obsoletos.
rm -f "${OBSOLETE_OVERLAYS[@]}"

size="$(du -h "$TARBALL_GZ" | cut -f1)"

echo ""
echo "============================================================="
echo "  PACOTE OFFLINE ATUALIZADO"
echo "============================================================="
echo "  ${TARBALL_GZ} (${size})"
echo "  ${SHA_FILE}"
echo "  ${MANIFEST_FILE}"
echo ""
echo "Copie a pasta mis-core-offline para o servidor OT e execute:"
echo "  bash import-images.sh"
