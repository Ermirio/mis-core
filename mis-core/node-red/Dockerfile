FROM nodered/node-red:latest

# Copia package.json para instalação de plugins automaticos
# (O usuário deve criar este arquivo se quiser plugins pré-instalados)
# COPY package.json .
# RUN npm install --unsafe-perm --no-update-notifier --no-fund --only=production

# Exemplo de instalação manual se necessário
# RUN npm install node-red-contrib-influxdb node-red-dashboard

# Configurações de ambiente padrão podem ser sobrescritas no docker-compose
ENV NODE_RED_ENABLE_PROJECTS=true
