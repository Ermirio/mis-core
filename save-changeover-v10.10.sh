#!/bin/bash
# ============================================================
# save-changeover-v10.10.sh
# Patch v10.8 -> v10.10 (backend + frontend; recipe rebuild p/ coerencia).
#
# O que muda (cumulativo sobre v10.8):
#   * Backend (mis-backend:v10.10):
#       - HARDENING User admin: nao-superuser NAO promove ninguem a superuser.
#         Campos is_superuser/is_staff/groups/user_permissions ficam READ-ONLY
#         para nao-superuser; e nao-superuser nao edita/apaga contas superuser.
#         Fecha o vetor de auto-promocao mesmo com auth.change_user.
#       - Migration 0019: BACKFILL de validade para usuarios comuns que ja
#         existiam antes da feature (davam "sem prazo"). Da +5 meses a todos.
#         Idempotente (get_or_create). Roda automatico no entrypoint.
#   * Frontend (mis-frontend:v10.10) — tela Gestao de Usuarios:
#       - Status legivel (badge com contraste corrigido).
#       - Botao "Definir prazo" para usuario sem validade (cria +5 meses);
#         "Renovar" para os demais (estende +5 meses e reativa).
#   * Recipe Monitor: sem mudanca de codigo (rebuild).
#
# Saidas:
#   mis-changeover-v10.10.tar   (3 imagens)
#   carregar-v10.10.sh
# ============================================================
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANGEOVER_DIR="$ROOT_DIR/mis-change-over"
RECIPE_DIR="$CHANGEOVER_DIR/Backend/recipe_monitor_service"
OUTDIR="$ROOT_DIR/dist/deploy"
TAR_FILE="$OUTDIR/mis-changeover-v10.10.tar"
LOAD_SCRIPT="$OUTDIR/carregar-v10.10.sh"

mkdir -p "$OUTDIR"

echo "================================================="
echo " MIS Changeover v10.10 - Hardening User admin (anti auto-promocao superuser)"
echo "================================================="

# v10.10 muda os TRES: backend (gestao usuarios + JWT + expiracao),
# frontend (dia+hora, status generico, tela gestao, esconder config LLM),
# recipe-monitor (sem mudanca de codigo, mas rebuildado para coerencia).
echo ""
echo " [1/4] Build mis-backend:v10.10 ..."
docker build -t mis-backend:v10.10 "$CHANGEOVER_DIR/Backend"

echo ""
echo " [2/4] Build mis-frontend:v10.10 ..."
docker build --build-arg REACT_APP_RECIPE_MONITOR_URL= -t mis-frontend:v10.10 "$CHANGEOVER_DIR/Frontend"

echo ""
echo " [3/4] Build mis-recipe-intelligent:v10.10 ..."
docker build -t mis-recipe-intelligent:v10.10 "$RECIPE_DIR"

echo ""
echo " [4/4] Salvando 3 imagens em $TAR_FILE ..."
docker save mis-backend:v10.10 mis-recipe-intelligent:v10.10 mis-frontend:v10.10 -o "$TAR_FILE"
SIZE=$(du -sh "$TAR_FILE" | cut -f1)
echo " [OK] $TAR_FILE ($SIZE)"

cat > "$LOAD_SCRIPT" << 'LOAD_EOF'
#!/bin/bash
# carregar-v10.10.sh — Patch incremental -> v10.10
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HUB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TAR_FILE="$SCRIPT_DIR/mis-changeover-v10.10.tar"

echo ""
echo "=== MIS Changeover v10.10 - Deploy Incremental ==="
[ -f "$TAR_FILE" ] || { echo "ERRO: $TAR_FILE nao encontrado."; exit 1; }

echo "[1/4] Carregando imagens..."
docker load -i "$TAR_FILE"
for IMG in mis-backend:v10.10 mis-recipe-intelligent:v10.10 mis-frontend:v10.10; do
    docker image inspect "$IMG" >/dev/null 2>&1 || { echo "ERRO: $IMG nao carregada"; exit 1; }
    echo "    OK: $IMG"
done

TARGET_COMPOSE="$HUB_DIR/docker-compose.yml"
TS=$(date +%Y%m%d-%H%M%S)
if [ -f "$TARGET_COMPOSE" ]; then
    cp "$TARGET_COMPOSE" "$TARGET_COMPOSE.bkp.$TS"
    echo ""
    echo "[2/4] Atualizando tags em $TARGET_COMPOSE (backup: .bkp.$TS)"
    sed -i -E 's|mis-backend:v10\.[0-9]+|mis-backend:v10.10|g'                   "$TARGET_COMPOSE"
    sed -i -E 's|mis-recipe-intelligent:v10\.[0-9]+|mis-recipe-intelligent:v10.10|g' "$TARGET_COMPOSE"
    sed -i -E 's|mis-frontend:v10\.[0-9]+|mis-frontend:v10.10|g'                 "$TARGET_COMPOSE"
    echo "    OK"
else
    echo "AVISO: $TARGET_COMPOSE nao existe. Edite manualmente para v10.10."
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
echo "Deploy v10.10 concluido."
echo ""
echo "Opcional — ajustar deadband de ruido em REAL (em .env do hub):"
echo "  RECIPE_MONITOR_COV_DEADBAND_REAL=0.01   # ignora oscilacoes < 0.01"
echo "  (default 0.0 = registra so quando o valor muda exatamente)"
echo ""
echo "Rollback v10.8:"
echo "  cp $TARGET_COMPOSE.bkp.$TS $TARGET_COMPOSE"
echo "  sudo docker compose up -d --no-deps mis-changeover-backend mis-changeover-frontend mis-recipe-monitor"
echo "  docker exec mis-core-proxy nginx -s reload"
LOAD_EOF
chmod +x "$LOAD_SCRIPT"

echo ""
echo "================================================="
echo " PACOTE v10.10 GERADO"
echo "================================================="
ls -lh "$OUTDIR" | grep -E "v10\.5" || true
echo ""
echo "Copie para o servidor OT:"
echo "  $TAR_FILE"
echo "  $LOAD_SCRIPT"
