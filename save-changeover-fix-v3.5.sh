#!/bin/bash
# ============================================================
# save-changeover-fix-v3.5.sh
# Fix: prefixo duplo no histórico de SKU (mis-change-over)
#      + nginx.conf agora ajustável via volume mount
#
# Gera:  dist/mis-core-changeover-fix-v3.5.tar
# Imagens: mis-core-proxy:v3.5
#          mis-core-changeover-frontend:v3.5
# ============================================================
set -e

OUTDIR="dist"
OUTFILE="$OUTDIR/mis-core-changeover-fix-v3.5.tar"

mkdir -p "$OUTDIR"

echo "================================================="
echo " BUILD: nginx-proxy → v3.5"
echo " (nginx.conf baked + volume mount habilitado)"
echo "================================================="
docker compose build nginx-proxy

echo ""
echo "================================================="
echo " BUILD: mis-changeover-frontend → v3.5"
echo " (fix: REACT_APP_HISTORICO_TROCAS_ENDPOINT corrigido)"
echo "================================================="
docker compose build mis-changeover-frontend

echo ""
echo "================================================="
echo " SAVE → $OUTFILE"
echo "================================================="
docker save mis-core-proxy:v3.5 mis-core-changeover-frontend:v3.5 -o "$OUTFILE"

SIZE=$(du -sh "$OUTFILE" | cut -f1)
echo ""
echo "================================================="
echo " CONCLUIDO! ($SIZE)"
echo ""
echo " Transferir para o servidor offline:"
echo "   scp $OUTFILE usuario@servidor:/caminho/"
echo ""
echo " Copiar também (arquivos de configuração):"
echo "   - docker-compose.yml              (tags atualizadas para v3.5)"
echo "   - proxy-reverse/nginx.conf        (OBRIGATÓRIO — volume mount ativo)"
echo ""
echo " No servidor offline — carregar e subir:"
echo "   docker load -i mis-core-changeover-fix-v3.5.tar"
echo "   docker compose up -d --force-recreate nginx-proxy mis-changeover-frontend"
echo "================================================="
