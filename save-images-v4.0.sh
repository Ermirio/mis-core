#!/bin/bash
# ============================================================
# save-images-v4.0.sh
# Salva as imagens atualizadas (flask v4.0 + frontend v4.0)
# para implantação no servidor OT offline.
#
# Alterações incluídas nesta versão:
#   - mis-core-flask:v4.0  → analytics com p-values, Spearman,
#                            resample dinâmico, scipy
#   - mis-core-frontend:v4.0 → histograma + curva normal,
#                            matriz correlação interativa,
#                            trend line no scatter, export CSV
# ============================================================
set -e

OUTDIR="dist/deploy"
OUTFILE="$OUTDIR/mis-core-images-v4.0.tar"

mkdir -p "$OUTDIR"

echo "================================================="
echo " SALVANDO IMAGENS v4.0 para servidor OT offline"
echo "================================================="

# Apenas as 2 imagens atualizadas nesta versão
UPDATED_IMAGES=(
  "mis-core-flask:v4.0"
  "mis-core-frontend:v4.0"
)

# Imagens das demais versões que devem permanecer no servidor
# (já carregadas previamente — não precisam ser reenviadas)
# Listadas aqui apenas como referência:
#   mis-core-django:v3.0
#   mis-core-proxy:v3.5
#   mis-core-coletor:v3.0
#   mis-core-changeover-frontend:v3.5
#   mis-core-changeover-backend:v1.0
#   mis-core-ai-backend:v1.0 / mis-core-ai-frontend:v1.0
#   mis-core-energy-backend:v1.0 / mis-core-energy-frontend:v1.0
#   mis-core-node-red:v1.0

IMAGES_TO_SAVE=()

echo ""
echo "Verificando imagens locais..."
for img in "${UPDATED_IMAGES[@]}"; do
  if docker image inspect "$img" &>/dev/null; then
    IMAGES_TO_SAVE+=("$img")
    echo "  [OK] $img"
  else
    echo "  [ERRO] $img — não encontrada. Execute primeiro:"
    echo "         docker build -t $img <contexto>"
    exit 1
  fi
done

echo ""
echo "================================================="
echo " SALVANDO ${#IMAGES_TO_SAVE[@]} imagens em:"
echo " $OUTFILE"
echo "================================================="

docker save "${IMAGES_TO_SAVE[@]}" -o "$OUTFILE"

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
echo " 2. Transferir arquivos de configuração atualizados:"
echo "    scp docker-compose.yml usuario@servidor-ot:/opt/mis-core/"
echo ""
echo " 3. No servidor OT, executar:"
echo "    cd /opt/mis-core"
echo "    docker load -i mis-core-images-v4.0.tar"
echo ""
echo " 4. Reiniciar apenas os serviços atualizados"
echo "    (sem derrubar o restante do stack):"
echo "    docker compose up -d --no-deps flask frontend"
echo ""
echo " 5. Verificar saúde dos containers:"
echo "    docker compose ps"
echo "    docker logs mis-core-flask --tail 30"
echo "    docker logs mis-core-frontend --tail 20"
echo ""
echo " Nginx NÃO precisa ser reiniciado (sem alteração de rotas)."
echo " Django NÃO precisa ser reiniciado."
echo "================================================="
