#!/bin/bash
# =============================================================================
# import-images.sh — Importa imagens MIS Core em servidor sem internet (rede OT)
#
# Uso (no servidor OT):
#   bash import-images.sh
#
# O script espera encontrar, no mesmo diretório:
#   mis-core-images.tar.gz   ← arquivo gerado pelo export-images.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT_FILE="$SCRIPT_DIR/mis-core-images.tar.gz"

echo "============================================================="
echo "  MIS Core — Importação de Imagens (Ambiente Offline)"
echo "============================================================="
echo ""

# --- Verificações -----------------------------------------------------------
command -v docker >/dev/null 2>&1 || {
  echo "ERRO: docker não está instalado ou não está no PATH."
  echo "      Instale o Docker Engine antes de continuar."
  exit 1
}

if [ ! -f "$INPUT_FILE" ]; then
  echo "ERRO: Arquivo não encontrado: $INPUT_FILE"
  echo ""
  echo "  Certifique-se de que o arquivo mis-core-images.tar.gz"
  echo "  está no mesmo diretório deste script."
  exit 1
fi

FILE_SIZE=$(du -h "$INPUT_FILE" | cut -f1)
echo "  Arquivo : $INPUT_FILE"
echo "  Tamanho : $FILE_SIZE"
echo ""

# --- Importar ---------------------------------------------------------------
echo "[1/2] Carregando imagens no Docker..."
echo "      (aguarde — pode levar alguns minutos)"
echo ""

docker load -i "$INPUT_FILE"

echo ""

# --- Verificar resultado ----------------------------------------------------
echo "[2/2] Imagens disponíveis após importação:"
echo ""
docker images | grep -E "mis-core|mysql|influxdb|chronograf|grafana|node-red|emqx|portainer" || true

echo ""
echo "============================================================="
echo "  IMPORTAÇÃO CONCLUÍDA"
echo "============================================================="
echo ""
echo "  Próximos passos:"
echo "    1. Configure o arquivo .env  (cp .env.example .env && nano .env)"
echo "    2. Suba o stack:             docker compose up -d"
echo "    3. Verifique os containers:  docker compose ps"
echo "    4. Acesse o sistema:         http://<IP-DO-SERVIDOR>:8080"
echo ""
