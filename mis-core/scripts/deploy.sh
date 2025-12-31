#!/bin/bash
# Script de deploy completo do MIS-Core

set -e

echo "🚀 MIS-Core - Deploy Automatizado"
echo "=================================="
echo ""

# Verificar se o arquivo .env existe
if [ ! -f ".env" ]; then
    echo "⚠️  Arquivo .env não encontrado!"
    echo "📝 Copiando .env.example para .env..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANTE: Edite o arquivo .env com suas configurações antes de continuar!"
    echo "   Pressione ENTER para continuar ou CTRL+C para cancelar..."
    read
fi

echo "✅ Arquivo .env encontrado"
echo ""

# Parar containers existentes
echo "🛑 Parando containers existentes..."
docker compose down -v 2>/dev/null || true
echo ""

# Build das imagens
echo "🔨 Construindo imagens Docker..."
docker compose build --no-cache
echo ""

# Iniciar serviços
echo "🚀 Iniciando serviços..."
docker compose up -d
echo ""

# Aguardar inicialização
echo "⏳ Aguardando inicialização dos serviços..."
echo ""

# Aguardar PostgreSQL
echo "  🔄 Aguardando PostgreSQL..."
until docker compose exec -T postgres pg_isready -U ${POSTGRES_USER:-mis_user} > /dev/null 2>&1; do
    sleep 2
done
echo "  ✅ PostgreSQL pronto!"

# Aguardar InfluxDB
echo "  🔄 Aguardando InfluxDB..."
until docker compose exec -T influxdb wget -q -O - http://localhost:8086/ping > /dev/null 2>&1; do
    sleep 2
done
echo "  ✅ InfluxDB pronto!"

# Aguardar Django
echo "  🔄 Aguardando Django..."
sleep 10
until curl -sf http://localhost:${DJANGO_PORT:-8000}/admin/ > /dev/null 2>&1; do
    sleep 2
done
echo "  ✅ Django pronto!"

# Aguardar Flask
echo "  🔄 Aguardando Flask..."
until curl -sf http://localhost:${FLASK_PORT:-5000}/api/health > /dev/null 2>&1; do
    sleep 2
done
echo "  ✅ Flask pronto!"

# Aguardar Frontend
echo "  🔄 Aguardando Frontend..."
until curl -sf http://localhost:${FRONTEND_PORT:-3000}/health > /dev/null 2>&1; do
    sleep 2
done
echo "  ✅ Frontend pronto!"

echo ""
echo "✅ Deploy concluído com sucesso!"
echo ""
echo "📊 Status dos serviços:"
docker compose ps
echo ""
echo "🌐 URLs de acesso:"
echo "   Frontend:     http://localhost:${FRONTEND_PORT:-3000}"
echo "   Django Admin: http://localhost:${DJANGO_PORT:-8000}/admin"
echo "   Flask API:    http://localhost:${FLASK_PORT:-5000}/api/health"
echo ""
echo "👤 Credenciais padrão:"
echo "   Usuário: ${DJANGO_SUPERUSER_USERNAME:-admin}"
echo "   Senha:   ${DJANGO_SUPERUSER_PASSWORD:-admin_password_2025}"
echo ""
echo "📝 Para ver os logs:"
echo "   docker compose logs -f"
echo ""
echo "🛑 Para parar o sistema:"
echo "   docker compose down"
echo ""
