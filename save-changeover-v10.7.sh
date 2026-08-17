#!/bin/bash
# ============================================================
# save-changeover-v10.7.sh  —  Patch backend-only sobre v10.6
#
# O que muda (ips backend):
#   * Admin de ContaUsuarioExpiracao travado: SOMENTE superuser vê/edita/renova.
#     Impede que o time que cria usuarios (staff nao-superuser) estenda
#     validade sem aprovacao. has_add_permission=False (so signal cria).
#   * models.renovar() agora reseta last_login: destrava contas bloqueadas
#     por INATIVIDADE (antes a renovacao nao resolvia esse caso).
#
#   Frontend e recipe-monitor: NAO mudam (retag de v10.6).
# ============================================================
set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANGEOVER_DIR="$ROOT_DIR/mis-change-over"
OUTDIR="$ROOT_DIR/dist/deploy"
TAR_FILE="$OUTDIR/mis-changeover-v10.7.tar"
LOAD_SCRIPT="$OUTDIR/carregar-v10.7.sh"
mkdir -p "$OUTDIR"

echo "================================================="
echo " MIS Changeover v10.7 - Patch (hardening expiracao de usuarios)"
echo "================================================="

echo ""
echo " [1/4] Build mis-backend:v10.7 ..."
docker build -t mis-backend:v10.7 "$CHANGEOVER_DIR/Backend"

echo ""
echo " [2/4] Retag mis-frontend:v10.6 -> v10.7 (sem mudancas)..."
docker tag mis-frontend:v10.6 mis-frontend:v10.7

echo ""
echo " [3/4] Retag mis-recipe-intelligent:v10.6 -> v10.7 (sem mudancas)..."
docker tag mis-recipe-intelligent:v10.6 mis-recipe-intelligent:v10.7

echo ""
echo " [4/4] Salvando 3 imagens em $TAR_FILE ..."
docker save mis-backend:v10.7 mis-recipe-intelligent:v10.7 mis-frontend:v10.7 -o "$TAR_FILE"
SIZE=$(du -sh "$TAR_FILE" | cut -f1)
echo " [OK] $TAR_FILE ($SIZE)"

cat > "$LOAD_SCRIPT" << 'LOAD_EOF'
#!/bin/bash
# carregar-v10.7.sh — Patch incremental -> v10.7
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HUB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TAR_FILE="$SCRIPT_DIR/mis-changeover-v10.7.tar"

echo ""
echo "=== MIS Changeover v10.7 - Deploy Incremental ==="
[ -f "$TAR_FILE" ] || { echo "ERRO: $TAR_FILE nao encontrado."; exit 1; }

echo "[1/4] Carregando imagens..."
docker load -i "$TAR_FILE"
for IMG in mis-backend:v10.7 mis-recipe-intelligent:v10.7 mis-frontend:v10.7; do
    docker image inspect "$IMG" >/dev/null 2>&1 || { echo "ERRO: $IMG nao carregada"; exit 1; }
    echo "    OK: $IMG"
done

TARGET_COMPOSE="$HUB_DIR/docker-compose.yml"
TS=$(date +%Y%m%d-%H%M%S)
if [ -f "$TARGET_COMPOSE" ]; then
    cp "$TARGET_COMPOSE" "$TARGET_COMPOSE.bkp.$TS"
    echo ""
    echo "[2/4] Atualizando tags em $TARGET_COMPOSE (backup: .bkp.$TS)"
    sed -i -E 's|mis-backend:v10\.[0-9]+|mis-backend:v10.7|g'                       "$TARGET_COMPOSE"
    sed -i -E 's|mis-recipe-intelligent:v10\.[0-9]+|mis-recipe-intelligent:v10.7|g' "$TARGET_COMPOSE"
    sed -i -E 's|mis-frontend:v10\.[0-9]+|mis-frontend:v10.7|g'                     "$TARGET_COMPOSE"
    echo "    OK"
else
    echo "AVISO: $TARGET_COMPOSE nao existe. Edite manualmente para v10.7."
fi

echo ""
echo "[3/4] Recriando backend (frontend/recipe inalterados, mas retag exige recriar p/ pegar a tag)..."
cd "$HUB_DIR"
sudo docker compose up -d --force-recreate --no-deps mis-changeover-backend mis-changeover-frontend mis-recipe-monitor
docker exec mis-core-proxy nginx -s reload 2>/dev/null || sudo docker compose restart nginx-proxy

echo ""
echo "[4/4] Validando..."
for i in $(seq 1 30); do
    docker exec mis-changeover-backend curl -fs http://localhost:8000/api/health/ >/dev/null 2>&1 && { echo "    Django OK"; break; }
    sleep 2
done
echo ""
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E "(NAMES|mis-changeover|mis-recipe|mis-redis)"
echo ""
echo "Deploy v10.7 concluido. Sem migration nova (so mudanca de codigo)."
echo ""
echo "Verificar: no admin, /mis-change-over-admin/ips/contausuarioexpiracao/"
echo "  deve dar 403/nao aparecer para usuarios que NAO sao superuser."
LOAD_EOF
chmod +x "$LOAD_SCRIPT"

echo ""
echo "================================================="
echo " PACOTE v10.7 GERADO"
echo "================================================="
ls -lh "$OUTDIR" | grep -E "v10\.7" || true
