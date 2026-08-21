# Manual De Implementacao Offline - MIS Core

Este manual descreve como levar a aplicacao para o servidor OT sem internet.

## 1. Pre-Requisitos

No computador de desenvolvimento:

- Docker e Docker Compose funcionando.
- Codigo fonte atualizado.
- Imagens base disponiveis localmente ou acesso a internet para baixa-las.

No servidor OT `192.168.70.160`:

- Para VM nova: internet temporaria para instalar Docker, Docker Compose,
  Python 3 e Node.js via `bootstrap-linux.sh`.
- Para servidor ja preparado: Docker e Docker Compose instalados.
- Porta `8080` liberada para os clientes da rede.
- A pasta `mis-core-offline` copiada para o disco local.

## 2. Gerar O Pacote De Imagens

Na raiz do projeto:

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\mis-core-offline\export_images.ps1 -Version dev
```

Linux:

```bash
MIS_VERSION=dev bash mis-core-offline/export_images.sh
```

Arquivos gerados:

- `mis-core-images-dev.tar.gz`
- `mis-core-images-dev.sha256`
- `mis-core-images-dev.manifest.txt`

O manifesto lista as imagens empacotadas e o alvo `192.168.70.160:8080`.

## 3. Copiar Para O Servidor OT

Copie a pasta inteira:

```text
mis-core-offline/
```

Ela deve conter `docker-compose.yml`, `.env.example`, scripts e o arquivo `mis-core-images-*.tar.gz`.

## 4. Configurar `.env`

No servidor OT:

Windows:

```powershell
cd C:\mis-core-offline
Copy-Item .env.example .env
notepad .env
```

Linux:

```bash
cd /opt/mis-core-offline
cp .env.example .env
nano .env
```

Valores ja preparados para a rede OT:

```env
SERVER_HOST=192.168.70.160
FRONTEND_PORT=8080
DJANGO_ALLOWED_HOSTS=192.168.70.160,localhost,127.0.0.1,django,fastapi,frontend,coletor
CSRF_TRUSTED_ORIGINS=http://192.168.70.160:8080,http://localhost:8080,http://127.0.0.1:8080
CORS_ALLOWED_ORIGINS=http://192.168.70.160:8080,http://localhost:8080,http://127.0.0.1:8080
FASTAPI_CORS_ORIGINS=http://192.168.70.160:8080,http://localhost:8080,http://127.0.0.1:8080,http://frontend
```

Troque as senhas antes da operacao definitiva:

- `DJANGO_SECRET_KEY`
- `JWT_SECRET_KEY`
- `DJANGO_SUPERUSER_PASSWORD`
- `MYSQL_PASSWORD`
- `MYSQL_ROOT_PASSWORD`
- `INFLUXDB_PASSWORD`

## 5. Importar E Subir

VM Linux nova ou recriada:

```bash
sudo bash bootstrap-linux.sh
```

Com IP fixo aplicado pelo script:

```bash
sudo bash bootstrap-linux.sh --configure-network --interface ens18 --ip 192.168.70.160/24 --gateway 192.168.70.1 --dns 192.168.70.1
```

Servidor ja preparado:

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\import_images.ps1
```

Linux:

```bash
bash import-images.sh
```

Os scripts executam:

1. Validacao do tarball.
2. Verificacao de checksum.
3. `docker load`.
4. Validacao das tags contra `MIS_VERSION`.
5. `docker compose up -d`.
6. Listagem dos containers.

## 6. Validar A Aplicacao

No servidor:

```bash
docker compose ps
bash scripts/check.sh
```

No navegador de qualquer cliente da rede:

```text
http://192.168.70.160:8080/mis-core/
http://192.168.70.160:8080/mis-core-admin/
```

Endpoints uteis:

```text
http://192.168.70.160:8080/version.json
http://192.168.70.160:8080/api/health/
http://192.168.70.160:8080/api/v2/healthz
```

## 7. Atualizar Versao Em Campo

No desenvolvimento, gere novo pacote:

```bash
MIS_VERSION=2026.05.09 bash mis-core-offline/export_images.sh
```

No OT:

1. Copie o novo `mis-core-images-2026.05.09.tar.gz` e `.sha256`.
2. Altere `MIS_VERSION=2026.05.09` no `.env`.
3. Rode `bash import-images.sh` ou `.\import_images.ps1`.

## 8. Operacao

Comandos principais:

```bash
docker compose ps
docker compose logs -f --tail=200
docker compose restart frontend
docker compose restart django
docker compose down
docker compose up -d
```

## 9. Notas De Arquitetura

- O frontend escuta em `0.0.0.0:8080`, entao qualquer cliente da rede consegue acessar o host `192.168.70.160`.
- O admin Django passa pelo mesmo gateway nginx em `/mis-core-admin/`.
- O FastAPI ja e a camada preferencial para novos endpoints.
- O pacote offline nao sobe Flask. O caminho ativo usa Django para cadastro,
  ingestao e comandos do coletor, e FastAPI v2 para analytics/producao.
- Se a VM antiga foi apagada sem backup dos volumes Docker, os cadastros e o
  historico MySQL/InfluxDB precisam ser recriados.
