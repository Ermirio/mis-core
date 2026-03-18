#!/bin/bash
# ============================================================
# save-changeover-timeout-v3.5.sh
# Fix: timeout Gunicorn 120s → 300s (evita 504 na troca de SKU
#      com múltiplos CLPs/tags)
#
# Gera:  dist/mis-core-changeover-timeout-v3.5.tar
# Imagem: mis-core-changeover-backend:3.5
# ============================================================
set -e

OUTDIR="dist"
OUTFILE="$OUTDIR/mis-core-changeover-timeout-v3.5.tar"

mkdir -p "$OUTDIR"

echo "================================================="
echo " SAVE → $OUTFILE"
echo "================================================="
docker save mis-core-changeover-backend:3.5 -o "$OUTFILE"

SIZE=$(du -sh "$OUTFILE" | cut -f1)
echo ""
echo "================================================="
echo " CONCLUIDO! ($SIZE)"
echo ""
echo " Transferir para o servidor offline:"
echo "   scp $OUTFILE usuario@servidor:/caminho/"
echo ""
echo " Copiar também (arquivos de configuração):"
echo "   - docker-compose.yml              (tag atualizada para 3.5)"
echo "   - proxy-reverse/nginx.conf        (proxy_read_timeout 300s)"
echo ""
echo " No servidor offline — carregar e subir:"
echo "   docker load -i mis-core-changeover-timeout-v3.5.tar"
echo "   docker compose up -d --force-recreate mis-changeover-backend"
echo "================================================="
