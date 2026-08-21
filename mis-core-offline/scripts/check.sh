#!/bin/bash
# =============================================================================
# check.sh — smoke test do MIS Core offline
# =============================================================================
#
# Verifica em ordem:
#   1. Containers rodando + healthy
#   2. /version.json do frontend bate com MIS_VERSION do .env
#   3. /api/version/ do Django bate com MIS_VERSION
#   4. /api/health/ do Django responde 200
#   5. /api/v2/healthz do FastAPI responde 200
#   6. Le /etc/mis-version dentro de cada container versionado
# =============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
[ -f .env ] && { set -a; source .env; set +a; }

FRONTEND_HOST="${1:-${SERVER_HOST:-127.0.0.1}}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
DJANGO_PORT="${DJANGO_PORT:-8001}"
FASTAPI_PORT="${FASTAPI_PORT:-8002}"

PASS=0
FAIL=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "============================================================="
echo "  MIS Core — Smoke Test (versão esperada: ${MIS_VERSION:-?})"
echo "============================================================="
echo ""

# --- 1) containers ---------------------------------------------------------
echo "[1] Containers..."
CONTAINERS=(
  "frontend:mis-core-frontend"
  "django:mis-core-django"
  "fastapi:mis-core-fastapi"
  "coletor:mis-core-coletor"
  "mysql:mis-core-mysql"
  "influxdb:mis-core-influxdb"
  "chronograf:mis-core-chronograf"
  "grafana:mis-core-grafana"
  "node-red:mis-core-nodered"
  "emqx:mis-core-emqx"
  "portainer:mis-core-portainer"
)
for entry in "${CONTAINERS[@]}"; do
  svc="${entry%%:*}"
  container="${entry#*:}"
  state=$(docker inspect --format '{{.State.Status}}' "$container" 2>/dev/null || echo "missing")
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "$container" 2>/dev/null || echo "n/a")
  if [ "$state" = "running" ]; then
    ok "$svc → $state ($health)"
  else
    fail "$svc → $state"
  fi
done
echo ""

# --- 2) /version.json frontend ---------------------------------------------
echo "[2] Frontend /version.json..."
FE_VERSION=$(curl -fsS "http://${FRONTEND_HOST}:${FRONTEND_PORT}/version.json" 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || echo "")
if [ "$FE_VERSION" = "${MIS_VERSION:-}" ]; then
  ok "frontend version=$FE_VERSION (bate com .env)"
else
  fail "frontend version='$FE_VERSION' ≠ '${MIS_VERSION:-}' do .env"
fi
echo ""

# --- 3) /api/version/ django -----------------------------------------------
echo "[3] Django /api/version/..."
DJ_VERSION=$(curl -fsS "http://${FRONTEND_HOST}:${FRONTEND_PORT}/api/version/" 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || echo "")
if [ "$DJ_VERSION" = "${MIS_VERSION:-}" ]; then
  ok "django version=$DJ_VERSION"
else
  fail "django version='$DJ_VERSION' ≠ '${MIS_VERSION:-}'"
fi
echo ""

# --- 4-5) healths ----------------------------------------------------------
echo "[4-5] Endpoints de health..."
curl -fsS "http://${FRONTEND_HOST}:${FRONTEND_PORT}/api/health/" >/dev/null 2>&1 \
  && ok "django  /api/health/" || fail "django /api/health/"
curl -fsS "http://${FRONTEND_HOST}:${FRONTEND_PORT}/api/v2/healthz" >/dev/null 2>&1 \
  && ok "fastapi /api/v2/healthz" || fail "fastapi /api/v2/healthz"
echo ""

# --- 6) /etc/mis-version dentro dos containers -----------------------------
echo "[6] /etc/mis-version (dentro do container)..."
for svc in frontend django; do
  v=$(docker exec "mis-core-$svc" cat /etc/mis-version 2>/dev/null | grep '^version=' | cut -d'=' -f2 || echo "")
  if [ "$v" = "${MIS_VERSION:-}" ]; then
    ok "$svc /etc/mis-version=$v"
  else
    fail "$svc /etc/mis-version='$v' ≠ '${MIS_VERSION:-}'"
  fi
done
echo ""

# --- Resumo ----------------------------------------------------------------
echo "============================================================="
echo "  Resultado: $PASS passou · $FAIL falhou"
echo "============================================================="
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
