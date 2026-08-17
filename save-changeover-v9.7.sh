#!/bin/bash
# ============================================================
# save-changeover-v9.7.sh
# Funcionalidades v9.7 (incrementais sobre v9.6):
#   - Poka Yoke na tela de Troca Automática:
#       · Filtro por Ordem de Produção (OP) apenas
#       · SKU oculto na lista — aparece só no modal de confirmação
#       · Coluna DUN14 removida da lista
#   - Bypass de validação para grupo Engenheiro:
#       · Engenheiro pode aprovar qualidade sem SAP liberado
#       · Badge "Bypass Engenheiro" sinaliza o bypass no card
#       · Backend aceita Qualidade OU Engenheiro na aprovação
#
# Gera: dist/deploy/mis-changeover-v9.7.tar
# Imagens: mis-frontend:v9.7  mis-backend:v9.7
# ============================================================
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_DIR="$ROOT_DIR/mis-change-over"
OUTDIR="$ROOT_DIR/dist/deploy"
OUTFILE="$OUTDIR/mis-changeover-v9.7.tar"

mkdir -p "$OUTDIR"

echo "================================================="
echo " MIS Changeover v9.7 — Build & Save"
echo "================================================="

echo ""
echo " [1/4] Build mis-backend:v9.7 ..."
docker build -t mis-backend:v9.7 "$COMPOSE_DIR/Backend"
echo " [OK] mis-backend:v9.7"

echo ""
echo " [2/4] Build mis-frontend:v9.7 ..."
docker build -t mis-frontend:v9.7 "$COMPOSE_DIR/Frontend"
echo " [OK] mis-frontend:v9.7"

echo ""
echo " [3/4] Salvando em $OUTFILE ..."
docker save mis-frontend:v9.7 mis-backend:v9.7 -o "$OUTFILE"

SIZE=$(du -sh "$OUTFILE" | cut -f1)

echo ""
echo " [4/4] Verificando imagens..."
docker image inspect mis-frontend:v9.7 --format "  frontend: {{.RepoTags}} — {{.Size}} bytes" 2>/dev/null || true
docker image inspect mis-backend:v9.7  --format "  backend:  {{.RepoTags}} — {{.Size}} bytes" 2>/dev/null || true

echo ""
echo "================================================="
echo " CONCLUÍDO!"
echo " Arquivo: $OUTFILE ($SIZE)"
echo ""
echo " ── PROCEDIMENTO DE DEPLOY NO SERVIDOR OT ──"
echo ""
echo " 1. Copiar para o servidor OT:"
echo "    scp $OUTFILE usuario@servidor-ot:~/Documents/dist/"
echo ""
echo " 2. No servidor OT:"
echo "    docker load -i mis-changeover-v9.7.tar"
echo "    sed -i 's/mis-backend:v9\.6/mis-backend:v9.7/g; s/mis-frontend:v9\.6/mis-frontend:v9.7/g' docker-compose.yml"
echo "    sudo docker compose up -d --no-deps mis-changeover-backend mis-changeover-frontend"
echo ""
echo " 3. Criar grupo Engenheiro no Django Admin (se ainda não existir):"
echo "    http://<servidor>:5006/admin/ → Grupos → Adicionar 'Engenheiro'"
echo "    Adicionar usuários engenheiros ao grupo"
echo ""
echo " 4. Rollback para v9.6 se necessário:"
echo "    sed -i 's/mis-backend:v9\.7/mis-backend:v9.6/g; s/mis-frontend:v9\.7/mis-frontend:v9.6/g' docker-compose.yml"
echo "    sudo docker compose up -d --no-deps mis-changeover-backend mis-changeover-frontend"
echo ""
echo "================================================="
