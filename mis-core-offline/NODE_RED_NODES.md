# Node-RED - Nos Industriais Offline

## O Que Esta Incluido

A imagem `mis-core-nodered:dev` agora inclui um baseline industrial:

- Modbus: `node-red-contrib-modbus`
- MySQL: `node-red-node-mysql` e `node-red-mysql-r2`
- InfluxDB 1.x, 1.8 Flux e 2.0: `node-red-contrib-influxdb`
- Dashboard legado: `node-red-dashboard`
- Dashboard novo: `@flowfuse/node-red-dashboard`
- S7, OPC UA, PCCC, Ethernet/IP, PostgreSQL, SQLite e componentes UI

## VM Nova

Se a VM ainda nao subiu o stack, basta deixar estes arquivos na pasta do pacote:

```text
mis-core-images-dev.tar.gz
mis-core-nodered-dev.tar.gz
mis-core-nodered-dev.sha256
import-images.sh
```

Depois rode:

```bash
cd /mnt/windows-migrations/pacote-vm-linux-dev
sudo bash bootstrap-linux.sh
```

O `import-images.sh` carrega o pacote principal e depois aplica o overlay
`mis-core-nodered-dev.tar.gz` automaticamente.

## VM Ja Rodando

Se o MIS Core ja esta de pe, copie os arquivos novos para `/opt/mis-core-offline`
e rode o atualizador:

```bash
sudo cp /mnt/windows-migrations/pacote-vm-linux-dev/mis-core-nodered-dev.tar.gz /opt/mis-core-offline/
sudo cp /mnt/windows-migrations/pacote-vm-linux-dev/mis-core-nodered-dev.sha256 /opt/mis-core-offline/
sudo cp /mnt/windows-migrations/pacote-vm-linux-dev/update-nodered-nodes.sh /opt/mis-core-offline/

cd /opt/mis-core-offline
sha256sum -c mis-core-nodered-dev.sha256
sudo bash update-nodered-nodes.sh ./mis-core-nodered-dev.tar.gz
```

O script faz backup do volume `nodered_data`, sincroniza `node_modules` da
imagem nova e reinicia apenas o Node-RED.

## Validacao

```bash
cd /opt/mis-core-offline
docker exec mis-core-nodered sh -lc 'npm ls --depth=0 node-red-contrib-modbus node-red-contrib-influxdb node-red-node-mysql node-red-dashboard @flowfuse/node-red-dashboard || true'
```

Depois abra o editor do Node-RED e confira `Palette Manager -> Installed`.
