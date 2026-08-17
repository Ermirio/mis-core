#!/bin/bash
# ============================================================
# save-changeover-v9.8.sh
#
# Gera o pacote COMPLETO de deploy v9.8 (Recipe Monitor + Redis +
# Django + Frontend) no padrao do servidor OT (dist/deploy/).
#
# O que muda vs v9.7:
#   * Django: migration 0017_recipe_monitor + endpoint
#     /api/recipe-monitor/formato/<id>/sincronizar/ + 2 campos
#     em Variavel (unidade, tolerancia) + permissao TIM/Eng/Coord
#   * Frontend: novo componente ReceitaMonitorContent + rota
#     /receita-monitor + item de menu + nginx faz proxy de
#     /recipe-monitor/* para o container mis-recipe-monitor
#   * Imagens novas: mis-recipe-intelligent:v9.8 + redis:7-alpine
#   * docker-compose: +mis-recipe-monitor +mis-redis
#
# Saida:
#   dist/deploy/mis-changeover-v9.8.tar          (4 imagens)
#   dist/deploy/docker-compose-v9.8.yaml         (compose completo)
#   dist/deploy/carregar-v9.8.sh                 (importa + sobe)
#   dist/deploy/RECIPE-MONITOR-v9.8.README.md    (instrucoes)
# ============================================================
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANGEOVER_DIR="$ROOT_DIR/mis-change-over"
RECIPE_DIR="$CHANGEOVER_DIR/Backend/recipe_monitor_service"
OUTDIR="$ROOT_DIR/dist/deploy"
TAR_FILE="$OUTDIR/mis-changeover-v9.8.tar"
COMPOSE_FILE="$OUTDIR/docker-compose-v9.8.yaml"
LOAD_SCRIPT="$OUTDIR/carregar-v9.8.sh"
README_FILE="$OUTDIR/RECIPE-MONITOR-v9.8.README.md"

mkdir -p "$OUTDIR"

echo "================================================="
echo " MIS Changeover v9.8 - Build & Save (Pacote Completo)"
echo "================================================="

# ────────────────────────────────────────────────────────────
# [1/6] Build mis-backend:v9.8
# ────────────────────────────────────────────────────────────
echo ""
echo " [1/6] Build mis-backend:v9.8 ..."
docker build -t mis-backend:v9.8 "$CHANGEOVER_DIR/Backend"
echo " [OK] mis-backend:v9.8"

# ────────────────────────────────────────────────────────────
# [2/6] Build mis-frontend:v9.8
#   Passa REACT_APP_RECIPE_MONITOR_URL vazio -> componente cai no
#   fallback que detecta o host atual + /recipe-monitor. Isso casa
#   com o proxy embutido no nginx do frontend.
# ────────────────────────────────────────────────────────────
echo ""
echo " [2/6] Build mis-frontend:v9.8 (com proxy /recipe-monitor/* embutido)..."
docker build \
    --build-arg REACT_APP_RECIPE_MONITOR_URL= \
    -t mis-frontend:v9.8 \
    "$CHANGEOVER_DIR/Frontend"
echo " [OK] mis-frontend:v9.8"

# ────────────────────────────────────────────────────────────
# [3/6] Build mis-recipe-intelligent:v9.8
# ────────────────────────────────────────────────────────────
echo ""
echo " [3/6] Build mis-recipe-intelligent:v9.8 ..."
docker build -t mis-recipe-intelligent:v9.8 "$RECIPE_DIR"
echo " [OK] mis-recipe-intelligent:v9.8"

# ────────────────────────────────────────────────────────────
# [3b/6] Garantir redis:7-alpine local (pull)
# ────────────────────────────────────────────────────────────
echo ""
echo " [3b/6] Garantindo redis:7-alpine local..."
docker pull redis:7-alpine

# ────────────────────────────────────────────────────────────
# [4/6] Salvar todas as 4 imagens em um unico TAR
# ────────────────────────────────────────────────────────────
echo ""
echo " [4/6] Salvando 4 imagens em $TAR_FILE ..."
docker save \
    mis-frontend:v9.8 \
    mis-backend:v9.8 \
    mis-recipe-intelligent:v9.8 \
    redis:7-alpine \
    -o "$TAR_FILE"

SIZE=$(du -sh "$TAR_FILE" | cut -f1)
echo " [OK] $TAR_FILE ($SIZE)"

# ────────────────────────────────────────────────────────────
# [5/6] Gerar docker-compose-v9.8.yaml
#   Compatível com o padrão do servidor OT:
#     - MySQL no host (host.docker.internal:3307)
#     - frontend na porta 3005, backend na 8000
#   Acrescenta: mis-recipe-monitor (porta 8100) + mis-redis (6379)
# ────────────────────────────────────────────────────────────
echo ""
echo " [5/6] Gerando $COMPOSE_FILE ..."
cat > "$COMPOSE_FILE" << 'COMPOSE_EOF'
# ============================================================
# docker-compose-v9.8.yaml — MIS Change Over + Recipe Monitor
# ============================================================
# IMPORTANTE: Este arquivo SUBSTITUI o docker-compose.yml atual.
# O carregar-v9.8.sh faz backup do antigo antes de substituir.
#
# Requisitos no host OT:
#   - MySQL rodando em host.docker.internal:3307 (db 'ips')
#   - Network 'shared-network' criada (docker network create shared-network)
# ============================================================
version: '3.8'

services:
  # === Frontend (React + nginx que tambem faz proxy do recipe-monitor) ===
  frontend:
    image: mis-frontend:v9.8
    pull_policy: never
    container_name: mis_frontend_container
    ports:
      - "3005:80"
    depends_on:
      - backend
      - mis-recipe-monitor
    networks:
      - app_network
      - shared-network

  # === Backend (Django) — migrations rodam automaticamente no entrypoint ===
  backend:
    image: mis-backend:v9.8
    pull_policy: never
    container_name: mis_backend_container
    ports:
      - "8000:8000"
    environment:
      DJANGO_SETTINGS_MODULE: digitalfactory.settings
      DJANGO_SECRET_KEY: sua_chave_secreta_aqui
      DJANGO_DEBUG: "True"
      DJANGO_ALLOWED_HOSTS: "*"
      DJANGO_CSRF_TRUSTED_ORIGINS: "http://localhost:3000,http://127.0.0.1:3000,http://192.168.15.13:3000,http://192.168.30.71:3000,http://192.168.30.78:3000,http://10.168.79:3000"

      DB_ENGINE: django.db.backends.mysql
      DB_NAME: ips
      DB_USER: root
      DB_PASSWORD: ixvq10A@10
      DB_HOST: host.docker.internal
      DB_PORT: 3307

      USE_X_FORWARDED_HOST: "true"
      SECURE_PROXY_SSL_HEADER: "HTTP_X_FORWARDED_PROTO,https"

      LM_STUDIO_URL: "http://host.docker.internal:1234"

    networks:
      - app_network
      - shared-network

  # === Redis (cache + pub/sub do Recipe Monitor) ===
  mis-redis:
    image: redis:7-alpine
    pull_policy: never
    container_name: mis-redis
    command: redis-server --save "" --appendonly no --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    networks:
      - app_network

  # === Recipe Monitor (FastAPI + asyncua) ===
  mis-recipe-monitor:
    image: mis-recipe-intelligent:v9.8
    pull_policy: never
    container_name: mis-recipe-monitor
    environment:
      DJANGO_BASE_URL: http://backend:8000
      REDIS_URL: redis://mis-redis:6379/0
      OPC_CONFIG_TTL_SECONDS: "60"
      OPC_SUBSCRIPTION_INTERVAL_MS: "500"
      HISTORY_MAX_POINTS: "60"
      LINES_PRELOAD: ""
      LOG_LEVEL: INFO
      CORS_ORIGINS: "http://localhost:3005,http://localhost:3000"
      TZ: America/Sao_Paulo
    ports:
      - "8100:8100"
    depends_on:
      mis-redis:
        condition: service_healthy
      backend:
        condition: service_started
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 20s
    networks:
      - app_network

volumes: {}

networks:
  app_network:
    driver: bridge
  shared-network:
    external: true
COMPOSE_EOF
echo " [OK] $COMPOSE_FILE"

# ────────────────────────────────────────────────────────────
# [6/6] Gerar carregar-v9.8.sh — script de deploy no servidor OT
# ────────────────────────────────────────────────────────────
echo ""
echo " [6/6] Gerando $LOAD_SCRIPT ..."
cat > "$LOAD_SCRIPT" << 'LOAD_EOF'
#!/bin/bash
# ============================================================
# carregar-v9.8.sh — Deploy MIS Changeover v9.8 no servidor OT
#
# O que faz:
#   1. docker load das 4 imagens (backend, frontend, recipe-monitor, redis)
#   2. Backup do docker-compose.yml atual
#   3. Substitui pelo docker-compose-v9.8.yaml
#   4. Sobe os 4 containers (migrations Django rodam automaticamente)
#   5. Valida health de Django, Redis e Recipe Monitor
#
# Uso: bash carregar-v9.8.sh
# Rollback automatico em caso de falha critica.
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TAR_FILE="$SCRIPT_DIR/mis-changeover-v9.8.tar"
NEW_COMPOSE="$SCRIPT_DIR/docker-compose-v9.8.yaml"
TARGET_COMPOSE="$SCRIPT_DIR/../docker-compose.yml"
BACKUP_COMPOSE="$SCRIPT_DIR/../docker-compose.yml.bkp.$(date +%Y%m%d-%H%M%S)"

echo ""
echo "=== MIS Changeover v9.8 - Deploy Offline ==="
echo ""

# ── Pré-checagens ──────────────────────────────────────────
if [ ! -f "$TAR_FILE" ]; then
    echo "ERRO: $TAR_FILE nao encontrado."
    exit 1
fi
if [ ! -f "$NEW_COMPOSE" ]; then
    echo "ERRO: $NEW_COMPOSE nao encontrado."
    exit 1
fi
if [ ! -f "$TARGET_COMPOSE" ]; then
    echo "AVISO: $TARGET_COMPOSE nao existe — sera criado do zero."
fi

# Garante que a shared-network existe (compose v9.7 ja usa)
if ! docker network inspect shared-network >/dev/null 2>&1; then
    echo "Criando network 'shared-network'..."
    docker network create shared-network
fi

# ── 1) Carregar imagens ────────────────────────────────────
echo "[1/5] Carregando imagens do $TAR_FILE ..."
docker load -i "$TAR_FILE"
echo "    OK"

# Confere que as 4 imagens estao mesmo presentes
for IMG in mis-backend:v9.8 mis-frontend:v9.8 mis-recipe-intelligent:v9.8 redis:7-alpine; do
    if ! docker image inspect "$IMG" >/dev/null 2>&1; then
        echo "ERRO: imagem $IMG nao foi carregada."
        exit 1
    fi
done

# ── 2) Backup do compose atual e substituir ────────────────
echo ""
echo "[2/5] Atualizando $TARGET_COMPOSE ..."
if [ -f "$TARGET_COMPOSE" ]; then
    cp "$TARGET_COMPOSE" "$BACKUP_COMPOSE"
    echo "    backup salvo em $BACKUP_COMPOSE"
fi
cp "$NEW_COMPOSE" "$TARGET_COMPOSE"
echo "    OK"

# ── 3) Subir todos os containers ───────────────────────────
echo ""
echo "[3/5] Subindo containers (recipe-monitor + redis sao novos)..."
sudo docker compose -f "$TARGET_COMPOSE" up -d
echo "    OK"

# ── 4) Aguardar Django (migrations rodam automatico) ───────
echo ""
echo "[4/5] Aguardando Django ficar saudavel (migrations aplicam aqui)..."
for i in $(seq 1 60); do
    if docker exec mis_backend_container curl -fs http://localhost:8000/api/health/ >/dev/null 2>&1; then
        echo "    Django OK (migrations 0017_recipe_monitor aplicada)"
        # Confirma a migration nova
        if docker logs mis_backend_container 2>&1 | grep -q "0017_recipe_monitor"; then
            echo "    Confirmado: 0017_recipe_monitor visivel nos logs"
        fi
        break
    fi
    sleep 2
done

# ── 5) Validar Recipe Monitor + Redis ──────────────────────
echo ""
echo "[5/5] Validando Recipe Monitor e Redis..."

# Redis
if docker exec mis-redis redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "    Redis OK"
else
    echo "    AVISO: Redis nao respondeu PONG"
fi

# Recipe Monitor
for i in $(seq 1 30); do
    if docker exec mis-recipe-monitor python -c \
       "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')" \
       >/dev/null 2>&1; then
        echo "    Recipe Monitor OK"
        break
    fi
    sleep 2
done

# ── Conclusao ──────────────────────────────────────────────
echo ""
echo "=========================================================="
echo " Deploy v9.8 concluido"
echo "=========================================================="
docker ps --format 'table {{.Names}}\t{{.Status}}'
echo ""
echo "Endpoints:"
echo "  Frontend (SPA):       http://<host>:3005/mis-change-over/"
echo "  Frontend -> Recipe:   http://<host>:3005/recipe-monitor/health"
echo "  Backend Django:       http://<host>:8000/api/health/"
echo "  Recipe Monitor:       http://<host>:8100/health"
echo "  Recipe Monitor docs:  http://<host>:8100/docs"
echo ""
echo "Proximos passos no Django Admin (http://<host>:8000/admin/):"
echo "  1. Criar grupos (se nao existirem): TIM, Engenharia, Coordenacao"
echo "  2. Cadastrar unidade e tolerancia nas Variaveis Mestras"
echo "  3. Adicionar operadores TIM/Engenharia/Coordenacao para sincronizar receita"
echo ""
echo "--- Rollback para v9.7 (se necessario) ---"
echo "  cp $BACKUP_COMPOSE $TARGET_COMPOSE"
echo "  sudo docker compose -f $TARGET_COMPOSE stop mis-recipe-monitor mis-redis || true"
echo "  sudo docker compose -f $TARGET_COMPOSE rm -f mis-recipe-monitor mis-redis || true"
echo "  sudo docker compose -f $TARGET_COMPOSE up -d --no-deps backend frontend"
echo "  # A migration 0017 fica aplicada (campos nullable, nao atrapalham)"
echo ""
LOAD_EOF
chmod +x "$LOAD_SCRIPT"
echo " [OK] $LOAD_SCRIPT"

# ────────────────────────────────────────────────────────────
# README
# ────────────────────────────────────────────────────────────
cat > "$README_FILE" << 'README_EOF'
# MIS Changeover v9.8 — Recipe Monitor + Redis

Pacote completo para deploy offline no servidor OT.

## Conteúdo deste diretório

| Arquivo | Descrição |
|---|---|
| `mis-changeover-v9.8.tar` | 4 imagens Docker: backend, frontend, recipe-monitor, redis |
| `docker-compose-v9.8.yaml` | Compose completo (substitui o atual no deploy) |
| `carregar-v9.8.sh` | Script automatizado: load + deploy + healthcheck |
| `RECIPE-MONITOR-v9.8.README.md` | Este arquivo |

## O que vai mudar no servidor OT

| Componente | Mudança |
|---|---|
| `mis_backend_container` | Imagem nova `mis-backend:v9.8`. Migration `0017_recipe_monitor` aplicada automaticamente pelo entrypoint. |
| `mis_frontend_container` | Imagem nova `mis-frontend:v9.8` com novo menu **Monitor de Receita** e proxy embutido para `/recipe-monitor/*`. |
| `mis-recipe-monitor` (novo) | FastAPI + asyncua na porta 8100. Lê CLPs via OPC UA e mantém estado em Redis. |
| `mis-redis` (novo) | Cache + pub/sub do Recipe Monitor. Sem persistência (cache puro, 256MB LRU). |

## Como deployar

```bash
# 1. Copiar o pacote para o servidor OT
scp -r mis-changeover-v9.8.tar docker-compose-v9.8.yaml carregar-v9.8.sh \
    usuario@servidor-ot:~/mis-deploy/deploy/

# 2. No servidor OT
cd ~/mis-deploy/deploy/
chmod +x carregar-v9.8.sh
bash carregar-v9.8.sh
```

O script faz tudo: load das imagens, backup do compose atual, substitui pelo novo,
sobe os 4 containers, aguarda saúde do Django (que roda migrate automaticamente)
e valida Redis + Recipe Monitor.

## Pré-requisitos no servidor OT

- Docker + docker compose
- MySQL rodando no host em `host.docker.internal:3307` (db `ips`)
- Network Docker `shared-network` (o script cria se não existir)

## Pós-deploy obrigatório

No Django Admin (http://servidor:8000/admin/):

1. **Criar grupos** (se ainda não existem):
   - `TIM`
   - `Engenharia`
   - `Coordenacao`

2. **Cadastrar tolerância e unidade** nas `Variável Mestra` que serão monitoradas.
   Sem tolerância, o classificador só distingue `normal` vs `alarme`.

3. **Adicionar operadores autorizados** aos grupos acima. Só eles podem clicar
   em "Atualizar receita com valores do CLP".

## Endpoints disponíveis após o deploy

| URL | Quem usa |
|---|---|
| http://host:3005/mis-change-over/ | Operador (SPA React) |
| http://host:3005/recipe-monitor/health | Frontend → backend (proxy interno) |
| http://host:8000/api/health/ | Django (porta direta) |
| http://host:8000/admin/ | Admin Django |
| http://host:8100/health | Recipe Monitor (porta direta) |
| http://host:8100/docs | Swagger do Recipe Monitor |

## Rollback para v9.7

Se algo der errado:

```bash
# 1. Restaura compose anterior (carregar-v9.8.sh imprime o backup gerado)
cp ../docker-compose.yml.bkp.<timestamp> ../docker-compose.yml

# 2. Para os serviços novos
sudo docker compose -f ../docker-compose.yml stop mis-recipe-monitor mis-redis
sudo docker compose -f ../docker-compose.yml rm -f mis-recipe-monitor mis-redis

# 3. Volta backend+frontend para v9.7
sudo docker compose -f ../docker-compose.yml up -d --no-deps backend frontend
```

A migration 0017 fica aplicada — campos novos são nullable e não atrapalham
o v9.7. Se quiser revertê-la também:

```bash
docker exec mis_backend_container python manage.py migrate ips 0016_validacaoqualidade_troca_nullable
```

## Troubleshooting

| Sintoma | Causa | Solução |
|---|---|---|
| Frontend abre mas Monitor de Receita mostra "Erro ao carregar" | Recipe Monitor não conseguiu chamar Django | `docker logs mis-recipe-monitor` — confirmar `DJANGO_BASE_URL` |
| Badge "OPC UA Offline" persistente | Linha não tem CLP cadastrado OU sem rede para o CLP | Verificar `Equipamento.conexao_opcua` no admin |
| Sincronizar retorna 403 | Operador não está em TIM/Eng/Coord | Adicionar ao grupo no admin |
| WebSocket não conecta | nginx do frontend sem suporte WS | Confirmar que `Frontend/nginx.conf` tem `map $http_upgrade $connection_upgrade` |
README_EOF

# ────────────────────────────────────────────────────────────
# Conclusao
# ────────────────────────────────────────────────────────────
echo ""
echo "================================================="
echo " PACOTE COMPLETO GERADO"
echo "================================================="
ls -lh "$OUTDIR" | grep -E "v9\.8" || true
echo ""
echo "Para deploy no servidor OT, copiar para la:"
echo "  $TAR_FILE"
echo "  $COMPOSE_FILE"
echo "  $LOAD_SCRIPT"
echo "  $README_FILE"
echo ""
echo "No servidor OT (no diretorio onde tem docker-compose.yml e a pasta deploy/):"
echo "  cd <diretorio>/deploy/"
echo "  bash carregar-v9.8.sh"
echo ""
echo "================================================="
