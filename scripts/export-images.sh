#!/bin/bash
# Script para exportar todas as imagens Docker para deploy offline

set -e

echo "🚀 MIS-Core - Exportação de Imagens Docker para Deploy Offline"
echo "=============================================================="

# Diretório de saída
OUTPUT_DIR="./docker-images"
mkdir -p "$OUTPUT_DIR"

# Arquivo de saída
OUTPUT_FILE="$OUTPUT_DIR/mis-core-images.tar"

echo ""
echo "📦 Construindo imagens Docker..."
echo ""

# Build das imagens
docker compose build --no-cache

echo ""
echo "📋 Listando imagens construídas..."
echo ""

# Listar imagens do projeto
docker images | grep "mis-core"

echo ""
echo "💾 Exportando imagens para arquivo tar..."
echo ""

# Exportar imagens
docker save \
  mis-core-django:latest \
  mis-core-flask:latest \
  mis-core-frontend:latest \
  postgres:15-alpine \
  influxdb:1.8-alpine \
  -o "$OUTPUT_FILE"

# Comprimir arquivo
echo ""
echo "🗜️  Comprimindo arquivo..."
gzip -f "$OUTPUT_FILE"

# Informações do arquivo
FILE_SIZE=$(du -h "$OUTPUT_FILE.gz" | cut -f1)

echo ""
echo "✅ Exportação concluída!"
echo ""
echo "📁 Arquivo gerado: $OUTPUT_FILE.gz"
echo "📊 Tamanho: $FILE_SIZE"
echo ""
echo "📝 Para importar em outro ambiente, execute:"
echo "   ./scripts/import-images.sh"
echo ""
