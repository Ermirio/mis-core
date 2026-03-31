#!/bin/bash
# ============================================================
# save-changeover-backend-v7.1.sh
# Funcionalidade: Impressora 3M via pysmb — compatível Linux/Docker
#   - Substituição de open() UNC path por SMBConnection (pysmb)
#   - Elimina dependência de SMB 1.0/CIFS habilitado no Windows
#   - pysmb==1.2.10 adicionado ao requirements.txt
#
# Gera: dist/deploy/mis-core-changeover-backend-v7.1.tar
# Imagem: mis-core-changeover-backend:v7.1
# ============================================================
set -e

OUTDIR="dist/deploy"
OUTFILE="$OUTDIR/mis-core-changeover-backend-v7.1.tar"

mkdir -p "$OUTDIR"

echo "================================================="
echo " VERIFICANDO imagem local..."
echo "================================================="

IMAGE="mis-core-changeover-backend:v7.1"

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
echo " 2. Transferir o docker-compose.offline.yml atualizado:"
echo "    scp docker-compose.offline.yml usuario@servidor-ot:/opt/mis-core/"
echo ""
echo " 3. No servidor OT, carregar a imagem:"
echo "    cd /opt/mis-core"
echo "    docker load -i mis-core-changeover-backend-v7.1.tar"
echo ""
echo " 4. Reiniciar apenas o serviço do changeover backend:"
echo "    docker compose -f docker-compose.offline.yml up -d --no-deps mis-changeover-backend"
echo ""
echo " 5. Verificar saúde do container:"
echo "    docker compose -f docker-compose.offline.yml ps mis-changeover-backend"
echo "    docker logs mis-changeover-backend --tail 30"
echo ""
echo " Nenhum outro serviço precisa ser reiniciado."
echo " Nenhuma migração de banco necessária (sem alteração de models)."
echo "================================================="
