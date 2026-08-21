# MIS Core Offline - Rede OT

Pacote autocontido para instalar o MIS Core em servidor sem internet.

Ambiente alvo configurado:

- Host OT: `192.168.70.160`
- Interface: `http://192.168.70.160:8080/mis-core/`
- Admin: `http://192.168.70.160:8080/mis-core-admin/`
- FastAPI: `http://192.168.70.160:8080/api/v2/docs`
- Chronograf: `http://192.168.70.160:8889`
- Portainer: `http://192.168.70.160:8080/mc-portainer/`

## Conteudo Da Pasta

```text
mis-core-offline/
  docker-compose.yml
  .env.example
  export_images.ps1
  export_images.sh
  import_images.ps1
  import-images.sh
  bootstrap-linux.sh              # prepara VM Linux nova e sobe o stack
  update-ot.sh                    # atualizacao padrao em servidor ja instalado
  update-nodered-nodes.sh         # atualiza nos em VM ja existente
  node-red/                       # config + Dockerfile da imagem custom
    Dockerfile                    # FROM nodered/node-red:4.0.9-20 + npm install
    package.json                  # baseline industrial + extras do DEV
    settings.js                   # AUTO-COPIADO do ../node-red/settings.js
  scripts/check.sh
  scripts/install.sh
  nginx-hub.conf.example
  proxy-reverse-nginx-central.conf # configuracao completa do Hub central
  RESTORE_VM_LINUX.md
  MANUAL_OFFLINE.md
  mis-core-images-<VERSION>.tar.gz
  mis-core-images-<VERSION>.sha256
  mis-core-images-<VERSION>.manifest.txt
```

O compose usa `pull_policy: never`, portanto o servidor OT nao tenta baixar nada da internet. Todas as imagens precisam estar no tarball.

### Portainer No Hub

O pacote inclui `portainer/portainer-ce:2.39.5-alpine` e o item Portainer na
secao Ferramentas do Hub. O nginx interno apenas encaminha `/mc-portainer/` ao
container; nao consulta nem depende da autenticacao do Django.

Os scripts criam automaticamente o administrador nativo `admin` em um volume
novo, evitando que a janela de configuracao inicial expire. A senha inicial fica
em `PORTAINER_ADMIN_PASSWORD` no `.env` protegido e pode ser consultada com:

```bash
sudo awk -F= '/^PORTAINER_ADMIN_PASSWORD=/{print $2}' /opt/mis-core-offline/.env
```

Depois do primeiro login, altere a senha no proprio Portainer. A partir dai,
somente a autenticacao nativa da ferramenta controla quem pode administrar
containers, imagens, volumes e redes; a senha do `.env` nao sobrescreve uma
conta que ja existe no volume `portainer_data`.

O Portainer monta `/var/run/docker.sock`, portanto sua conta administrativa
equivale a acesso administrativo ao Docker da VM. Nao foi publicada uma porta
direta; use sempre `/mc-portainer/` pelo Hub.

### Imagem Node-RED custom

A imagem `mis-core-nodered:<VERSION>` substitui a imagem oficial pura do
Node-RED e e construida durante o `export_images.ps1` ou `export_images.sh`
com:

- O `settings.js` canonico (adminAuth via Django, Projects, contextStorage,
  debug logging) copiado de `node-red/settings.js` na raiz do repo.
- Um `package.json` com baseline industrial obrigatorio: Modbus, MySQL,
  InfluxDB 1.x/1.8 Flux/2.0, dashboards, S7, OPC UA, PCCC, Ethernet/IP,
  PostgreSQL, SQLite e componentes de UI.
- Nos extras extraidos em tempo real do container `mis-core-nodered` em DEV,
  quando ele estiver rodando. O baseline nunca e removido por um DEV
  incompleto.

Se voce instalar um novo no via palette no DEV, basta rodar `export_images.ps1`
de novo. A proxima imagem ja vem com ele baked-in, somada ao baseline.

Em VM nova, o volume do Node-RED nasce com os modulos da imagem. Em VM ja
rodando, o volume `nodered_data` pode esconder o `/data` da imagem nova; nesse
caso rode:

```bash
cd /opt/mis-core-offline
sudo bash update-nodered-nodes.sh
```

Se o arquivo `mis-core-nodered-dev.tar.gz` estiver na pasta do pacote, o
`import-images.sh` carrega essa imagem automaticamente depois do pacote geral.
Para VM ja em execucao, rode o `update-nodered-nodes.sh` em seguida para
sincronizar o volume existente.

## Gerar Ou Atualizar O Pacote

No computador de desenvolvimento, com Docker funcionando:

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\mis-core-offline\export_images.ps1 -Version dev
```

Linux:

```bash
MIS_VERSION=dev bash mis-core-offline/export_images.sh
```

O script faz build das imagens da aplicacao, valida tags, salva o pacote dentro de `mis-core-offline` e gera checksum.

## Instalar No Servidor OT

Copie a pasta `mis-core-offline` inteira para o servidor `192.168.70.160`.

### VM Linux nova ou recriada

Se a VM foi apagada ou nasceu limpa, use o bootstrap. Ele instala Docker,
Docker Compose, Python 3, Node.js, cria `.env`, carrega as imagens e sobe o
stack:

```bash
cd /caminho/onde/esta/mis-core-offline
sudo bash bootstrap-linux.sh
```

Com IP fixo da rede OT:

```bash
sudo bash bootstrap-linux.sh --configure-network --interface ens18 --ip 192.168.70.160/24 --gateway 192.168.70.1 --dns 192.168.70.1
```

Veja tambem: `RESTORE_VM_LINUX.md`.

Importante: se a VM antiga foi apagada sem backup de volumes, o tarball das
imagens restaura a aplicacao, mas nao restaura cadastros nem historico do
MySQL/InfluxDB.

### Levar o pacote via VMware Shared Folder

No Windows, coloque o pacote em `D:\migrations`. No VMware, habilite:

```text
VM Settings -> Options -> Shared Folders -> Always enabled
Host path: D:\migrations
Name: migrations
```

Dentro da VM Linux, monte com:

```bash
sudo bash mount-vmware-share.sh
cd /mnt/windows-migrations/pacote-vm-linux-dev
sudo bash bootstrap-linux.sh
```

### Servidor com Docker ja instalado

Para servidor OT que ja esta instalado, o procedimento padrao e:

```bash
sudo bash /mnt/windows-migrations/pacote-vm-linux-dev/update-ot.sh
```

O `update-ot.sh` sincroniza a pasta padrao para `/opt/mis-core-offline`,
preserva o `.env`, valida checksum, carrega apenas imagens diferentes e
reinicia somente os servicos afetados.

Veja tambem: `ATUALIZAR_SERVER_OT.md`.

### Primeira subida manual, se nao usar bootstrap

Windows:

```powershell
cd C:\mis-core-offline
Copy-Item .env.example .env
notepad .env
powershell -ExecutionPolicy Bypass -File .\import_images.ps1
```

Linux:

```bash
cd /opt/mis-core-offline
cp .env.example .env
nano .env
bash import-images.sh
```

Revise obrigatoriamente as senhas marcadas com `TROQUE` antes do uso definitivo.

## Validacao

```bash
docker compose ps
bash scripts/check.sh
```

Ou pelo navegador de qualquer cliente da rede OT:

```text
http://192.168.70.160:8080/mis-core/
http://192.168.70.160:8080/mis-core-admin/
http://192.168.70.160:8080/mc-portainer/
```

## Portas Expostas

| Porta | Uso |
|---|---|
| `8080` | Interface, admin e gateway das APIs |
| `8080` | Portainer via `/mc-portainer/` (sem porta administrativa direta) |
| `8001` | Django direto, diagnostico |
| `8002` | FastAPI direto, diagnostico |
| `8087` | InfluxDB direto |
| `3308` | MySQL direto |
| `8889` | Chronograf |
| `3001` | Grafana |
| `1880` | Node-RED |
| `1883` | EMQX MQTT |
| `8083` | EMQX WebSocket |
| `18083` | EMQX Dashboard |

## Observacao Sobre Backend

O pacote offline nao sobe nem exporta `mis-core-flask`. O caminho ativo usa Django para cadastro, ingestao e comandos do coletor, e FastAPI v2 para os endpoints novos de analytics e producao.
