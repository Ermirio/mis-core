# ============================================================================
# mis-core-nodered — imagem Node-RED com TODOS os nós usados no MIS Core.
#
# Construída automaticamente pelo `export_images.ps1` da pasta mis-core-offline:
#   1. Mantem um baseline industrial obrigatorio no package.json.
#   2. Mescla nos extras instalados no container DEV, quando ele existir.
#   3. Builda `mis-core-nodered:$Version` com `docker build`.
#   4. Empacota dentro do tar.gz do deploy offline.
#
# Resultado: o pacote OT instala todos os nós sem precisar de internet —
# o `npm install` aconteceu na máquina DEV, durante o build.
# ============================================================================
FROM nodered/node-red:4.0.9-20

# Cópia em camada própria pra cache funcionar quando só código de fluxo muda.
COPY package.json /tmp/package.json

# Instala os nos no userDir (/data), mesmo lugar onde o palette manager
# instalaria. Em uma VM nova, o volume nodered_data nasce com este conteudo.
# Em VM ja em execucao, rode update-nodered-nodes.sh para sincronizar o
# node_modules novo para o volume existente.
USER root
RUN cp /tmp/package.json /data/package.json && \
    cd /data && \
    npm install --unsafe-perm --no-update-notifier --no-fund --omit=dev && \
    chown -R node-red:node-red /data
USER node-red

LABEL org.opencontainers.image.title="mis-core-nodered" \
      org.opencontainers.image.description="Node-RED + nodes industriais do MIS Core"
