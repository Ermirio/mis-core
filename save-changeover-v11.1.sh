#!/bin/bash
# ============================================================
# save-changeover-v11.1.sh
# Patch v11.0 -> v11.1 (backend + frontend + recipe rebuild).
#
# POR QUE v11.1 (e nao reusar v11.0):
#   Tag de imagem no Docker e um ponteiro mutavel. Reusar a MESMA tag (v11.0)
#   para conteudo diferente faz o Compose achar que "ja esta atualizado" e NAO
#   recriar o container (ele compara a string da tag + hash de config, nao o
#   digest resolvido). Subir a versao (v11.1) muda de fato a linha do compose
#   => recriacao garantida e verificavel via `docker ps` / imagem do container.
#
# CONTEUDO (mesmo do v11.0 + ajustes de frontend do card "Formato na maquina"):
#   A) Validacao de Qualidade por CAIXAS (primeira rodada de SKU) — Fase 1 (MIS)
#   B) Sincronismo de receita TRAVADO no formato que roda na maquina
#      (detectado via OPC + fallback ultima troca) — elimina risco de
#      sincronizar no formato errado.
#
# O que muda:
#   * Backend (mis-backend:v11.1):
#       - Migration 0020_validacao_por_caixas (ADITIVA):
#         + Linha.tag_caixas_sku_opc (contador de caixas desde a troca)
#         + ValidacaoQualidade: meta_caixas, caixas_produzidas, parada_em,
#           caixas_na_aprovacao, observacao_qualidade
#         + Modelos: ConfiguracaoValidacaoQualidade, CriterioValidacaoQualidade
#           (Formato x Linha), HistoricoValidacaoQualidade
#       - Worker: conta caixas (nao mais tempo); ao atingir a meta escreve True
#         em tag_aguardando_validacao_opc (CLP para) e registra historico.
#       - Aprovacao registra quem/caixas/observacao no historico e libera.
#       - (B) _resolver_formato_ativo(linha): le tag_sku_atual_opc (OPC) com
#         fallback p/ StatusLinha.sku_atual -> AssociacaoProdutoLinha -> formato.
#       - (B) GET /api/recipe-monitor/linha/<nome>/formato-ativo/ (formato+receita).
#       - (B) recipe_monitor_sincronizar: TRAVA 409 'formato_divergente' se o
#         formato pedido != formato ativo detectado na linha.
#   * Frontend (mis-frontend:v11.1):
#       - Tela Validacoes: barra de CAIXAS (X/Y) no lugar do timer; badge
#         "Linha parada — aguardando validacao"; caixas amostradas na aprovacao.
#       - (B) Monitor de Receita: dropdown de formato substituido por card
#         TRAVADO "Formato na maquina" (nome + SKU + fonte OPC/ultima troca).
#   * Recipe Monitor: repasse do sincronismo ja injeta linha_nome (rebuild).
#
#   ATENCAO — Fase 2 (automacao, NAO incluida): o CLP precisa expor a tag
#   "caixas desde a troca" (zerada na troca) para o fluxo rodar de ponta a ponta.
#
# Saidas:
#   mis-changeover-v11.1.tar   (3 imagens)
#   carregar-v11.1.sh
# ============================================================
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANGEOVER_DIR="$ROOT_DIR/mis-change-over"
RECIPE_DIR="$CHANGEOVER_DIR/Backend/recipe_monitor_service"
OUTDIR="$ROOT_DIR/dist/deploy"
TAR_FILE="$OUTDIR/mis-changeover-v11.1.tar"
LOAD_SCRIPT="$OUTDIR/carregar-v11.1.sh"

mkdir -p "$OUTDIR"

echo "================================================="
echo " MIS Changeover v11.1 - Validacao por CAIXAS + Formato travado na maquina"
echo "================================================="

echo ""
echo " [1/4] Build mis-backend:v11.1 ..."
docker build -t mis-backend:v11.1 "$CHANGEOVER_DIR/Backend"

echo ""
echo " [2/4] Build mis-frontend:v11.1 ..."
docker build --build-arg REACT_APP_RECIPE_MONITOR_URL= -t mis-frontend:v11.1 "$CHANGEOVER_DIR/Frontend"

echo ""
echo " [3/4] Build mis-recipe-intelligent:v11.1 ..."
docker build -t mis-recipe-intelligent:v11.1 "$RECIPE_DIR"

echo ""
echo " [4/4] Salvando 3 imagens em $TAR_FILE ..."
docker save mis-backend:v11.1 mis-recipe-intelligent:v11.1 mis-frontend:v11.1 -o "$TAR_FILE"
SIZE=$(du -sh "$TAR_FILE" | cut -f1)
echo " [OK] $TAR_FILE ($SIZE)"

cat > "$LOAD_SCRIPT" << 'LOAD_EOF'
#!/bin/bash
# carregar-v11.1.sh — Patch incremental -> v11.1
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HUB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TAR_FILE="$SCRIPT_DIR/mis-changeover-v11.1.tar"

echo ""
echo "=== MIS Changeover v11.1 - Deploy Incremental ==="
[ -f "$TAR_FILE" ] || { echo "ERRO: $TAR_FILE nao encontrado. Copie o .tar para $SCRIPT_DIR"; exit 1; }

echo "[1/4] Carregando imagens..."
docker load -i "$TAR_FILE"
for IMG in mis-backend:v11.1 mis-recipe-intelligent:v11.1 mis-frontend:v11.1; do
    docker image inspect "$IMG" >/dev/null 2>&1 || { echo "ERRO: $IMG nao carregada"; exit 1; }
    echo "    OK: $IMG"
done

TARGET_COMPOSE="$HUB_DIR/docker-compose.yml"
TS=$(date +%Y%m%d-%H%M%S)
if [ -f "$TARGET_COMPOSE" ]; then
    cp "$TARGET_COMPOSE" "$TARGET_COMPOSE.bkp.$TS"
    echo ""
    echo "[2/4] Atualizando tags em $TARGET_COMPOSE (backup: .bkp.$TS)"
    # Aceita origem v10.x OU v11.0 (qualquer versao anterior) -> v11.1.
    # Delimitador '#' para o '|' ficar como alternancia ERE sem ambiguidade.
    sed -i -E 's#mis-backend:v(10\.[0-9]+|11\.0)#mis-backend:v11.1#g'                   "$TARGET_COMPOSE"
    sed -i -E 's#mis-recipe-intelligent:v(10\.[0-9]+|11\.0)#mis-recipe-intelligent:v11.1#g' "$TARGET_COMPOSE"
    sed -i -E 's#mis-frontend:v(10\.[0-9]+|11\.0)#mis-frontend:v11.1#g'                 "$TARGET_COMPOSE"
    echo "    Tags apos ajuste:"
    grep -nE 'mis-(backend|frontend|recipe-intelligent):v' "$TARGET_COMPOSE" | sed 's/^/      /'
else
    echo "AVISO: $TARGET_COMPOSE nao existe. Edite manualmente para v11.1."
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
echo "Status + IMAGEM que cada container esta rodando (confirme v11.1):"
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -E "(NAMES|mis-changeover|mis-recipe|mis-redis|mis-core-proxy)"
echo ""
echo "Deploy v11.1 concluido."
echo ""
echo "Rollback v11.0:"
echo "  cp $TARGET_COMPOSE.bkp.$TS $TARGET_COMPOSE"
echo "  sudo docker compose up -d --no-deps mis-changeover-backend mis-changeover-frontend mis-recipe-monitor"
echo "  docker exec mis-core-proxy nginx -s reload"
LOAD_EOF
chmod +x "$LOAD_SCRIPT"

echo ""
echo "================================================="
echo " PACOTE v11.1 GERADO"
echo "================================================="
ls -lh "$OUTDIR" | grep -E "v11\.1" || true
echo ""
echo "Copie para o servidor OT (RECOPIE o .tar — nome novo evita usar o antigo):"
echo "  $TAR_FILE"
echo "  $LOAD_SCRIPT"
