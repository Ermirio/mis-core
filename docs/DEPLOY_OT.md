# Deploy do mis-core em Rede OT Offline

> **Para quem é este guia**: técnico de automação / engenheiro de processo que
> vai subir o mis-core num servidor isolado na rede de chão de fábrica (OT),
> sem acesso à internet, sem acesso a Docker Hub, sem acesso a PyPI.

---

## 1. O problema que este guia resolve

Uma rede OT típica (chão de fábrica) é **air-gapped** — firewall bloqueia
qualquer coisa que não esteja num whitelist curto (CLPs, historian, servidor
local). Isso significa três coisas práticas na hora de deploy:

| Limitação da rede OT           | Impacto no deploy             | Saída que este guia adota      |
|--------------------------------|-------------------------------|--------------------------------|
| Sem Docker Hub                 | `docker pull` não funciona    | `docker save` + tarball        |
| Sem PyPI / npm                 | `pip install`/`npm i` falham  | Tudo pré-empacotado na imagem  |
| Sem repositório Git            | `git clone` não funciona      | Código vai no próprio tarball  |
| Disco pequeno no server OT     | Não dá pra caber "tudo"       | Apenas runtime, sem dev tools  |

> **Analogia WCM**: isto é um "kaizen de setup". Se você não pode levar
> ferramentas todo dia, você monta um kit que vai com você e resolve 100%
> dos casos no turno.

---

## 2. Estratégia recomendada: tarball único (docker save/load)

É a abordagem já montada em [`mis-core-offline/`](../mis-core-offline/)
(scripts PowerShell + compose). Funciona assim:

```
┌─────────────────────────┐                   ┌──────────────────────────┐
│ PC de desenvolvimento   │                   │ Servidor OT (offline)    │
│ (com internet)          │                   │                          │
│                         │   pendrive /      │                          │
│ docker compose build    │   compartilhamento│ docker load -i *.tar     │
│ export_images.ps1  ────►│ ─────────────────►│ docker compose up -d     │
│ (gera mis-core-*.tar)   │                   │                          │
└─────────────────────────┘                   └──────────────────────────┘
```

### Passo 1 — No PC de dev (com internet): build + export

```powershell
# Da raiz do repo
cd C:\...\mis-core

# Builda TODAS as imagens (inclui a nova FastAPI v2)
docker compose build

# Retaga com as versões que o offline espera (evita divergência)
docker tag mis-core-frontend:dev    mis-core-frontend:v1.0
docker tag mis-core-django:dev      mis-core-django:v1.0
docker tag mis-core-flask:dev       mis-core-flask:v1.1
docker tag mis-core-fastapi:dev     mis-core-fastapi:v2.0
docker tag mis-core-coletor:dev     mis-core-coletor:v1.0

# Baixa as imagens de base que o offline também usa
docker pull mysql:8.0
docker pull influxdb:1.8-alpine
docker pull chronograf:1.8
docker pull kapacitor:1.5

# Gera o tarball (~1.5 a 2 GB)
cd mis-core-offline
pwsh ./export_images.ps1
```

O resultado é um arquivo `mis-core-images.tar`. Copie **ele + a pasta inteira
`mis-core-offline/`** para o servidor (pendrive, compartilhamento SMB interno,
fita, whatever).

### Passo 2 — No servidor OT: import + up

```powershell
# Em PowerShell, na pasta mis-core-offline/
cd C:\mis-core-offline

pwsh ./import_images.ps1
```

O script:
1. Faz `docker load -i mis-core-images.tar` (carrega todas as imagens),
2. Confere com `docker images | findstr mis-core`,
3. Dá `docker-compose up -d`,
4. Imprime as URLs de acesso.

**Acesso final:**

| Serviço               | URL local do servidor OT                          |
|-----------------------|---------------------------------------------------|
| Frontend              | `http://<server>:81`                              |
| API Django legado     | `http://<server>:8001/api/`                       |
| API Flask legado      | `http://<server>:5002/api/`                       |
| API FastAPI v2 (novo) | `http://<server>:8002/api/v2/docs` (Swagger)      |
| Chronograf (admin DB) | `http://<server>:8889/chronograf`                 |

> O **frontend** no nginx interno já faz reverse-proxy: do ponto de vista do
> navegador, todas as APIs aparecem como `/api/django/`, `/api/flask/` e
> `/api/v2/` no mesmo host:port do frontend. As portas 8001/5002/8002 ficam
> expostas só para debug direto.

---

## 3. Estratégia alternativa A — mirror interno de PyPI/npm

Quando a empresa já mantém um **Nexus/Artifactory** interno e você não quer
empacotar runtime fixo (porque precisa atualizar pacotes Python com frequência).

Nos `Dockerfile`s, adicione antes do `pip install`:

```dockerfile
ARG PIP_INDEX_URL=https://nexus.empresa.com/repository/pypi/simple
ARG PIP_TRUSTED_HOST=nexus.empresa.com
ENV PIP_INDEX_URL=$PIP_INDEX_URL \
    PIP_TRUSTED_HOST=$PIP_TRUSTED_HOST
```

E no `docker-compose.yml`:

```yaml
services:
  fastapi:
    build:
      context: ./backend-fastapi
      args:
        PIP_INDEX_URL: https://nexus.empresa.com/repository/pypi/simple
        PIP_TRUSTED_HOST: nexus.empresa.com
```

**Trade-off**: requer Nexus operacional e sincronização periódica com PyPI.
Não recomendado para o primeiro deploy — fique no tarball.

---

## 4. Estratégia alternativa B — wheels pré-baixadas

Quando você quer `docker build` rodando no servidor OT (ex.: para fazer um
patch pequeno de código lá mesmo) mas sem acesso a PyPI.

### No PC de dev (com internet):

```bash
cd backend-fastapi
mkdir -p ./wheels
pip download \
  --dest ./wheels \
  -r requirements.txt   # ou pyproject dependency list

# Copie ./wheels/ junto com o código
```

### Dockerfile (backend-fastapi/Dockerfile):

```dockerfile
COPY wheels/ /tmp/wheels/
RUN pip install --no-index --find-links=/tmp/wheels/ -e .
```

**Trade-off**: funciona, mas é frágil — qualquer `arch` diferente (ARM vs x86)
quebra, e atualizar dependência vira ritual.

---

## 5. Checklist pré-deploy (não pule!)

Antes de rodar `import_images.ps1` no servidor OT:

- [ ] **Docker Desktop / Docker Engine instalado** no servidor. Se o server
      é Windows Server, precisa do Docker EE ou WSL2+Docker Desktop
      (verificar licenças). Se for Linux, o script `.ps1` pode virar `.sh`
      trivial (a lógica é a mesma).
- [ ] **Portas liberadas** no firewall do Windows/Linux: 81, 5002, 8001,
      8002, 8087, 8889 (interno), 3308 (se for acessar MySQL direto).
- [ ] **Timezone no servidor** está `America/Sao_Paulo` — o compose força
      via env `TZ`, mas o host também precisa bater senão os logs mentem.
- [ ] **Disco disponível** ≥ 20 GB para os volumes (mysql_data, influxdb_data).
      InfluxDB cresce rápido se retenção não for configurada; criar política
      de retenção (ex.: 90 dias raw, agregados mantidos indefinidamente).
- [ ] **Rede OPC UA acessível** pelo servidor onde o coletor vai rodar —
      o firewall deve permitir a porta do CLP/SCADA (tipicamente 4840).
- [ ] **Segredos trocados**: `DJANGO_SECRET_KEY`, `JWT_SECRET`,
      `MYSQL_ROOT_PASSWORD`, `INFLUXDB_ADMIN_PASSWORD`, `admin123`.
      **Os defaults do compose são inseguros**. Use um `.env` com os valores
      reais e referencie via `${VAR}` no compose.
- [ ] **Backup prévio** se este é um server que já tinha outra versão rodando.

---

## 6. Operação pós-deploy

### Ver logs

```powershell
# Todos os serviços, tempo real
docker compose -f mis-core-offline/docker-compose.yml logs -f

# Serviço específico
docker logs -f mis-core-coletor      # ver reconexões OPC
docker logs -f mis-core-fastapi      # ver requests de analytics
```

### Validar health

```powershell
curl http://localhost:81/health                      # frontend nginx
curl http://localhost:8001/api/health/               # django
curl http://localhost:5002/api/health                # flask
curl http://localhost:8002/api/v2/healthz            # fastapi (liveness)
curl http://localhost:8002/api/v2/ready              # fastapi (valida Influx)
```

Se qualquer uma falhar, rode `docker compose ps` — serviço "unhealthy" deve
ter a causa nos logs.

### Atualizar uma imagem (hotfix)

Repete o ciclo **só para a imagem alterada**:

```powershell
# No dev
docker build -t mis-core-fastapi:v2.1 ./backend-fastapi
docker save -o fastapi-v2.1.tar mis-core-fastapi:v2.1

# No OT (pendrive chega)
docker load -i fastapi-v2.1.tar
# Edite o compose apontando :v2.0 -> :v2.1
docker compose up -d fastapi
```

### Rollback

O padrão de versionamento com tags explícitas (`:v2.0`, `:v2.1`) permite
voltar trivialmente: edita o compose, `up -d <serviço>`. **Nunca use `:latest`**
em produção OT.

---

## 7. Problemas comuns (FAQ)

**"`docker load` dá `no space left on device`"**
O `/var/lib/docker` está cheio. Rode `docker system prune -a` (⚠️ isso apaga
imagens não-referenciadas) ou aumente a partição.

**"Frontend mostra tela branca / não consegue falar com API"**
Provavelmente o `VITE_*_URL` foi hardcoded em outra coisa durante o build.
Verifique no DevTools (F12) → Network qual URL está sendo chamada. Se estiver
errada, rebuilde o frontend com `VITE_*_URL` corretos (ver `docker-compose.yml`
na raiz, seção `frontend.build.args`).

**"FastAPI responde 503 em /api/v2/ready"**
Ele consegue se comunicar com o Influx? `docker logs mis-core-fastapi` mostra
stacktrace. Checar `INFLUX_HOST` bate com o nome do serviço (`influxdb`) e se
o credential é o mesmo do `INFLUXDB_ADMIN_PASSWORD`.

**"Coletor ficou travado sem reconectar após CLP reiniciar"**
Esperado apenas na v1 antiga. A partir desta versão, o coletor tem watchdog
+ circuit breaker + OfflineBuffer SQLite WAL — ver `coletor/coletor.py`.
Verificar `docker logs mis-core-coletor | Select-String "reconnect"`.

**"Migrations Django falharam no primeiro up"**
Normal em máquinas lentas: o Django tenta conectar antes do MySQL subir.
Rode `docker compose restart django` — o `depends_on: condition:
service_healthy` já garante ordem correta na segunda tentativa.

**"Como faço para o frontend usar o FastAPI em vez do Flask para analytics?"**
No navegador do usuário final, abra DevTools e rode:
```js
localStorage.setItem("homeVariant", "v2");    // Home ISA-101 nova
localStorage.setItem("sidebarVariant", "v2"); // Sidebar ISA-101 nova
location.reload();
```
Nenhum rebuild necessário — feature-flags locais. Para reverter:
`localStorage.removeItem("homeVariant")`.

---

## 8. Próximos passos (pós-deploy)

1. **Política de retenção no Influx** — rode via Chronograf:
   ```sql
   CREATE RETENTION POLICY raw_90d ON industrial_db DURATION 90d REPLICATION 1 DEFAULT;
   CREATE RETENTION POLICY agg_inf  ON industrial_db DURATION INF REPLICATION 1;
   ```
2. **Backup automatizado** — cron/agendador diário:
   - `mysqldump` de `mis_core_db`,
   - `influxd backup` de `industrial_db`,
   - Guardar em pasta de rede OT (NAS).
3. **Monitoramento de disco** — configurar alerta quando `/var/lib/docker`
   passar de 80%.
4. **Segurança**: trocar os passwords default, considerar montar volumes em
   disco dedicado, limitar portas expostas no firewall.
5. **Migração Strangler** — começar a apontar componentes do frontend para
   `/api/v2/*` e medir. Ver [ADR-001](./adr/ADR-001-fastapi-strangler.md).

---

## 9. Arquivos relevantes

| Arquivo                                       | Função                                          |
|-----------------------------------------------|-------------------------------------------------|
| `./docker-compose.yml`                        | Compose de DEV (builda do código local)         |
| `./mis-core-offline/docker-compose.yml`       | Compose de PROD (consome imagens do tarball)    |
| `./mis-core-offline/export_images.ps1`        | Gera `mis-core-images.tar` no PC de dev         |
| `./mis-core-offline/import_images.ps1`        | Carrega tarball + sobe stack no server OT       |
| `./mis-core-offline/MANUAL_OFFLINE.md`        | Manual operacional original (curto)             |
| `./frontend-react/nginx.conf`                 | Reverse-proxy interno do container frontend     |
| `./backend-fastapi/README.md`                 | Referência da camada v2 (endpoints + fórmulas)  |
| `./docs/adr/ADR-001-fastapi-strangler.md`     | Decisão arquitetural da migração                |

---

*Última revisão: conteúdo baseado na release com FastAPI v2 + Sidebar/Home
ISA-101. Se o arquivo `docker-compose.yml` ou os Dockerfiles mudarem de
estrutura, atualizar também este guia.*
