# Playbook de Release — do commit ao servidor OT

> **Uso**: cola-se a Parte 1 no agente Claude do VS Code (ele executa o build
> e testa local). A Parte 2 você roda no PC de dev com Docker Desktop. A
> Parte 3 você executa no servidor OT offline.

---

## Parte 1 — Prompt para colar no Claude do VS Code (build + subir local)

```
CONTEXTO:
Este repo é o mis-core (MIS industrial). Hoje tem 5 serviços Docker
para buildar, incluindo uma camada NOVA em FastAPI (backend-fastapi/)
que coexiste com Flask e Django sob prefixo /api/v2. Meu objetivo é
gerar imagens locais, rodar o stack inteiro via docker-compose, validar
health-checks, e só então empacotar tudo em tarball para deploy offline.

TAREFAS (executar em ordem — parar e me avisar se qualquer etapa falhar):

1) Verificar Docker Desktop rodando:
   docker info | Select-String "Server Version"
   docker compose version

2) Na RAIZ do repo (onde está docker-compose.yml novo):
   docker compose build --pull
   # "--pull" garante bases atualizadas (nginx:alpine, node:20-alpine,
   # python:3.11-slim, mysql:8.0, influxdb:1.8-alpine)

3) Conferir as 5 imagens locais com tag :dev:
   docker images | Select-String "mis-core"
   # Esperado ver:
   #   mis-core-frontend:dev
   #   mis-core-django:dev
   #   mis-core-flask:dev
   #   mis-core-fastapi:dev   <- NOVA
   #   mis-core-coletor:dev

4) Subir o stack completo (em background):
   docker compose up -d

5) Aguardar 60s e checar health de todos:
   Start-Sleep -Seconds 60
   docker compose ps
   # Todos precisam ficar "healthy" (exceto chronograf que não tem healthcheck).
   # Se alguém estiver "unhealthy", mostrar logs:
   #   docker compose logs --tail=100 <serviço>

6) Smoke-tests HTTP (tem que responder 200) — caminhos batem com nginx.conf
   do frontend: /api/ -> django, /flask-api/ -> flask (com rewrite removendo
   o prefixo), /api/v2/ -> fastapi:
   curl -f http://localhost:8080/health                  # nginx frontend
   curl -f http://localhost:8080/api/health/             # proxy django (django expõe /api/health/)
   curl -f http://localhost:8080/flask-api/health        # proxy flask  (nginx rewrite -> /api/health no flask)
   curl -f http://localhost:8080/api/v2/healthz          # proxy fastapi (NOVO)
   curl -f http://localhost:8080/api/v2/ready            # fastapi+influx (NOVO)

7) Abrir no navegador e conferir visualmente:
   http://localhost:8080              # home do MIS
   http://localhost:8080/api/v2/docs  # Swagger da camada v2 (NOVO)

8) Se tudo estiver verde, retaggear para as versões de release:
   docker tag mis-core-frontend:dev  mis-core-frontend:v14.0
   docker tag mis-core-django:dev    mis-core-django:v14.0
   docker tag mis-core-flask:dev     mis-core-flask:v14.0
   docker tag mis-core-fastapi:dev   mis-core-fastapi:v14.0
   docker tag mis-core-coletor:dev   mis-core-coletor:v14.0

9) Pré-baixar as imagens base que o compose offline também consome:
   docker pull mysql:8.0
   docker pull influxdb:1.8-alpine
   docker pull chronograf:1.8
   docker pull kapacitor:1.5

10) Reportar: quais containers ficaram healthy, qual a saída do curl
    no /api/v2/ready (tem que mostrar {"status":"ok","checks":{"influx":"ok"}}),
    e se a tela home carregou sem erro no console do navegador.

NÃO EXECUTAR: export_images.ps1 ainda. Eu quero rodar manualmente no
próximo passo depois de confirmar que está tudo verde.

DICAS:
- Se "docker compose build" falhar no frontend com timeout de pnpm,
  aumentar o timeout: docker compose build --build-arg NPM_TIMEOUT=300000
- Se o fastapi ficar unhealthy, verificar INFLUX_PASSWORD e se o influxdb
  subiu ANTES dele (depends_on já cobre, mas pode ter race em máquina lenta).
- Se der 404 em /api/v2/docs, conferir em docker logs mis-core-fastapi que
  os routers foram registrados com prefixo /api/v2.
```

---

## Parte 2 — No PC de dev: exportar o tarball

Depois que a Parte 1 terminou verde, você roda (PowerShell na pasta
`mis-core-offline/`):

```powershell
cd C:\Users\ermir\OneDrive\Documentos\GitHub\mis-core\mis-core\mis-core-offline

# Gera mis-core-images.tar (~1.5 a 2 GB)
pwsh .\export_images.ps1
```

O script empacota **9 imagens**: as 5 `mis-core-*:v*` retaggeadas + 4 bases
(mysql, influxdb, chronograf, kapacitor).

**Confirme que o arquivo foi criado:**

```powershell
Get-Item mis-core-images.tar | Select-Object Name, Length
# Esperado: algo como 1.8 GB
```

**O que levar no pendrive (ou compartilhamento SMB interno):**

```
mis-core-offline/
├── mis-core-images.tar        <- o tarball pesado
├── docker-compose.yml         <- compose de produção
├── import_images.ps1          <- script de import
├── export_images.ps1          <- (opcional, só para referência)
└── MANUAL_OFFLINE.md          <- manual curto
```

Copie a **pasta inteira** `mis-core-offline/` para o pendrive. Não copie só
o .tar — você precisa do compose e do script também.

---

## Parte 3 — No servidor OT offline: subir o stack

**Pré-requisitos no servidor OT** (conferir antes de colocar o pendrive):

- [ ] Docker Desktop (Windows Server) ou Docker Engine (Linux) instalado
- [ ] PowerShell 7+ disponível (`pwsh --version`)
- [ ] Portas livres: 81, 5002, 8001, 8002 (NOVO para FastAPI), 8087, 8889
- [ ] Firewall permite a rede do CLP/SCADA chegar nesta máquina
- [ ] Timezone do host: `America/Sao_Paulo`
- [ ] Disco: ≥ 20 GB livre em `C:\ProgramData\Docker` (volumes)

**Execução:**

```powershell
# 1) Copie a pasta mis-core-offline\ do pendrive para uma pasta local
#    (evita problemas de permissão ou pendrive sumindo no meio)
Copy-Item -Path E:\mis-core-offline -Destination C:\mis-core-offline -Recurse

cd C:\mis-core-offline

# 2) Subir (o script faz docker load + docker compose up -d)
pwsh .\import_images.ps1
```

O script vai imprimir as URLs finais. Deve sair algo como:

```
Deploy Concluido!
Frontend:   http://localhost:81
Django:     http://localhost:8001
Flask:      http://localhost:5002
FastAPI v2: http://localhost:8002/api/v2/docs
Coletor:    Rodando (Servico de Background - Sem URL)
```

**Validação pós-deploy** (cola no PowerShell do servidor):

```powershell
# Estado dos containers
docker compose ps

# Health da API nova
curl http://localhost:8002/api/v2/healthz
curl http://localhost:8002/api/v2/ready

# Health das APIs legadas
curl http://localhost:8001/api/health/
curl http://localhost:5002/api/health

# Frontend direto
curl http://localhost:81/health

# Frontend com reverse-proxy para FastAPI (o caminho que o usuário final usa)
curl http://localhost:81/api/v2/healthz
```

Se qualquer `curl` falhar, ver `docker logs <container>`. Os nomes são
`mis-core-frontend`, `mis-core-django`, `mis-core-flask`, `mis-core-fastapi`,
`mis-core-coletor`, `mis-core-mysql`, `mis-core-influxdb`.

**Primeira configuração** (uma vez só, no primeiro boot):

1. Abra `http://<ip-do-server>:81` no PC de um operador da rede OT.
2. Login admin / admin123 → **trocar a senha imediatamente**.
3. Ativar os layouts ISA-101 novos (no DevTools do navegador, F12 → Console):
   ```js
   localStorage.setItem("homeVariant", "v2");
   localStorage.setItem("sidebarVariant", "v2");
   location.reload();
   ```
4. Criar política de retenção no Influx (uma vez). Chronograf em
   `http://<ip-do-server>:8889/chronograf` → Query Admin:
   ```sql
   CREATE RETENTION POLICY raw_90d ON industrial_db DURATION 90d REPLICATION 1 DEFAULT;
   ```

---

## Parte 4 — Rollback (se der ruim em produção)

### Voltar uma versão específica

As tags são imutáveis (`:v1.0`, `:v2.0`). Se subirem uma `:v2.1` quebrada:

```powershell
# No compose, trocar :v2.1 -> :v2.0 e refazer up
cd C:\mis-core-offline
notepad docker-compose.yml     # editar a linha do serviço fastapi
docker compose up -d fastapi
```

### Derrubar tudo mantendo dados

```powershell
docker compose down
# Os volumes mysql_data e influxdb_data NÃO são apagados por padrão.
```

### Zerar completamente (⚠️ apaga banco)

```powershell
docker compose down -v
```

---

## Parte 5 — Troubleshooting relâmpago

| Sintoma                                          | Causa provável                         | Ação                                                                |
|--------------------------------------------------|----------------------------------------|----------------------------------------------------------------------|
| Frontend mostra tela branca                      | VITE_*_URL errado no build             | Rebuild com os args corretos (ver docker-compose.yml raiz)           |
| `/api/v2/ready` retorna 503                      | FastAPI não fala com Influx            | Checar `INFLUX_HOST=influxdb` e senha bate com `INFLUXDB_ADMIN_PASSWORD` |
| Container `mis-core-django` unhealthy            | MySQL ainda subindo                    | `docker compose restart django` (depends_on cobre, mas máquina lenta reinicia) |
| Coletor não conecta CLP                          | Firewall OT bloqueando                 | Liberar porta 4840 (OPC UA) do IP do coletor para o IP do CLP        |
| "no space left on device" no docker load         | `/var/lib/docker` cheio                | `docker system prune -a` (CUIDADO — limpa imagens não referenciadas) |
| Swagger `/api/v2/docs` dá 404                    | Prefixo do router errado               | `docker logs mis-core-fastapi` confirma routers em `/api/v2/*`       |

---

## Referências

- **Compose de dev** (builda do código): `./docker-compose.yml`
- **Compose de produção offline**: `./mis-core-offline/docker-compose.yml`
- **Manual de deploy detalhado**: `./docs/DEPLOY_OT.md`
- **ADR Strangler Pattern**: `./docs/adr/ADR-001-fastapi-strangler.md`
- **API v2 endpoints**: `./backend-fastapi/README.md`
