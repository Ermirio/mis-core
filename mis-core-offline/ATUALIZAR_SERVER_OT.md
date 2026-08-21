# Atualizacao Padrao Do Servidor OT

Este e o procedimento padrao para servidor OT que ja tem o MIS Core instalado.

Use `bootstrap-linux.sh` apenas em VM nova ou recriada. Para atualizacao normal,
use sempre `update-ot.sh`.

## 1. No Windows

Mantenha a pasta do pacote em:

```text
D:\migrations\pacote-vm-linux-dev
```

Essa pasta deve conter, no minimo:

```text
docker-compose.yml
.env.example
update-ot.sh
bootstrap-linux.sh
import-images.sh
scripts/
node-red/
mis-core-images-dev.tar.gz
mis-core-images-dev.sha256
```

Ela tambem pode conter overlays especificos:

```text
mis-core-django-dev.tar.gz
mis-core-django-dev.sha256
mis-core-nodered-dev.tar.gz
mis-core-nodered-dev.sha256
```

Quando existe um pacote geral novo, overlays com data anterior sao ignorados
automaticamente. O export completo tambem remove overlays obsoletos para evitar
que uma imagem incremental antiga sobrescreva o pacote novo.

## 2. Na VM Linux

Monte a pasta compartilhada, se ainda nao estiver montada:

```bash
sudo bash /mnt/windows-migrations/pacote-vm-linux-dev/mount-vmware-share.sh
```

Se ainda nao existir `/mnt/windows-migrations`, faca o mount manual uma vez:

```bash
sudo apt-get update
sudo apt-get install -y open-vm-tools fuse3
sudo mkdir -p /mnt/windows-migrations
sudo vmhgfs-fuse .host:/migrations /mnt/windows-migrations -o uid=$(id -u),gid=$(id -g),umask=022
```

## 3. Rodar Atualizacao

O comando padrao passa a ser sempre:

```bash
sudo bash /mnt/windows-migrations/pacote-vm-linux-dev/update-ot.sh
```

O script sincroniza o pacote para `/opt/mis-core-offline`, preserva o `.env`
do servidor, valida checksum, carrega apenas imagens diferentes e reinicia os
servicos afetados.

## 4. Validar

```bash
cd /opt/mis-core-offline
docker compose ps
bash scripts/check.sh 192.168.70.160
```

Acessos:

```text
http://192.168.70.160:8080/mis-core/
http://192.168.70.160:8080/mis-core-admin/
http://192.168.70.160:8080/api/v2/docs
http://192.168.70.160:8080/mc-portainer/
```

O Portainer nao exige login no MIS Core. Em um volume novo, o update cria o
administrador nativo `admin` automaticamente, sem a janela de setup de cinco
minutos. Consulte a senha inicial com:

```bash
sudo awk -F= '/^PORTAINER_ADMIN_PASSWORD=/{print $2}' /opt/mis-core-offline/.env
```

Depois disso, usuarios e senhas sao gerenciados somente pelo Portainer. A senha
do `.env` e apenas a credencial inicial e nao redefine uma conta existente.

## Hub Central

O acesso direto pela VM OT funciona apenas com o comando de atualizacao acima.
Se os usuarios entram pelo proxy central da rede `.71`, atualize tambem a
configuracao desse nginx usando `proxy-reverse-nginx-central.conf`, incluido no
pacote. O arquivo adiciona `/mc-portainer/` ao MIS Core e preserva o caminho
`/portainer/` legado.

Compare o arquivo com a configuracao ativa do Hub, aplique os blocos
`mc_portainer_via_frontend` e `/mc-portainer/`, depois valide e recarregue:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Se o nginx central roda em container, execute os comandos equivalentes dentro
do container antes de recria-lo.

## O Que O Script Nao Faz

- Nao apaga volumes Docker.
- Nao apaga MySQL.
- Nao apaga InfluxDB.
- Nao sobrescreve o `.env` existente.
- Nao baixa imagens da internet.

## VM Nova

Se a VM foi recriada ou apagada, rode:

```bash
cd /mnt/windows-migrations/pacote-vm-linux-dev
sudo bash bootstrap-linux.sh
```

Depois disso, as proximas atualizacoes voltam para:

```bash
sudo bash /mnt/windows-migrations/pacote-vm-linux-dev/update-ot.sh
```
