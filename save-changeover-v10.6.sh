#!/bin/bash
# ============================================================
# save-changeover-v10.6.sh
# Patch incremental v10.5 -> v10.6.
#
# O que muda:
#   * Recipe Monitor (mis-recipe-intelligent:v10.6):
#       - Filtro Change-of-Value: so registra ponto no grafico quando o
#         valor REALMENTE muda. Elimina pontos redundantes de
#         reenvio/keep-alive/reconexao do servidor OPC.
#       - Deadband REAL configuravel via RECIPE_MONITOR_COV_DEADBAND_REAL
#         (default 0.0 = so filtra valores exatamente iguais).
#
#   * Backend e Frontend: NAO mudam (continuam v10.5 — reusados).
#
# Saidas:
#   mis-changeover-v10.6.tar   (3 imagens: backend v10.5 retag + recipe v10.6 + frontend v10.5 retag)
#   carregar-v10.6.sh
# ============================================================
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANGEOVER_DIR="$ROOT_DIR/mis-change-over"
RECIPE_DIR="$CHANGEOVER_DIR/Backend/recipe_monitor_service"
OUTDIR="$ROOT_DIR/dist/deploy"
TAR_FILE="$OUTDIR/mis-changeover-v10.6.tar"
LOAD_SCRIPT="$OUTDIR/carregar-v10.6.sh"

mkdir -p "$OUTDIR"

echo "================================================="
echo " MIS Changeover v10.6 - Patch (Change-of-Value no Recipe Monitor)"
echo "================================================="

# v10.6 muda os TRES: backend (gestao usuarios + JWT + expiracao),
# frontend (dia+hora, status generico, tela gestao, esconder config LLM),
# recipe-monitor (sem mudanca de codigo, mas rebuildado para coerencia).
echo ""
echo " [1/4] Build mis-backend:v10.6 ..."
docker build -t mis-backend:v10.6 "$CHANGEOVER_DIR/Backend"

echo ""
echo " [2/4] Build mis-frontend:v10.6 ..."
docker build --build-arg REACT_APP_RECIPE_MONITOR_URL= -t mis-frontend:v10.6 "$CHANGEOVER_DIR/Frontend"

echo ""
echo " [3/4] Build mis-recipe-intelligent:v10.6 ..."
docker build -t mis-recipe-intelligent:v10.6 "$RECIPE_DIR"

echo ""
echo " [4/4] Salvando 3 imagens em $TAR_FILE ..."
docker save mis-backend:v10.6 mis-recipe-intelligent:v10.6 mis-frontend:v10.6 -o "$TAR_FILE"
SIZE=$(du -sh "$TAR_FILE" | cut -f1)
echo " [OK] $TAR_FILE ($SIZE)"

cat > "$LOAD_SCRIPT" << 'LOAD_EOF'
#!/bin/bash
# carregar-v10.6.sh — Patch incremental -> v10.6
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HUB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TAR_FILE="$SCRIPT_DIR/mis-changeover-v10.6.tar"

echo ""
echo "=== MIS Changeover v10.6 - Deploy Incremental ==="
[ -f "$TAR_FILE" ] || { echo "ERRO: $TAR_FILE nao encontrado."; exit 1; }

echo "[1/4] Carregando imagens..."
docker load -i "$TAR_FILE"
for IMG in mis-backend:v10.6 mis-recipe-intelligent:v10.6 mis-frontend:v10.6; do
    docker image inspect "$IMG" >/dev/null 2>&1 || { echo "ERRO: $IMG nao carregada"; exit 1; }
    echo "    OK: $IMG"
done

TARGET_COMPOSE="$HUB_DIR/docker-compose.yml"
TS=$(date +%Y%m%d-%H%M%S)
if [ -f "$TARGET_COMPOSE" ]; then
    cp "$TARGET_COMPOSE" "$TARGET_COMPOSE.bkp.$TS"
    echo ""
    echo "[2/4] Atualizando tags em $TARGET_COMPOSE (backup: .bkp.$TS)"
    sed -i -E 's|mis-backend:v10\.[0-9]+|mis-backend:v10.6|g'                   "$TARGET_COMPOSE"
    sed -i -E 's|mis-recipe-intelligent:v10\.[0-9]+|mis-recipe-intelligent:v10.6|g' "$TARGET_COMPOSE"
    sed -i -E 's|mis-frontend:v10\.[0-9]+|mis-frontend:v10.6|g'                 "$TARGET_COMPOSE"
    echo "    OK"
else
    echo "AVISO: $TARGET_COMPOSE nao existe. Edite manualmente para v10.6."
fi

echo ""
echo "[3/4] Recriando containers backend + frontend + recipe-monitor..."
cd "$HUB_DIR"
sudo docker compose up -d --force-recreate --no-deps mis-changeover-backend mis-changeover-frontend mis-recipe-monitor
docker exec mis-core-proxy nginx -s reload 2>/dev/null || sudo docker compose restart nginx-proxy

echo ""
echo "[4/4] Validando..."
for i in $(seq 1 30); do
    docker exec mis-changeover-backend curl -fs http://localhost:8000/api/health/ >/dev/null 2>&1 && { echo "    Django OK"; break; }
    sleep 2
done
for i in $(seq 1 20); do
    docker exec mis-recipe-monitor python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')" >/dev/null 2>&1 && { echo "    Recipe Monitor OK"; break; }
    sleep 2
done
echo ""
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E "(NAMES|mis-changeover|mis-recipe|mis-redis|mis-core-proxy)"
echo ""
echo "Deploy v10.6 concluido."
echo ""
echo "Opcional — ajustar deadband de ruido em REAL (em .env do hub):"
echo "  RECIPE_MONITOR_COV_DEADBAND_REAL=0.01   # ignora oscilacoes < 0.01"
echo "  (default 0.0 = registra so quando o valor muda exatamente)"
echo ""
echo "Rollback v10.5:"
echo "  cp $TARGET_COMPOSE.bkp.$TS $TARGET_COMPOSE"
echo "  sudo docker compose up -d --no-deps mis-changeover-backend mis-changeover-frontend mis-recipe-monitor"
echo "  docker exec mis-core-proxy nginx -s reload"
LOAD_EOF
chmod +x "$LOAD_SCRIPT"

echo ""
echo "================================================="
echo " PACOTE v10.6 GERADO"
echo "================================================="
ls -lh "$OUTDIR" | grep -E "v10\.5" || true
echo ""
echo "Copie para o servidor OT:"
echo "  $TAR_FILE"
echo "  $LOAD_SCRIPT"
