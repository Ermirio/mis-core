#!/bin/bash
# ============================================================
# save-changeover-v11.0.sh
# Patch v10.10 -> v11.0 (backend + frontend; recipe rebuild p/ coerencia).
#
# FEATURES:
#   A) Validacao de Qualidade por CAIXAS (primeira rodada de SKU) — Fase 1 (MIS)
#   B) Sincronismo de receita TRAVADO no formato que roda na maquina
#      (detectado via OPC + fallback ultima troca) — elimina risco de
#      sincronizar no formato errado.
#
# O que muda:
#   * Backend (mis-backend:v11.0):
#       - Migration 0020_validacao_por_caixas (ADITIVA):
#         + Linha.tag_caixas_sku_opc (contador de caixas desde a troca)
#         + ValidacaoQualidade: meta_caixas, caixas_produzidas, parada_em,
#           caixas_na_aprovacao, observacao_qualidade
#         + Modelos: ConfiguracaoValidacaoQualidade (default global + chave geral),
#           CriterioValidacaoQualidade (Formato x Linha), HistoricoValidacaoQualidade
#       - Worker: conta caixas (nao mais tempo); ao atingir a meta escreve True
#         em tag_aguardando_validacao_opc (CLP para) e registra historico.
#       - Aprovacao registra quem/caixas/observacao no historico e libera (OPC False).
#       - (B) _resolver_formato_ativo(linha): le tag_sku_atual_opc (OPC) com
#         fallback p/ StatusLinha.sku_atual -> AssociacaoProdutoLinha -> formato.
#       - (B) GET /api/recipe-monitor/linha/<nome>/formato-ativo/ (formato+receita).
#       - (B) recipe_monitor_sincronizar: TRAVA 409 'formato_divergente' se o
#         formato pedido != formato ativo detectado na linha.
#   * Frontend (mis-frontend:v11.0):
#       - Tela Validacoes: barra de CAIXAS (X/Y) no lugar do timer; badge
#         "Linha parada — aguardando validacao"; caixas amostradas na aprovacao.
#       - (B) Monitor de Receita: dropdown de formato substituido por card
#         TRAVADO "Formato na maquina" (nome + SKU + fonte OPC/ultima troca).
#   * Recipe Monitor: repasse do sincronismo ja injeta linha_nome (sem mudanca
#     de codigo; rebuild p/ coerencia).
#
#   ATENCAO — Fase 2 (automacao, NAO incluida): o CLP precisa expor a tag
#   "caixas desde a troca" (zerada na troca) para o fluxo rodar de ponta a ponta.
#   Ate la, a validacao so cria/conta se a tag estiver configurada e lendo.
#
# Saidas:
#   mis-changeover-v11.0.tar   (3 imagens)
#   carregar-v11.0.sh
# ============================================================
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANGEOVER_DIR="$ROOT_DIR/mis-change-over"
RECIPE_DIR="$CHANGEOVER_DIR/Backend/recipe_monitor_service"
OUTDIR="$ROOT_DIR/dist/deploy"
TAR_FILE="$OUTDIR/mis-changeover-v11.0.tar"
LOAD_SCRIPT="$OUTDIR/carregar-v11.0.sh"

mkdir -p "$OUTDIR"

echo "================================================="
echo " MIS Changeover v11.0 - Validacao de Qualidade por CAIXAS (Fase 1)"
echo "================================================="

# v11.0 muda os TRES: backend (gestao usuarios + JWT + expiracao),
# frontend (dia+hora, status generico, tela gestao, esconder config LLM),
# recipe-monitor (sem mudanca de codigo, mas rebuildado para coerencia).
echo ""
echo " [1/4] Build mis-backend:v11.0 ..."
docker build -t mis-backend:v11.0 "$CHANGEOVER_DIR/Backend"

echo ""
echo " [2/4] Build mis-frontend:v11.0 ..."
docker build --build-arg REACT_APP_RECIPE_MONITOR_URL= -t mis-frontend:v11.0 "$CHANGEOVER_DIR/Frontend"

echo ""
echo " [3/4] Build mis-recipe-intelligent:v11.0 ..."
docker build -t mis-recipe-intelligent:v11.0 "$RECIPE_DIR"

echo ""
echo " [4/4] Salvando 3 imagens em $TAR_FILE ..."
docker save mis-backend:v11.0 mis-recipe-intelligent:v11.0 mis-frontend:v11.0 -o "$TAR_FILE"
SIZE=$(du -sh "$TAR_FILE" | cut -f1)
echo " [OK] $TAR_FILE ($SIZE)"

cat > "$LOAD_SCRIPT" << 'LOAD_EOF'
#!/bin/bash
# carregar-v11.0.sh — Patch incremental -> v11.0
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HUB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TAR_FILE="$SCRIPT_DIR/mis-changeover-v11.0.tar"

echo ""
echo "=== MIS Changeover v11.0 - Deploy Incremental ==="
[ -f "$TAR_FILE" ] || { echo "ERRO: $TAR_FILE nao encontrado."; exit 1; }

echo "[1/4] Carregando imagens..."
docker load -i "$TAR_FILE"
for IMG in mis-backend:v11.0 mis-recipe-intelligent:v11.0 mis-frontend:v11.0; do
    docker image inspect "$IMG" >/dev/null 2>&1 || { echo "ERRO: $IMG nao carregada"; exit 1; }
    echo "    OK: $IMG"
done

TARGET_COMPOSE="$HUB_DIR/docker-compose.yml"
TS=$(date +%Y%m%d-%H%M%S)
if [ -f "$TARGET_COMPOSE" ]; then
    cp "$TARGET_COMPOSE" "$TARGET_COMPOSE.bkp.$TS"
    echo ""
    echo "[2/4] Atualizando tags em $TARGET_COMPOSE (backup: .bkp.$TS)"
    sed -i -E 's|mis-backend:v10\.[0-9]+|mis-backend:v11.0|g'                   "$TARGET_COMPOSE"
    sed -i -E 's|mis-recipe-intelligent:v10\.[0-9]+|mis-recipe-intelligent:v11.0|g' "$TARGET_COMPOSE"
    sed -i -E 's|mis-frontend:v10\.[0-9]+|mis-frontend:v11.0|g'                 "$TARGET_COMPOSE"
    echo "    OK"
else
    echo "AVISO: $TARGET_COMPOSE nao existe. Edite manualmente para v11.0."
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
echo "Deploy v11.0 concluido."
echo ""
echo "Opcional — ajustar deadband de ruido em REAL (em .env do hub):"
echo "  RECIPE_MONITOR_COV_DEADBAND_REAL=0.01   # ignora oscilacoes < 0.01"
echo "  (default 0.0 = registra so quando o valor muda exatamente)"
echo ""
echo "Rollback v10.10:"
echo "  cp $TARGET_COMPOSE.bkp.$TS $TARGET_COMPOSE"
echo "  sudo docker compose up -d --no-deps mis-changeover-backend mis-changeover-frontend mis-recipe-monitor"
echo "  docker exec mis-core-proxy nginx -s reload"
LOAD_EOF
chmod +x "$LOAD_SCRIPT"

echo ""
echo "================================================="
echo " PACOTE v11.0 GERADO"
echo "================================================="
ls -lh "$OUTDIR" | grep -E "v10\.5" || true
echo ""
echo "Copie para o servidor OT:"
echo "  $TAR_FILE"
echo "  $LOAD_SCRIPT"
