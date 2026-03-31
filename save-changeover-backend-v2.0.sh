#!/bin/bash
# ============================================================
# save-changeover-backend-v2.0.sh
# Funcionalidade: Duplicar Formato no Django Admin
#   - Botão "Duplicar Formato" na tela de edição
#   - View customizada com formulário de confirmação
#   - Cópia atômica de Formato + todos os FormatoVariavel
#
# Gera: dist/deploy/mis-core-changeover-backend-2.0.tar
# Imagem: mis-core-changeover-backend:2.0
# ============================================================
set -e

OUTDIR="dist/deploy"
OUTFILE="$OUTDIR/mis-core-changeover-backend-2.0.tar"

mkdir -p "$OUTDIR"

echo "================================================="
echo " VERIFICANDO imagem local..."
echo "================================================="

IMAGE="mis-core-changeover-backend:2.0"

if ! docker image inspect "$IMAGE" &>/dev/null; then
  echo ""
  echo "  [ERRO] $IMAGE não encontrada localmente."
  echo "  Execute primeiro:"
  echo "    cd mis-change-over/Backend"
  echo "    docker build -t $IMAGE ."
  exit 1
fi

echo "  [OK] $IMAGE"

echo ""
echo "================================================="
echo " SALVANDO imagem em:"
echo " $OUTFILE"
echo "================================================="

docker save "$IMAGE" -o "$OUTFILE"

SIZE=$(du -sh "$OUTFILE" | cut -f1)

echo ""
echo "================================================="
echo " CONCLUIDO!"
echo " Arquivo: $OUTFILE ($SIZE)"
echo ""
echo " ── PROCEDIMENTO DE ATUALIZAÇÃO NO SERVIDOR OT ──"
echo ""
echo " 1. Transferir o arquivo ao servidor:"
echo "    scp $OUTFILE usuario@servidor-ot:/opt/mis-core/"
echo ""
echo " 2. Transferir o docker-compose.yml atualizado:"
echo "    scp docker-compose.yml usuario@servidor-ot:/opt/mis-core/"
echo ""
echo " 3. No servidor OT, carregar a imagem:"
echo "    cd /opt/mis-core"
echo "    docker load -i mis-core-changeover-backend-2.0.tar"
echo ""
echo " 4. Reiniciar apenas o serviço do changeover backend:"
echo "    docker compose up -d --no-deps mis-changeover-backend"
echo ""
echo " 5. Verificar saúde do container:"
echo "    docker compose ps mis-changeover-backend"
echo "    docker logs mis-changeover-backend --tail 30"
echo ""
echo " Nenhum outro serviço precisa ser reiniciado."
echo " Nenhuma migração de banco necessária (sem alteração de models)."
echo "================================================="
