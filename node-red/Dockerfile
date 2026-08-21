FROM nodered/node-red:4.0.9-20

# Instala todos os nós utilizados no projeto
RUN npm install --unsafe-perm --no-update-notifier --no-fund \
    @energyweb/node-red-contrib-green-proof-worker@~2.5.1 \
    @flowfuse/node-red-dashboard@~1.30.2 \
    node-red-contrib-cip-st-ethernet-ip@~2.0.3 \
    node-red-contrib-consecutive-queue-gate@~1.1.1 \
    node-red-contrib-cron-plus@~2.2.4 \
    node-red-contrib-float@~1.0.3 \
    node-red-contrib-influxdb@~0.7.0 \
    node-red-contrib-modbus@~5.45.2 \
    node-red-contrib-mssql@~0.0.7 \
    node-red-contrib-omron-fins@~0.5.0 \
    node-red-contrib-opcua@~0.2.348 \
    node-red-contrib-originalpid@~0.3.1 \
    node-red-contrib-pccc@~1.0.2 \
    node-red-contrib-postgresql@~0.15.4 \
    node-red-contrib-s7@~3.1.1 \
    node-red-contrib-ui-led@~0.4.11 \
    node-red-contrib-ui-level@~0.1.46 \
    node-red-contrib-ui-navbar@~1.0.11 \
    node-red-contrib-ui-state-trail@~1.0.2 \
    node-red-node-mysql@~3.0.0 \
    node-red-node-sqlite@~1.1.1 \
    node-red-node-ui-table@~0.4.5

# Configurações de ambiente padrão podem ser sobrescritas no docker-compose
ENV NODE_RED_ENABLE_PROJECTS=true
