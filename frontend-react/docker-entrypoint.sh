#!/bin/sh
set -e

# =============================================================================
# docker-entrypoint.sh — frontend MIS Core
#
# 1) Gera /env-config.js com as URLs de API resolvidas em runtime.
#    Permite a MESMA imagem rodar em standalone, atrás do hub proxy, ou
#    em rede OT — basta o compose definir VITE_*_URL diferente.
#
# 2) Gera /version.json com a versão da imagem (gravada via build args).
#    Acessível em http://<host>/version.json e
#    http://<host>/mis-core/version.json — usado para detectar visualmente
#    qual imagem está rodando, eliminando o bug de "rodei v2 mas vejo v1".
# =============================================================================

echo "[entrypoint] Configurando variáveis de ambiente em runtime..."

cat > /usr/share/nginx/html/env-config.js <<EOF
window.ENV = {
  VITE_DJANGO_API_URL: '${VITE_DJANGO_API_URL:-/api}',
  VITE_FLASK_API_URL: '${VITE_FLASK_API_URL:-/api}',
  VITE_FASTAPI_V2_URL: '${VITE_FASTAPI_V2_URL:-/api/v2}',
  MIS_MODE: '${MIS_MODE:-production}'
};
EOF

# version.json — fonte canônica da versão do servidor
# As três variáveis vêm do Dockerfile via ARG/ENV.
APP_VERSION_VAL="${MIS_VERSION:-${APP_VERSION:-0.0.0-runtime}}"
GIT_HASH_VAL="${MIS_GIT_HASH:-${GIT_HASH:-no-git}}"
BUILD_TIME_VAL="${MIS_BUILD_TIME:-${BUILD_TIME:-unknown}}"
SERVED_AT_VAL="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat > /usr/share/nginx/html/version.json <<EOF
{
  "service": "mis-core-frontend",
  "version": "${APP_VERSION_VAL}",
  "git_hash": "${GIT_HASH_VAL}",
  "build_time": "${BUILD_TIME_VAL}",
  "served_at": "${SERVED_AT_VAL}"
}
EOF

echo "[entrypoint] env-config.js e version.json gerados."
echo "[entrypoint]   versão : ${APP_VERSION_VAL}"
echo "[entrypoint]   git    : ${GIT_HASH_VAL}"
echo "[entrypoint]   built  : ${BUILD_TIME_VAL}"
echo "[entrypoint] Iniciando Nginx..."

exec "$@"
