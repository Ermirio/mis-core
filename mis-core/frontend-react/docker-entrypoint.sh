#!/bin/sh
set -e

echo "🔄 Configurando variáveis de ambiente..."

# Criar arquivo de configuração JavaScript com variáveis de ambiente
cat > /usr/share/nginx/html/env-config.js << EOF
window.ENV = {
  VITE_DJANGO_API_URL: '${VITE_DJANGO_API_URL}',
  VITE_FLASK_API_URL: '${VITE_FLASK_API_URL}',
  VITE_FASTAPI_V2_URL: '${VITE_FASTAPI_V2_URL}'
};
EOF

echo "✅ Variáveis de ambiente configuradas!"
echo "🚀 Iniciando Nginx..."

exec "$@"
