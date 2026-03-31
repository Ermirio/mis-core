#!/bin/bash
# ============================================================
# save-images-v2.5.sh
# Constrói as imagens corrigidas (sem volume de código),
# taga como v2.5 e salva tudo que precisa ir para o servidor
# offline num único arquivo .tar
# ============================================================
set -e

OUTDIR="dist/deploy"
OUTFILE="$OUTDIR/mis-core-images-v2.5.tar"

mkdir -p "$OUTDIR"

echo "================================================="
echo " BUILD: flask, django, coletor → v2.5"
echo " + proxy (nginx.conf atualizado)"
echo " + changeover-frontend (env corrigido)"
echo "================================================="

docker compose build flask django coletor nginx-proxy mis-changeover-frontend

echo ""
echo "================================================="
echo " VERIFICANDO imagens customizadas existentes..."
echo "================================================="

# Imagens customizadas que precisam ir junto
# (as que foram buildadas localmente — não vêm do Docker Hub)
CUSTOM_IMAGES=(
  "mis-core-flask:v2.5"
  "mis-core-django:v2.5"
  "mis-core-coletor:v2.5"
  "mis-core-frontend:v2.1"
  "mis-core-proxy:v2.0"
  "mis-core-node-red:v1.0"
  "mis-core-ai-backend:v1.0"
  "mis-core-ai-frontend:v1.0"
  "mis-core-energy-backend:v1.0"
  "mis-core-energy-frontend:v1.0"
  "mis-core-energy-collector:v1.0"
  "mis-core-changeover-backend:v1.0"
  "mis-core-changeover-frontend:v1.0"
)

# Imagens públicas que também precisam estar offline
PUBLIC_IMAGES=(
  "mysql:8.0"
  "influxdb:1.8-alpine"
  "portainer/portainer-ce:latest"
  "n8nio/n8n:latest"
  "grafana/grafana:latest"
  "emqx/emqx:5.8.5"
  "chronograf:1.8"
  "kapacitor:1.5"
)

IMAGES_TO_SAVE=()

for img in "${CUSTOM_IMAGES[@]}"; do
  if docker image inspect "$img" &>/dev/null; then
    IMAGES_TO_SAVE+=("$img")
    echo "  [OK] $img"
  else
    echo "  [SKIP] $img — não encontrada localmente (rode 'docker compose build' antes)"
  fi
done

for img in "${PUBLIC_IMAGES[@]}"; do
  if docker image inspect "$img" &>/dev/null; then
    IMAGES_TO_SAVE+=("$img")
    echo "  [OK] $img"
  else
    echo "  [SKIP] $img — não encontrada localmente (rode 'docker pull $img' antes)"
  fi
done

if [ ${#IMAGES_TO_SAVE[@]} -eq 0 ]; then
  echo "Nenhuma imagem encontrada para salvar. Abortando."
  exit 1
fi

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
echo " Para transferir ao servidor offline:"
echo "   scp $OUTFILE usuario@servidor:/caminho/destino/"
echo ""
echo " No servidor offline, para carregar:"
echo "   docker load -i mis-core-images-v2.5.tar"
echo ""
echo " Lembre de copiar também:"
echo "   - docker-compose.yml"
echo "   - .env"
echo "   - proxy-reverse/nginx.conf   ← OBRIGATÓRIO (volume mount ativo)"
echo "   - proxy-reverse/html/"
echo "   - proxy-reverse/imagens/"
echo "================================================="
