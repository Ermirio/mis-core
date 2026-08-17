# Recipe Monitor — Operações (subir do zero)

Este guia leva do zero até a tela do **Monitor de Receita** funcionando
em produção. Três componentes precisam estar de pé:

  1. **Django** (`mis-change-over`) — fornece config OPC, formatos e
     recebe o sincronismo
  2. **Redis** — cache de estado + pub/sub
  3. **mis-recipe-intelligent** — este serviço (FastAPI + asyncua)

Mais o **Frontend React** com o novo componente integrado.

---

## 1. Django — aplicar migration nova

Da raiz do `mis-change-over/Backend`:

```bash
python manage.py migrate ips 0017_recipe_monitor
```

A migration é puramente aditiva (`AddField` nullable + `CreateModel`).
Não destrói nem altera campos existentes.

### Cadastrar tolerância e unidade nas variáveis

Pelo Django Admin, edite cada `Variavel` que você quer monitorar:

  - **Unidade** — texto curto (`rpm`, `bar`, `L`, `°C`, ...)
  - **Tolerância** — opcional. Sem ela, o classifier só decide
    `normal` vs `alarme` (sem zona de "atenção"). Com ela:
      - `|atual − receita| ≤ tolerância` → **NORMAL**
      - `|atual − receita| ≤ 2·tolerância` → **ATENÇÃO**
      - `|atual − receita| > 2·tolerância` → **ALARME**

Para variáveis BOOL/STRING, tolerância é ignorada (só "igual" ou "diferente").

### Criar grupos de permissão (se ainda não existem)

Pelo admin, em **Grupos**, certifique-se de que existem:

  - `TIM`
  - `Engenharia`
  - `Coordenacao` (sem cedilha) ou `Coordenação`

Operadores nesses grupos podem clicar em "Atualizar receita com valores
do CLP". Outros usuários veem o botão mas recebem 403 ao clicar.

---

## 2. Subir Redis + Recipe Monitor (via docker-compose)

Da raiz do `mis-core`:

```bash
# Sobe apenas os dois serviços novos (assume que mysql + django já estão de pé)
docker compose up -d mis-redis mis-recipe-monitor

# Verifica
docker compose logs -f mis-recipe-monitor
curl http://localhost:8100/health
# → {"status": "ok", "service": "mis-recipe-intelligent"}
```

### Variáveis de ambiente úteis (no `.env` do compose)

| Var | Default | Quando trocar |
|---|---|---|
| `MIS_REDIS_PORT` | `6379` | Conflito de porta no host |
| `RECIPE_MONITOR_PORT` | `8100` | Idem |
| `RECIPE_MONITOR_LINES_PRELOAD` | (vazio) | `L21,L18` para abrir subscriptions assim que o serviço sobe (sempre quente) |
| `RECIPE_MONITOR_LOG_LEVEL` | `INFO` | `DEBUG` para diagnosticar |
| `RECIPE_MONITOR_CORS_ORIGINS` | `localhost:3009,3005,3000` | Adicionar domínio do frontend em produção |
| `RECIPE_MONITOR_PUBLIC_URL` | `http://localhost:8100` | URL pública (passada ao build do React via `--build-arg`) |

---

## 3. Rebuild do Frontend (com a URL do serviço)

```bash
# Em desenvolvimento (npm start) — não precisa de build, basta um .env:
cd mis-change-over/Frontend
cp .env.example .env
# Edite .env e ponha REACT_APP_RECIPE_MONITOR_URL=http://localhost:8100
npm start

# Em produção (docker)
docker compose build mis-changeover-frontend
docker compose up -d mis-changeover-frontend
```

---

## 4. Validação manual ponta a ponta

### 4.1. Sem CLP real

Mesmo sem nenhum CLP conectado, todos os componentes precisam responder:

```bash
# Saúde do serviço
curl http://localhost:8100/health
# → 200 OK

# Config OPC vinda do Django (precisa de Django de pé + linha cadastrada)
curl -H "Authorization: Bearer <JWT>" http://localhost:8100/linhas/L21/config
# → 200 com {nome, equipamentos: [...]}  ou  404 se a linha não existe

# Snapshot — vai mostrar variáveis com atual=null se ainda não há leitura
curl -H "Authorization: Bearer <JWT>" http://localhost:8100/linhas/L21/snapshot
# → 200 com {linha, opc_online: false, variaveis: [{atual: null, ...}]}
```

### 4.2. Tela do operador

  1. Login normal no `mis-change-over`
  2. Menu superior → **Monitor de Receita** (entre Troca Automática e Histórico)
  3. Sidebar → escolher uma linha (ex.: L21)
  4. Esperar carregamento — em 1-2s, vê tabela com variáveis cadastradas
  5. Se o badge `OPC UA Offline` aparecer: o serviço não conseguiu
     conectar nos CLPs da linha. Veja `docker compose logs mis-recipe-monitor`
  6. Escolher um formato no dropdown → coluna "Receita" se preenche
  7. Quando há divergência, clicar em **Atualizar receita com valores do CLP**
  8. Modal mostra antes/depois → confirmar
  9. Toast verde → receita gravada com sucesso (auditoria registra o operador)

---

## 5. Diagnóstico

### Serviço sobe mas snapshot vem vazio

  - **Causa provável**: a linha não tem `ConfiguracaoEquipamentoVariavel`
    cadastrada, OU os `Equipamento.conexao_opcua` estão nulos.
  - **Verificar**: `curl /linhas/L21/config` — se `configuracoes_variaveis: []`
    ou `conexao_opcua_url: null`, o admin precisa preencher.

### Badge "OPC UA Offline" persistente

  - Veja logs: `docker compose logs mis-recipe-monitor | grep OPC`
  - Linhas como `[OPC] falha ao conectar opc.tcp://...` indicam que o
    servidor OPC está inacessível da rede do container. Confirme
    conectividade: `docker compose exec mis-recipe-monitor python -c
    "import asyncio; from asyncua import Client; asyncio.run(Client('opc.tcp://HOST:PORT').connect())"`

### Sincronizar retorna 403

  - O usuário logado não está em TIM / Engenharia / Coordenação.
  - Verifique pelo admin Django → Usuários → Grupos.

### Sincronizar retorna 400 "sem leitura"

  - O serviço não tinha valor cacheado dessa variável no Redis no
    momento do clique. Pode acontecer se o operador apertar muito
    rápido após abrir a tela ou se o CLP não responde.
  - **Alternativa**: o frontend pode mandar `valor` explícito no body
    (já faz isso por padrão na versão atual — usa o `atual` da própria UI).

### Erro CORS no browser

  - Adicione o domínio do frontend em `RECIPE_MONITOR_CORS_ORIGINS`
    (ver variáveis de ambiente acima) e reinicie o serviço.

### WebSocket fecha imediatamente

  - Provavelmente o proxy reverso não está configurado para WS.
  - No nginx, exige `proxy_http_version 1.1; proxy_set_header Upgrade
    $http_upgrade; proxy_set_header Connection "upgrade";`

---

## 6. Métricas-chave para monitorar

| Sinal | Onde olhar | Significado |
|---|---|---|
| `/health` 200 OK | `curl` ou healthcheck Docker | Serviço vivo |
| `opc_online: true` no snapshot | UI ou `curl /snapshot` | Reader recebendo updates do CLP |
| `redis-cli KEYS 'linha:*'` | Redis | Quantas linhas estão sendo monitoradas |
| `redis-cli HLEN linha:L21:atual` | Redis | Quantas variáveis têm valor cacheado |
| `docker compose logs mis-recipe-monitor` | logs | `[VQ-Worker]`, `[OPC]`, `[WS]` |

---

## 7. Rollback

Se algo der errado, o rollback é simples — tudo é aditivo:

```bash
# Para o serviço novo
docker compose stop mis-recipe-monitor mis-redis

# Reverte a migration (opcional — campos novos não atrapalham)
python manage.py migrate ips 0016_validacaoqualidade_troca_nullable

# Remove o link "Monitor de Receita" do menu se quiser
# (edita Header.jsx removendo o <Nav.Item> adicionado)
```

O resto do `mis-change-over` continua funcionando normalmente.
Nenhum fluxo existente foi tocado.
