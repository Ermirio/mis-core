#!/bin/bash
# ============================================================
# save-changeover-v10.0.sh
#
# Gera o pacote COMPLETO de deploy v10.0 (Recipe Monitor + Redis +
# Django + Frontend) para o hub central (rede OT, 192.168.30.71).
#
# O que muda vs v9.9:
#   * Django: migration 0017_recipe_monitor + endpoint
#     /api/recipe-monitor/formato/<id>/sincronizar/ + 2 campos
#     em Variavel (unidade, tolerancia) + permissao TIM/Eng/Coord
#   * Frontend: novo componente ReceitaMonitorContent + rota
#     /receita-monitor + item de menu "Monitor de Receita"
#   * Imagens NOVAS: mis-recipe-intelligent:v10.0 + redis:7-alpine
#   * docker-compose: +mis-recipe-monitor +mis-redis
#   * nginx central: +location /recipe-monitor/ (REST + WS)
#
# Saidas em dist/deploy/:
#   mis-changeover-v10.0.tar             (4 imagens)
#   docker-compose-v10.0.yaml            (compose completo)
#   proxy-reverse-nginx-v10.0.conf       (nginx central completo)
#   .env-v10.0                           (env completo)
#   carregar-v10.0.sh                    (deploy automatico)
#   RECIPE-MONITOR-v10.0.README.md       (instrucoes)
# ============================================================
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANGEOVER_DIR="$ROOT_DIR/mis-change-over"
RECIPE_DIR="$CHANGEOVER_DIR/Backend/recipe_monitor_service"
OUTDIR="$ROOT_DIR/dist/deploy"
TAR_FILE="$OUTDIR/mis-changeover-v10.0.tar"
COMPOSE_FILE="$OUTDIR/docker-compose-v10.0.yaml"
NGINX_FILE="$OUTDIR/proxy-reverse-nginx-v10.0.conf"
ENV_FILE="$OUTDIR/.env-v10.0"
LOAD_SCRIPT="$OUTDIR/carregar-v10.0.sh"
README_FILE="$OUTDIR/RECIPE-MONITOR-v10.0.README.md"

mkdir -p "$OUTDIR"

echo "================================================="
echo " MIS Changeover v10.0 - Build & Save (Pacote Completo)"
echo "================================================="

# ────────────────────────────────────────────────────────────
# [1/5] Build mis-backend:v10.0
# ────────────────────────────────────────────────────────────
echo ""
echo " [1/5] Build mis-backend:v10.0 ..."
docker build -t mis-backend:v10.0 "$CHANGEOVER_DIR/Backend"
echo " [OK] mis-backend:v10.0"

# ────────────────────────────────────────────────────────────
# [2/5] Build mis-frontend:v10.0
# ────────────────────────────────────────────────────────────
echo ""
echo " [2/5] Build mis-frontend:v10.0 ..."
docker build \
    --build-arg REACT_APP_RECIPE_MONITOR_URL= \
    -t mis-frontend:v10.0 \
    "$CHANGEOVER_DIR/Frontend"
echo " [OK] mis-frontend:v10.0"

# ────────────────────────────────────────────────────────────
# [3/5] Build mis-recipe-intelligent:v10.0
# ────────────────────────────────────────────────────────────
echo ""
echo " [3/5] Build mis-recipe-intelligent:v10.0 ..."
docker build -t mis-recipe-intelligent:v10.0 "$RECIPE_DIR"
echo " [OK] mis-recipe-intelligent:v10.0"

# ────────────────────────────────────────────────────────────
# [3b/5] Garantir redis:7-alpine local (pull)
# ────────────────────────────────────────────────────────────
echo ""
echo " [3b/5] Garantindo redis:7-alpine local..."
docker pull redis:7-alpine

# ────────────────────────────────────────────────────────────
# [4/5] Salvar todas as 4 imagens em um unico TAR
# ────────────────────────────────────────────────────────────
echo ""
echo " [4/5] Salvando 4 imagens em $TAR_FILE ..."
docker save \
    mis-frontend:v10.0 \
    mis-backend:v10.0 \
    mis-recipe-intelligent:v10.0 \
    redis:7-alpine \
    -o "$TAR_FILE"

SIZE=$(du -sh "$TAR_FILE" | cut -f1)
echo " [OK] $TAR_FILE ($SIZE)"

# ────────────────────────────────────────────────────────────
# Validacao dos arquivos auxiliares (compose, env, nginx ja existem)
# ────────────────────────────────────────────────────────────
for f in "$COMPOSE_FILE" "$NGINX_FILE" "$ENV_FILE"; do
    if [ ! -f "$f" ]; then
        echo " ERRO: arquivo auxiliar nao encontrado: $f"
        echo "   (esse arquivo deveria estar no repo em dist/deploy/)"
        exit 1
    fi
done

# ────────────────────────────────────────────────────────────
# [5/5] Gerar carregar-v10.0.sh — deploy no servidor OT
# ────────────────────────────────────────────────────────────
echo ""
echo " [5/5] Gerando $LOAD_SCRIPT ..."
cat > "$LOAD_SCRIPT" << 'LOAD_EOF'
#!/bin/bash
# ============================================================
# carregar-v10.0.sh — Deploy MIS Changeover v10.0 no hub central
#
# Layout esperado no servidor OT:
#   ~/mis-hub/
#     docker-compose.yml
#     .env
#     proxy-reverse/nginx.conf
#     deploy/                          <-- este diretorio
#       mis-changeover-v10.0.tar
#       docker-compose-v10.0.yaml
#       proxy-reverse-nginx-v10.0.conf
#       .env-v10.0
#       carregar-v10.0.sh
#
# Uso:
#   cd ~/mis-hub/deploy/
#   bash carregar-v10.0.sh
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HUB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

TAR_FILE="$SCRIPT_DIR/mis-changeover-v10.0.tar"
NEW_COMPOSE="$SCRIPT_DIR/docker-compose-v10.0.yaml"
NEW_NGINX="$SCRIPT_DIR/proxy-reverse-nginx-v10.0.conf"
NEW_ENV="$SCRIPT_DIR/.env-v10.0"

TARGET_COMPOSE="$HUB_DIR/docker-compose.yml"
TARGET_NGINX="$HUB_DIR/proxy-reverse/nginx.conf"
TARGET_ENV="$HUB_DIR/.env"

TS=$(date +%Y%m%d-%H%M%S)
BACKUP_COMPOSE="$TARGET_COMPOSE.bkp.$TS"
BACKUP_NGINX="$TARGET_NGINX.bkp.$TS"
BACKUP_ENV="$TARGET_ENV.bkp.$TS"

echo ""
echo "=== MIS Changeover v10.0 - Deploy Offline ==="
echo "Hub dir: $HUB_DIR"
echo ""

# ── Pre-checagens ──────────────────────────────────────────
for f in "$TAR_FILE" "$NEW_COMPOSE" "$NEW_NGINX" "$NEW_ENV"; do
    if [ ! -f "$f" ]; then
        echo "ERRO: arquivo do pacote ausente: $f"
        exit 1
    fi
done

if [ ! -d "$HUB_DIR/proxy-reverse" ]; then
    echo "ERRO: $HUB_DIR/proxy-reverse/ nao encontrado."
    echo "       Este script espera o layout padrao do mis-hub."
    exit 1
fi

# ── 1) Carregar imagens ────────────────────────────────────
echo "[1/6] Carregando 4 imagens de $TAR_FILE ..."
docker load -i "$TAR_FILE"
for IMG in mis-backend:v10.0 mis-frontend:v10.0 mis-recipe-intelligent:v10.0 redis:7-alpine; do
    if ! docker image inspect "$IMG" >/dev/null 2>&1; then
        echo "    ERRO: imagem $IMG nao foi carregada."
        exit 1
    fi
    echo "    OK: $IMG"
done

# ── 2) Backup do compose atual e substituir ────────────────
echo ""
echo "[2/6] Atualizando $TARGET_COMPOSE ..."
if [ -f "$TARGET_COMPOSE" ]; then
    cp "$TARGET_COMPOSE" "$BACKUP_COMPOSE"
    echo "    backup: $BACKUP_COMPOSE"
fi
cp "$NEW_COMPOSE" "$TARGET_COMPOSE"
echo "    OK"

# ── 3) Backup do nginx atual e substituir ──────────────────
echo ""
echo "[3/6] Atualizando $TARGET_NGINX ..."
if [ -f "$TARGET_NGINX" ]; then
    cp "$TARGET_NGINX" "$BACKUP_NGINX"
    echo "    backup: $BACKUP_NGINX"
fi
cp "$NEW_NGINX" "$TARGET_NGINX"
echo "    OK"

# ── 4) Atualizar .env (preserva valores customizados) ──────
echo ""
echo "[4/6] Atualizando $TARGET_ENV ..."
if [ -f "$TARGET_ENV" ]; then
    cp "$TARGET_ENV" "$BACKUP_ENV"
    echo "    backup: $BACKUP_ENV"
    # Acrescenta vars do Recipe Monitor se ainda nao existem
    for VAR in RECIPE_MONITOR_LINES_PRELOAD RECIPE_MONITOR_LOG_LEVEL RECIPE_MONITOR_CORS_ORIGINS; do
        if ! grep -q "^$VAR=" "$TARGET_ENV"; then
            VAL=$(grep "^$VAR=" "$NEW_ENV" | head -1)
            if [ -n "$VAL" ]; then
                echo "" >> "$TARGET_ENV"
                echo "# Adicionado automaticamente por carregar-v10.0.sh" >> "$TARGET_ENV"
                echo "$VAL" >> "$TARGET_ENV"
                echo "    + adicionado: $VAR"
            fi
        else
            echo "    = mantido: $VAR (ja existia)"
        fi
    done
else
    cp "$NEW_ENV" "$TARGET_ENV"
    echo "    .env criado do zero"
fi

# ── 5) Subir os 4 containers do mis-change-over + recipe ───
echo ""
echo "[5/6] Subindo containers (recipe-monitor + redis sao novos)..."
cd "$HUB_DIR"
sudo docker compose up -d \
    mis-redis \
    mis-recipe-monitor \
    mis-changeover-backend \
    mis-changeover-frontend
echo "    OK"

# ── 5b) Reload do nginx proxy (sem restart) ────────────────
echo ""
echo "[5b/6] Reload do nginx-proxy (sem downtime)..."
if docker exec mis-core-proxy nginx -t 2>&1 | tail -2; then
    docker exec mis-core-proxy nginx -s reload
    echo "    OK"
else
    echo "    AVISO: nginx -t falhou. Verifique $TARGET_NGINX."
    echo "    Rollback: cp $BACKUP_NGINX $TARGET_NGINX && docker exec mis-core-proxy nginx -s reload"
fi

# ── 6) Validar health ──────────────────────────────────────
echo ""
echo "[6/6] Validando saude dos servicos..."

# Django (migrations rodam aqui automaticamente)
echo "    aguardando Django saudavel (migration 0017_recipe_monitor)..."
for i in $(seq 1 60); do
    if docker exec mis-changeover-backend curl -fs http://localhost:8000/api/health/ >/dev/null 2>&1; then
        echo "      Django OK"
        if docker logs mis-changeover-backend 2>&1 | grep -q "0017_recipe_monitor"; then
            echo "      Confirmado: 0017_recipe_monitor aplicada"
        fi
        break
    fi
    sleep 2
done

# Redis
if docker exec mis-redis redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "    Redis OK"
else
    echo "    AVISO: Redis nao respondeu PONG"
fi

# Recipe Monitor (espera healthcheck)
echo "    aguardando Recipe Monitor saudavel..."
for i in $(seq 1 30); do
    if docker exec mis-recipe-monitor python -c \
       "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')" \
       >/dev/null 2>&1; then
        echo "    Recipe Monitor OK"
        break
    fi
    sleep 2
done

# Via proxy central
echo "    testando Recipe Monitor via proxy central..."
PROXY_PORT=$(grep -E "^PROXY_HOST_PORT=" "$TARGET_ENV" | cut -d= -f2 || echo "3000")
if curl -fs "http://localhost:${PROXY_PORT}/recipe-monitor/health" >/dev/null 2>&1; then
    echo "    Recipe Monitor via proxy OK (http://localhost:${PROXY_PORT}/recipe-monitor/health)"
else
    echo "    AVISO: /recipe-monitor/health via proxy nao respondeu"
fi

# ── Conclusao ──────────────────────────────────────────────
echo ""
echo "=========================================================="
echo " Deploy v10.0 concluido"
echo "=========================================================="
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E "(NAMES|mis-)"
echo ""
echo "Endpoints (substitua localhost pelo IP do hub, ex.: 192.168.30.71):"
echo "  Hub:                  http://localhost:${PROXY_PORT}/"
echo "  Change Over (SPA):    http://localhost:${PROXY_PORT}/mis-change-over/"
echo "  Recipe Monitor REST:  http://localhost:${PROXY_PORT}/recipe-monitor/health"
echo "  Recipe Monitor docs:  http://localhost:${PROXY_PORT}/recipe-monitor/docs"
echo "  Change Over admin:    http://localhost:${PROXY_PORT}/mis-change-over-admin/"
echo ""
echo "Proximos passos no Django Admin:"
echo "  1. Criar grupos: TIM, Engenharia, Coordenacao (se nao existem)"
echo "  2. Cadastrar 'unidade' e 'tolerancia' nas Variaveis Mestras"
echo "  3. Adicionar operadores autorizados aos grupos acima"
echo ""
echo "--- Rollback automatico ---"
echo "  cp $BACKUP_COMPOSE $TARGET_COMPOSE"
echo "  cp $BACKUP_NGINX $TARGET_NGINX"
echo "  cp $BACKUP_ENV $TARGET_ENV"
echo "  cd $HUB_DIR"
echo "  sudo docker compose stop mis-recipe-monitor mis-redis"
echo "  sudo docker compose rm -f mis-recipe-monitor mis-redis"
echo "  sudo docker compose up -d --no-deps mis-changeover-backend mis-changeover-frontend"
echo "  docker exec mis-core-proxy nginx -s reload"
echo ""
LOAD_EOF
chmod +x "$LOAD_SCRIPT"
echo " [OK] $LOAD_SCRIPT"

# ────────────────────────────────────────────────────────────
# README
# ────────────────────────────────────────────────────────────
cat > "$README_FILE" << 'README_EOF'
# MIS Changeover v10.0 — Recipe Monitor + Redis

Pacote completo para deploy offline no hub central do servidor OT.

## Conteudo do pacote (dist/deploy/)

| Arquivo | Tamanho aprox. | Descricao |
|---|---|---|
| `mis-changeover-v10.0.tar` | ~650 MB | 4 imagens Docker (backend, frontend, recipe-monitor, redis) |
| `docker-compose-v10.0.yaml` | ~17 KB | Compose completo do hub central, com Recipe Monitor + Redis |
| `proxy-reverse-nginx-v10.0.conf` | ~26 KB | nginx central completo com locations /recipe-monitor/* |
| `.env-v10.0` | ~3 KB | .env completo com vars do Recipe Monitor |
| `carregar-v10.0.sh` | ~7 KB | Script automatizado: load + substituir + subir + validar |
| `RECIPE-MONITOR-v10.0.README.md` | este arquivo | Documentacao |

## O que muda vs v9.9

| Componente | Mudanca |
|---|---|
| `mis-changeover-backend` | Imagem nova `mis-backend:v10.0`. Migration `0017_recipe_monitor` aplica automaticamente. Endpoint novo: `PATCH /api/recipe-monitor/formato/<id>/sincronizar/` |
| `mis-changeover-frontend` | Imagem nova `mis-frontend:v10.0`. Novo item "Monitor de Receita" no menu superior. Rota nova: `/receita-monitor` |
| `mis-recipe-monitor` (NOVO) | FastAPI + asyncua. Le tags OPC continuamente. Porta 8100 (nao publicada — acesso via proxy). |
| `mis-redis` (NOVO) | Cache + pub/sub. Sem persistencia. 256 MB LRU. |
| `proxy-reverse/nginx.conf` | +2 locations: `/recipe-monitor/` (REST) e `/recipe-monitor/ws/` (WebSocket). |
| `.env` | +3 vars opcionais para Recipe Monitor (tem defaults). |

## Como deployar

```bash
# 1. Copiar para o servidor OT
scp -r dist/deploy/* usuario@192.168.30.71:~/mis-hub/deploy/

# 2. No servidor OT
cd ~/mis-hub/deploy/
chmod +x carregar-v10.0.sh
bash carregar-v10.0.sh
```

O script `carregar-v10.0.sh` faz tudo automaticamente:

1. Carrega as 4 imagens
2. Backup de `docker-compose.yml`, `nginx.conf`, `.env`
3. Substitui pelos novos (preservando vars customizadas no .env)
4. Sobe os containers (incluindo Redis + Recipe Monitor)
5. Aguarda Django (migrations rodam aqui)
6. Reload do nginx proxy sem downtime
7. Valida saude de tudo
8. Imprime endpoints + comandos de rollback

## Pre-requisitos no servidor OT

- Docker + docker compose
- Hub central ja rodando (v9.9 ou anterior)
- Layout padrao: `~/mis-hub/{docker-compose.yml,.env,proxy-reverse/}`

## Pos-deploy obrigatorio

No Django Admin (http://192.168.30.71:3000/mis-change-over-admin/):

1. **Criar grupos** (se nao existem):
   - `TIM`
   - `Engenharia`
   - `Coordenacao`

2. **Cadastrar tolerancia e unidade** nas `Variavel Mestra` que serao monitoradas

3. **Adicionar operadores autorizados** aos grupos acima

## Endpoints disponiveis apos deploy

Substitua `localhost:3000` pelo IP/porta do seu hub (ex.: `192.168.30.71:3000`).

| URL | Quem usa |
|---|---|
| http://host:3000/mis-change-over/ | Operador (SPA React) |
| http://host:3000/mis-change-over-admin/ | Admin Django |
| http://host:3000/mis-change-over-api/ | API Django (uso interno do React) |
| http://host:3000/recipe-monitor/health | Health do Recipe Monitor |
| http://host:3000/recipe-monitor/docs | Swagger do Recipe Monitor |
| http://host:3000/recipe-monitor/linhas/L01/snapshot | Estado atual de uma linha |
| ws://host:3000/recipe-monitor/ws/linhas/L01/stream | WebSocket (push real-time) |

## Rollback automatico

O `carregar-v10.0.sh` salva backups e imprime os comandos exatos de rollback
ao final. Em resumo:

```bash
# Restaurar configs
cp ~/mis-hub/docker-compose.yml.bkp.<timestamp> ~/mis-hub/docker-compose.yml
cp ~/mis-hub/proxy-reverse/nginx.conf.bkp.<timestamp> ~/mis-hub/proxy-reverse/nginx.conf
cp ~/mis-hub/.env.bkp.<timestamp> ~/mis-hub/.env

# Parar novos servicos
cd ~/mis-hub/
sudo docker compose stop mis-recipe-monitor mis-redis
sudo docker compose rm -f mis-recipe-monitor mis-redis

# Voltar backend+frontend
sudo docker compose up -d --no-deps mis-changeover-backend mis-changeover-frontend
docker exec mis-core-proxy nginx -s reload
```

A migration `0017_recipe_monitor` fica aplicada — campos novos sao nullable
e nao atrapalham v9.9.

## Troubleshooting

| Sintoma | Causa | Solucao |
|---|---|---|
| `/recipe-monitor/health` retorna 502 | Container nao subiu | `docker logs mis-recipe-monitor` |
| Frontend mostra "Erro ao carregar" no monitor | Recipe Monitor nao consegue chamar Django | Verificar `DJANGO_BASE_URL` no container |
| "OPC UA Offline" persistente | Linha sem CLP cadastrado OU rede sem alcance ao CLP | Verificar `Equipamento.conexao_opcua` no admin |
| Sincronizar retorna 403 | Operador nao esta em TIM/Eng/Coord | Adicionar ao grupo no admin |
| Reload nginx falhou | Syntax error no nginx.conf | `docker exec mis-core-proxy nginx -t` para ver erro |
README_EOF

# ────────────────────────────────────────────────────────────
# Conclusao
# ────────────────────────────────────────────────────────────
echo ""
echo "================================================="
echo " PACOTE v10.0 GERADO"
echo "================================================="
ls -lh "$OUTDIR" | grep -E "v10\.0" || true
echo ""
echo "Copie para o servidor OT (192.168.30.71):"
echo "  scp -r dist/deploy/*v10.0* usuario@192.168.30.71:~/mis-hub/deploy/"
echo ""
echo "No servidor OT:"
echo "  cd ~/mis-hub/deploy/"
echo "  bash carregar-v10.0.sh"
echo ""
echo "================================================="
