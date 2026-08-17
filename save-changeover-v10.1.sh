#!/bin/bash
# ============================================================
# save-changeover-v10.1.sh
#
# Patch incremental v10.0 -> v10.1.
#
# O que muda:
#   * Django (mis-backend:v10.1):
#       - convert_value aceita "32.0" para tipos inteiros (int(float(valor)))
#       - OPCCoordinatorConfigView com permission_classes = [] (service-to-service)
#       - FormatoSerializer sem recursao (get_variaveis dict direto)
#       - get_produtos_count usa AssociacaoProdutoLinha
#       - HistoricoSincronismoReceita registrado no admin
#
#   * Recipe Monitor (mis-recipe-intelligent:v10.1):
#       - Pydantic schemas aceitam int (Optional[int | float | bool | str])
#       - _to_django_string: float inteiro -> int string (32.0 -> 32)
#       - Filtro de equipamentos por tipo (default: BALANCA*)
#       - Filtro de variaveis por nome (default: SKU_Esperado, Descricao_Esperada,
#         EAN_Esperado, DUN14_Esperado, Filme_Esperado, NumeroOP_Esperado)
#       - Ambos configuraveis via env (RECIPE_MONITOR_IGNORE_EQUIPMENT_TYPES
#         e RECIPE_MONITOR_IGNORE_VARIABLE_NAMES)
#
#   * Frontend: NAO MUDA. Continua mis-frontend:v10.0.
#
# Saidas em dist/deploy/:
#   mis-changeover-v10.1.tar             (2 imagens: backend + recipe)
#   carregar-v10.1.sh                    (deploy automatico)
# ============================================================
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANGEOVER_DIR="$ROOT_DIR/mis-change-over"
RECIPE_DIR="$CHANGEOVER_DIR/Backend/recipe_monitor_service"
OUTDIR="$ROOT_DIR/dist/deploy"
TAR_FILE="$OUTDIR/mis-changeover-v10.1.tar"
LOAD_SCRIPT="$OUTDIR/carregar-v10.1.sh"

mkdir -p "$OUTDIR"

echo "================================================="
echo " MIS Changeover v10.1 - Patch incremental (backend + recipe-monitor)"
echo "================================================="

echo ""
echo " [1/4] Build mis-backend:v10.1 ..."
docker build -t mis-backend:v10.1 "$CHANGEOVER_DIR/Backend"

echo ""
echo " [2/4] Build mis-recipe-intelligent:v10.1 ..."
docker build -t mis-recipe-intelligent:v10.1 "$RECIPE_DIR"

echo ""
echo " [3/4] Build mis-frontend:v10.1 (com protecao do botao Sincronizar)..."
docker build \
    --build-arg REACT_APP_RECIPE_MONITOR_URL= \
    -t mis-frontend:v10.1 \
    "$CHANGEOVER_DIR/Frontend"

echo ""
echo " [4/4] Salvando 3 imagens em $TAR_FILE ..."
docker save mis-backend:v10.1 mis-recipe-intelligent:v10.1 mis-frontend:v10.1 -o "$TAR_FILE"
SIZE=$(du -sh "$TAR_FILE" | cut -f1)
echo " [OK] $TAR_FILE ($SIZE)"

# Gerar carregar-v10.1.sh
cat > "$LOAD_SCRIPT" << 'LOAD_EOF'
#!/bin/bash
# carregar-v10.1.sh — Patch incremental v10.0 -> v10.1 (backend + recipe-monitor)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HUB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TAR_FILE="$SCRIPT_DIR/mis-changeover-v10.1.tar"

echo ""
echo "=== MIS Changeover v10.1 - Deploy Incremental ==="
echo "Hub dir: $HUB_DIR"
echo ""

if [ ! -f "$TAR_FILE" ]; then
    echo "ERRO: $TAR_FILE nao encontrado."
    exit 1
fi

# 1. Carregar imagens
echo "[1/4] Carregando imagens..."
docker load -i "$TAR_FILE"
for IMG in mis-backend:v10.1 mis-recipe-intelligent:v10.1 mis-frontend:v10.1; do
    docker image inspect "$IMG" >/dev/null 2>&1 || { echo "ERRO: $IMG nao carregada"; exit 1; }
    echo "    OK: $IMG"
done

# 2. Atualizar tags no docker-compose.yml (substitui v10.0 -> v10.1 apenas das 2 imagens)
TARGET_COMPOSE="$HUB_DIR/docker-compose.yml"
TS=$(date +%Y%m%d-%H%M%S)
if [ -f "$TARGET_COMPOSE" ]; then
    cp "$TARGET_COMPOSE" "$TARGET_COMPOSE.bkp.$TS"
    echo ""
    echo "[2/4] Atualizando tags em $TARGET_COMPOSE (backup: .bkp.$TS)"
    sed -i 's|mis-backend:v10\.0|mis-backend:v10.1|g'                   "$TARGET_COMPOSE"
    sed -i 's|mis-recipe-intelligent:v10\.0|mis-recipe-intelligent:v10.1|g' "$TARGET_COMPOSE"
    sed -i 's|mis-frontend:v10\.0|mis-frontend:v10.1|g'                 "$TARGET_COMPOSE"
    echo "    OK"
else
    echo "AVISO: $TARGET_COMPOSE nao existe. Edite manualmente para usar v10.1."
fi

# 3. Recriar apenas os 2 containers afetados (preserva o resto)
echo ""
echo "[3/4] Recriando containers backend + frontend + recipe-monitor (sem mexer nos outros)..."
cd "$HUB_DIR"
sudo docker compose up -d --force-recreate --no-deps mis-changeover-backend mis-changeover-frontend mis-recipe-monitor

# 3b. Reload do proxy (evita 502 por DNS cache)
echo "    Reload do nginx-proxy (evita 502 por DNS stale)..."
docker exec mis-core-proxy nginx -s reload 2>/dev/null || \
    sudo docker compose restart nginx-proxy

# 4. Validar
echo ""
echo "[4/4] Validando saude..."
for i in $(seq 1 30); do
    if docker exec mis-changeover-backend curl -fs http://localhost:8000/api/health/ >/dev/null 2>&1; then
        echo "    Django OK"
        break
    fi
    sleep 2
done
for i in $(seq 1 20); do
    if docker exec mis-recipe-monitor python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')" >/dev/null 2>&1; then
        echo "    Recipe Monitor OK"
        break
    fi
    sleep 2
done
echo ""
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E "(NAMES|mis-changeover-backend|mis-recipe-monitor|mis-core-proxy|mis-redis)"

echo ""
echo "============================================="
echo " Deploy v10.1 concluido"
echo "============================================="
echo ""
echo "Mudancas que entraram:"
echo "  * Bug do '32.0' em DINT/UDINT: corrigido em todas as camadas"
echo "  * Balancas e variaveis interceptadas (SKU_Esperado etc): NAO aparecem mais no monitor"
echo ""
echo "Variaveis env opcionais (em .env do hub) — defaults ja cobrem o caso comum:"
echo "  RECIPE_MONITOR_IGNORE_EQUIPMENT_TYPES=BALANCA,BALANCA_PLC"
echo "  RECIPE_MONITOR_IGNORE_VARIABLE_NAMES=SKU_Esperado,Descricao_Esperada,EAN_Esperado,DUN14_Esperado,Filme_Esperado,NumeroOP_Esperado"
echo ""
echo "Rollback v10.0:"
echo "  cp $TARGET_COMPOSE.bkp.$TS $TARGET_COMPOSE"
echo "  sudo docker compose up -d --no-deps mis-changeover-backend mis-recipe-monitor"
echo "  docker exec mis-core-proxy nginx -s reload"
echo ""
LOAD_EOF
chmod +x "$LOAD_SCRIPT"

echo ""
echo "================================================="
echo " PACOTE v10.1 GERADO"
echo "================================================="
ls -lh "$OUTDIR" | grep -E "v10\.1" || true
echo ""
echo "Copie ESSES 2 ARQUIVOS para o servidor OT:"
echo "  $TAR_FILE"
echo "  $LOAD_SCRIPT"
echo ""
echo "No servidor OT:"
echo "  cd ~/mis-hub/deploy/  (ou onde estao os arquivos)"
echo "  bash carregar-v10.1.sh"
echo ""
