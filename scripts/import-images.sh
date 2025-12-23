#!/bin/bash
# Script para importar imagens Docker em ambiente offline

set -e

echo "🚀 MIS-Core - Importação de Imagens Docker (Deploy Offline)"
echo "============================================================"

# Arquivo de entrada
INPUT_FILE="./docker-images/mis-core-images.tar.gz"

if [ ! -f "$INPUT_FILE" ]; then
    echo "❌ Erro: Arquivo $INPUT_FILE não encontrado!"
    echo ""
    echo "Certifique-se de que o arquivo foi copiado para este diretório."
    exit 1
fi

echo ""
echo "📁 Arquivo encontrado: $INPUT_FILE"
echo "📊 Tamanho: $(du -h $INPUT_FILE | cut -f1)"
echo ""

# Descomprimir arquivo
echo "🗜️  Descomprimindo arquivo..."
gunzip -k -f "$INPUT_FILE"

# Importar imagens
INPUT_TAR="${INPUT_FILE%.gz}"
echo ""
echo "💾 Importando imagens Docker..."
echo ""

docker load -i "$INPUT_TAR"

echo ""
echo "✅ Importação concluída!"
echo ""
echo "📋 Imagens importadas:"
docker images | grep -E "mis-core|postgres|influxdb"
echo ""
echo "🚀 Para iniciar o sistema, execute:"
echo "   docker compose up -d"
echo ""
