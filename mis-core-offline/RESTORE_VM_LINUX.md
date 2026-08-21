# Restore De VM Linux - MIS Core Offline

Este roteiro e para quando a VM do servidor OT foi perdida inteira.

## O Que Este Restore Recupera

- Sistema operacional preparado com Docker, Docker Compose, Python 3, Node.js e utilitarios.
- Imagens Docker do MIS Core carregadas a partir de `mis-core-images-<VERSAO>.tar.gz`.
- Containers do MIS Core subindo automaticamente.
- Servico `mis-core-offline.service` habilitado no boot da VM.

## O Que Nao Volta Sem Backup

Se os volumes da VM antiga foram apagados, estes dados nao voltam pelo tarball de imagens:

- Cadastros do MySQL: fabrica, area, linha, equipamento, variaveis, usuarios, permissoes.
- Historico do InfluxDB: estados, medicoes, analises, dados de producao.
- Dados persistidos do Grafana, Node-RED, EMQX e ferramentas auxiliares.

Nesse caso, a aplicacao sobe vazia e o recadastro precisa seguir a hierarquia:

```text
Fabrica -> Area -> Linha -> Equipamento -> Variavel
```

Essa hierarquia e importante porque os novos dados gravados no Influx devem carregar as tags `factory`, `area`, `line`, `equipment` e a variavel analisada.

## Arquitetura Padrao Da Rede OT

Padrao atual usado pelo pacote:

```text
Rede OT:      192.168.70.0/24
Servidor MIS: 192.168.70.160
Gateway:      192.168.70.1
App:          http://192.168.70.160:8080/mis-core/
Admin:        http://192.168.70.160:8080/mis-core-admin/
FastAPI:      http://192.168.70.160:8080/api/v2/docs
Chronograf:   http://192.168.70.160:8889
Portainer:    http://192.168.70.160:8080/mc-portainer/
```

Portas principais:

| Porta | Uso |
|---|---|
| `8080` | Frontend, admin e gateway interno das APIs |
| `8001` | Django direto, diagnostico |
| `8002` | FastAPI direto, diagnostico |
| `8087` | InfluxDB direto |
| `3308` | MySQL direto |
| `8889` | Chronograf |
| `3001` | Grafana |
| `1880` | Node-RED |
| `1883`, `8083`, `18083` | EMQX |

## 1. Gerar Um Pacote Novo No Desenvolvimento

Nao use um tarball antigo se ele foi gerado antes da correcao de hierarquia/equipamento.
Gere de novo para garantir que as imagens levem o codigo atual e a imagem custom `mis-core-nodered`.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\mis-core-offline\export_images.ps1 -Version dev
```

Linux:

```bash
MIS_VERSION=dev bash mis-core-offline/export_images.sh
```

Arquivos esperados dentro de `mis-core-offline/`:

```text
mis-core-images-dev.tar.gz
mis-core-images-dev.sha256
mis-core-images-dev.manifest.txt
```

## 2. Copiar Para A VM Nova

Copie a pasta inteira `mis-core-offline` para a VM.

Destino recomendado:

```text
/opt/mis-core-offline
```

Se estiver copiando primeiro para um pendrive ou home do usuario, nao tem problema:
o bootstrap copia a pasta para `/opt/mis-core-offline`.

## 3. Rodar Bootstrap Na VM

Com a VM tendo acesso a internet para instalar Docker/Node/Python:

```bash
cd /caminho/onde/esta/mis-core-offline
sudo bash bootstrap-linux.sh
```

Com IP fixo aplicado automaticamente:

```bash
cd /caminho/onde/esta/mis-core-offline
sudo bash bootstrap-linux.sh --configure-network --interface ens18 --ip 192.168.70.160/24 --gateway 192.168.70.1 --dns 192.168.70.1
```

Troque `ens18` pelo nome real da interface da VM. Para descobrir:

```bash
ip link
ip route
```

Se o Linux ja tiver Docker/Compose instalados e voce quiser so subir o pacote:

```bash
cd /opt/mis-core-offline
bash import-images.sh
```

## 4. Validar

```bash
cd /opt/mis-core-offline
docker compose ps
bash scripts/check.sh 192.168.70.160
```

Links:

```text
http://192.168.70.160:8080/mis-core/
http://192.168.70.160:8080/mis-core-admin/
http://192.168.70.160:8080/api/v2/docs
```

## 5. Gateway Principal

Se houver um gateway principal na frente do servidor MIS, ele deve encaminhar para:

```text
/mis-core/        -> http://192.168.70.160:8080/mis-core/
/mis-core-admin/  -> http://192.168.70.160:8080/mis-core-admin/
/mis-core/api/    -> http://192.168.70.160:8080/api/
/mis-core/api/v2/ -> http://192.168.70.160:8080/api/v2/
/static/          -> http://192.168.70.160:8080/static/
```

O exemplo completo fica em:

```text
mis-core-offline/nginx-hub.conf.example
```

Para uso direto, sem gateway principal, nao precisa mexer nesse arquivo.

## 6. Pos-Restore

1. Entrar no admin Django.
2. Cadastrar novamente fabrica, areas, linhas, equipamentos e variaveis.
3. Validar o coletor OPC UA.
4. Conferir no Chronograf/Influx se os pontos novos estao entrando com tags de hierarquia.
5. Verificar analytics por linha/equipamento antes de liberar operacao.

Com VM apagada sem backup, nao rode backfill: nao ha historico antigo para enriquecer.
