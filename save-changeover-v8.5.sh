#!/bin/bash
# ============================================================
# save-changeover-v8.5.sh
# Funcionalidade:
#   - Detecção de primeira rodada do SKU na linha
#     (badge visual na tabela + modal de aviso ao operador)
#   - Campo primeira_rodada registrado em TrocaSKU com
#     usuario, linha e data_hora para rastreabilidade
#
# Gera: dist/deploy/mis-changeover-v8.5.tar
# Imagens: mis-frontend:v8.5  mis-backend:v8.5
# ============================================================
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_DIR="$ROOT_DIR/mis-change-over"
OUTDIR="$ROOT_DIR/dist/deploy"
OUTFILE="$OUTDIR/mis-changeover-v8.5.tar"

mkdir -p "$OUTDIR"

echo "================================================="
echo " MIS Changeover v8.5 — Build & Save"
echo "================================================="

# ── Build ─────────────────────────────────────────────────
echo ""
echo " [1/3] Building images via docker-compose-build.yml ..."
docker compose -f "$COMPOSE_DIR/docker-compose-build.yml" build --no-cache

echo ""
echo " [OK] mis-frontend:v8.5"
echo " [OK] mis-backend:v8.5"

# ── Save ──────────────────────────────────────────────────
echo ""
echo " [2/3] Salvando em $OUTFILE ..."
docker save mis-frontend:v8.5 mis-backend:v8.5 -o "$OUTFILE"

SIZE=$(du -sh "$OUTFILE" | cut -f1)

echo ""
echo " [3/3] Verificando tar..."
docker image inspect mis-frontend:v8.5 --format "  frontend: {{.RepoTags}} {{.Size}} bytes" 2>/dev/null || true
docker image inspect mis-backend:v8.5  --format "  backend:  {{.RepoTags}} {{.Size}} bytes" 2>/dev/null || true

echo ""
echo "================================================="
echo " CONCLUIDO!"
echo " Arquivo: $OUTFILE ($SIZE)"
echo ""
echo " ── PROCEDIMENTO DE DEPLOY NO SERVIDOR OT ──"
echo ""
echo " 1. Copiar para o servidor OT:"
echo "    Os arquivos abaixo devem estar juntos na mesma pasta:"
echo "      mis-changeover-v8.5.tar"
echo "      Docker-Compose.yaml  (versao atualizada para v8.5)"
echo ""
echo " 2. No servidor OT — carregar imagens:"
echo "    docker load -i mis-changeover-v8.5.tar"
echo ""
echo " 3. Subir os containers:"
echo "    docker compose -f Docker-Compose.yaml up -d"
echo ""
echo " 4. Aplicar migration do banco (primeira vez em v8.5):"
echo "    docker exec mis_backend_container python manage.py migrate"
echo ""
echo " 5. Verificar:"
echo "    Frontend: http://localhost:3005"
echo "    Backend:  http://localhost:8000"
echo ""
echo "================================================="
