#!/bin/bash

# Script para reconstruir os containers do MIS-Energy com as novas alterações
# Autor: Manus AI
# Data: 03/01/2026

set -e  # Parar em caso de erro

echo "======================================"
echo "REBUILD MIS-ENERGY CONTAINERS"
echo "======================================"
echo ""

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar se está no diretório correto
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Erro: docker-compose.yml não encontrado!${NC}"
    echo "Execute este script a partir do diretório raiz do projeto (mis-core)"
    exit 1
fi

# Verificar se está no branch correto
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "mis-hub" ]; then
    echo -e "${YELLOW}⚠️  Aviso: Você está no branch '$CURRENT_BRANCH', não 'mis-hub'${NC}"
    read -p "Deseja continuar mesmo assim? (s/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        exit 1
    fi
fi

# Mostrar último commit
echo -e "${GREEN}📝 Último commit:${NC}"
git log -1 --oneline
echo ""

# Passo 1: Parar containers do MIS-Energy
echo -e "${YELLOW}🛑 Passo 1: Parando containers do MIS-Energy...${NC}"
docker-compose stop mis-energy-backend mis-energy-frontend mis-energy-collector
echo -e "${GREEN}✅ Containers parados${NC}"
echo ""

# Passo 2: Remover containers antigos
echo -e "${YELLOW}🗑️  Passo 2: Removendo containers antigos...${NC}"
docker-compose rm -f mis-energy-backend mis-energy-frontend mis-energy-collector
echo -e "${GREEN}✅ Containers removidos${NC}"
echo ""

# Passo 3: Remover imagens antigas (forçar rebuild)
echo -e "${YELLOW}🧹 Passo 3: Removendo imagens antigas...${NC}"
docker rmi -f mis-core-mis-energy-backend:latest 2>/dev/null || true
docker rmi -f mis-core-mis-energy-frontend:latest 2>/dev/null || true
docker rmi -f mis-core-mis-energy-collector:latest 2>/dev/null || true
echo -e "${GREEN}✅ Imagens antigas removidas${NC}"
echo ""

# Passo 4: Limpar cache do Docker (opcional mas recomendado)
echo -e "${YELLOW}🧹 Passo 4: Limpando cache do Docker...${NC}"
docker builder prune -f
echo -e "${GREEN}✅ Cache limpo${NC}"
echo ""

# Passo 5: Reconstruir imagens SEM CACHE
echo -e "${YELLOW}🔨 Passo 5: Reconstruindo imagens (sem cache)...${NC}"
echo "Isso pode levar alguns minutos..."
docker-compose build --no-cache mis-energy-backend mis-energy-frontend mis-energy-collector
echo -e "${GREEN}✅ Imagens reconstruídas${NC}"
echo ""

# Passo 6: Iniciar containers
echo -e "${YELLOW}🚀 Passo 6: Iniciando containers...${NC}"
docker-compose up -d mis-energy-backend mis-energy-frontend mis-energy-collector
echo -e "${GREEN}✅ Containers iniciados${NC}"
echo ""

# Passo 7: Aguardar containers ficarem saudáveis
echo -e "${YELLOW}⏳ Passo 7: Aguardando containers ficarem prontos...${NC}"
sleep 10

# Verificar status dos containers
echo -e "${GREEN}📊 Status dos containers:${NC}"
docker-compose ps mis-energy-backend mis-energy-frontend mis-energy-collector
echo ""

# Passo 8: Verificar logs para erros
echo -e "${YELLOW}📋 Passo 8: Verificando logs recentes...${NC}"
echo ""
echo "--- Backend ---"
docker-compose logs --tail=20 mis-energy-backend | grep -i "error\|warning\|started" || echo "Sem erros aparentes"
echo ""
echo "--- Frontend ---"
docker-compose logs --tail=20 mis-energy-frontend | grep -i "error\|warning\|ready" || echo "Sem erros aparentes"
echo ""

# Resumo final
echo ""
echo "======================================"
echo -e "${GREEN}✅ REBUILD CONCLUÍDO COM SUCESSO!${NC}"
echo "======================================"
echo ""
echo "📌 Próximos passos:"
echo "1. Acesse a aplicação em: http://localhost:3000/mis-energy"
echo "2. Faça um hard refresh no navegador (Ctrl+Shift+R ou Cmd+Shift+R)"
echo "3. Verifique se as novas funcionalidades estão visíveis:"
echo "   - Cards de equipamentos com métricas financeiras"
echo "   - Métricas corretas por tipo de medidor (energia vs produção)"
echo "   - Dashboard com dados reais do InfluxDB"
echo ""
echo "🔍 Para ver logs em tempo real:"
echo "   docker-compose logs -f mis-energy-backend"
echo "   docker-compose logs -f mis-energy-frontend"
echo ""
echo "🐛 Se ainda houver problemas:"
echo "   1. Verifique se o InfluxDB tem dados: docker-compose exec influxdb influx -execute 'SHOW DATABASES'"
echo "   2. Verifique se o MySQL está acessível: docker-compose exec mysql mysql -uroot -p -e 'SHOW DATABASES'"
echo "   3. Reinicie todo o stack: docker-compose restart"
echo ""
