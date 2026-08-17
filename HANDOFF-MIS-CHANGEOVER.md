# MIS Change Over — Documento de Handoff / Contexto para IA

> **Propósito deste arquivo:** dar a qualquer modelo (ou pessoa) o contexto completo para
> **revisar** ou **implementar features** no MIS Change Over — sem precisar do histórico da conversa.
> Cole este arquivo como contexto inicial. Última atualização do doc: **2026-08-17**.

---

## 0. TL;DR (leia isto primeiro)

- **O que é:** sistema industrial de **troca de SKU / changeover** de linhas de produção (rede OT/fábrica), com leitura de CLPs via **OPC UA**, sincronismo de receitas, validações de qualidade e monitor de receita em tempo real.
- **Onde está o código:** monorepo local `C:\Users\ermir\OneDrive\Documentos\GitHub\mis-core`; a aplicação fica na subpasta **`mis-change-over/`**.
- **⚠️ Fonte da verdade = árvore LOCAL, não o GitHub.** O remoto está em **v8.5**; o que está em produção é **v11.1**, com **~164 arquivos não commitados**. Ver §7.
- **Deploy:** **offline**, por imagens Docker (`docker save`→`.tar`→`scp`→`docker load`) para um servidor Linux OT sem internet. Ver §8. Regra de ouro: **sempre subir o número da versão** e **transferir arquivos por `scp`, nunca copiar/colar**.
- **Produção:** servidor OT `administrator@192.168.30.71`, hub em **`~/Documents/dist/`**.

---

## 1. Localização do projeto e arquivos

| Item | Caminho |
|---|---|
| Monorepo (raiz) | `C:\Users\ermir\OneDrive\Documentos\GitHub\mis-core` |
| **Aplicação Change Over** | `mis-change-over/` |
| Backend Django | `mis-change-over/Backend/` |
| App principal Django | `mis-change-over/Backend/ips/` |
| App auxiliar | `mis-change-over/Backend/programa_andretti/` |
| Settings/URLs Django | `mis-change-over/Backend/digitalfactory/` |
| Serviço Recipe Monitor (FastAPI) | `mis-change-over/Backend/recipe_monitor_service/` |
| Frontend React | `mis-change-over/Frontend/` |
| Telas (componentes) | `mis-change-over/Frontend/src/components/` |
| Scripts de build de pacote | raiz: `save-changeover-vX.Y.sh` |
| Pacotes/scripts de deploy | `dist/deploy/` (`.tar`, `carregar-*.sh`, `restaurar-*.sh`, compose do hub) |
| Compose mestre do hub (servidor) | `dist/deploy/docker-compose.hub-v11.1.yml` |

> O monorepo contém outros produtos (mis-core, mis-ai, mis-energy, mis-planning) que **compartilham** o mesmo MySQL/InfluxDB/nginx-proxy no servidor, mas **este handoff é do Change Over**.

---

## 2. Arquitetura e serviços

```
Navegador (rede OT)
   │
   ▼
nginx-proxy central (mis-core-proxy)  ──►  roteia por caminho:
   ├── /                         → frontends (React)
   ├── /api/  (changeover)       → mis-changeover-backend (Django :8000)
   └── /recipe-monitor/          → mis-recipe-monitor (FastAPI :8100)  [HTTP + WebSocket]

mis-changeover-backend (Django + DRF + SimpleJWT)
   ├── MySQL (mis_changeover_db)
   ├── OPC UA (lib `opcua`, síncrono) → CLPs das linhas
   └── Workers em background (leitura OPC, validação por caixas, expiração de contas)

mis-recipe-monitor (FastAPI + asyncua)
   ├── lê tags OPC continuamente
   ├── Redis (mis-redis) — cache + pub/sub
   ├── WebSocket → tela "Monitor de Receita"
   └── repassa o PATCH de sincronismo para o Django (não valida JWT localmente)
```

**Portas (padrão do compose do hub):**

| Serviço | Container | Porta host:container |
|---|---|---|
| Changeover backend (Django) | `mis-changeover-backend` | `5006:8000` |
| Changeover frontend (React/nginx) | `mis-changeover-frontend` | `3009:80` |
| Recipe Monitor (FastAPI) | `mis-recipe-monitor` | `8100:8100` |
| Redis | `mis-redis` | `6379:6379` |
| MySQL (compartilhado) | `mis-hub-mysql` | `3306` |
| nginx-proxy (central) | `mis-core-proxy` | `80` |

---

## 3. Stack técnica

**Backend Django** (`mis-change-over/Backend/`)
- Python 3.11, Django 5.1, Django REST Framework, `djangorestframework-simplejwt`.
- `MyTokenObtainPairSerializer` custom: adiciona claims `groups`, `is_superuser`, `is_staff`; bloqueia login de conta expirada.
- MySQL (`mysql_native_password`), banco `mis_changeover_db`.
- OPC UA **síncrono** via `opcua` (leitura/escrita de tags no Django).
- Impressora 3M via `pysmb` (SMB Direct TCP 445).
- Workers iniciados no `apps.py`/serviço: leitura OPC, `OPCValidacaoQualidadeWorker`, `ExpiracaoContasWorker`.

**Recipe Monitor** (`recipe_monitor_service/`) — imagem `mis-recipe-intelligent`
- FastAPI + `asyncua` (OPC assíncrono), Redis (`redis`/`hiredis`), WebSocket, `python-jose`.
- Estrutura: `app/main.py`, `app/api/rest.py`, `app/api/ws.py`, `app/opc/`, `app/state/`, `app/django_client.py`, `app/auth.py`, `app/classifier.py`, `app/schemas.py`, `app/config.py`.

**Frontend** (`mis-change-over/Frontend/`) — imagem `mis-frontend`
- React (Create React App), `react-bootstrap`, `recharts`, `axios` (hook `useAxios` com refresh JWT automático), `react-icons`.
- Build servido por nginx dentro do container.

---

## 4. Estrutura de pastas (Change Over)

```
mis-change-over/
├── Backend/
│   ├── digitalfactory/        # settings.py, urls.py (projeto Django)
│   ├── ips/                   # APP PRINCIPAL: models, views, serializers, services (workers),
│   │   ├── admin.py           #   permissions, urls, migrations 0001..0020
│   │   └── migrations/        #   última: 0020_validacao_por_caixas
│   ├── programa_andretti/     # app auxiliar (programa Andretti)
│   ├── recipe_monitor_service/# microserviço FastAPI (mis-recipe-intelligent)
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── requirements.txt
└── Frontend/
    ├── src/
    │   ├── App.js             # rotas
    │   ├── components/        # telas (ver §6)
    │   │   └── layout/        # Header.jsx (menu), Sidebar, config.js
    │   └── ...
    ├── dockerfile
    └── nginx.conf
```

---

## 5. Modelos de dados principais (app `ips`)

Núcleo: `Linha`, `Formato`, `FormatoVariavel`, `VariavelMestra`, `Produto`, `AssociacaoProdutoLinha`,
`Equipamento`, `Controle`, `StatusLinha`, `Troca`, `IntertravamentoLinha`, `HistoricoSincronismoReceita`.

Adições recentes (features deste ciclo):
- **Expiração de conta** — `ContaUsuarioExpiracao` (inatividade 60 dias OU validade 5 meses; só superuser renova). Migrations `0018`, `0019` (backfill).
- **Validação de qualidade por CAIXAS** — `Linha.tag_caixas_sku_opc`; `ValidacaoQualidade` estendida (`quantidade_caixas_meta`, `caixas_produzidas`, `parada_em`, `caixas_na_aprovacao`, `observacao_qualidade`); `ConfiguracaoValidacaoQualidade` (singleton), `CriterioValidacaoQualidade` (Formato×Linha), `HistoricoValidacaoQualidade`. Migration `0020`.
- **Recipe Monitor** — suporte a tags OPC de leitura contínua. Migration `0017`.

> **Política de migrations:** apenas **aditivas**. O projeto tem drift pré-existente (0001 e 0004 criam `Controle`) que **impede migrar do zero**, mas é inócuo em produção (só migra incrementalmente). Validar migrations novas com `sqlmigrate` + `manage.py check`, não com migrate-from-scratch.

---

## 6. Funcionalidades (telas e o que fazem)

| Tela / Componente | Função |
|---|---|
| **Troca de SKU** (`TrocasContent`, `TrocaAutomaticaContent`) | Executa a troca de SKU na linha (grava no CLP via OPC), registra `Troca`. |
| **Validações** (`ValidacoesContent`) | Pipeline SAP → Qualidade. **Qualidade por caixas**: ao atingir a meta de caixas o worker escreve `True` em `tag_aguardando_validacao_opc` (CLP para) e mostra card "linha parada — aguardando validação". |
| **Monitor de Receita** (`ReceitaMonitorContent`) | Compara receita do Formato × leitura OPC ao vivo (WebSocket). **Formato TRAVADO no que roda na máquina** (detectado via `tag_sku_atual_opc` com fallback para última troca) — sem dropdown, para o operador não sincronizar no formato errado. Backend bloqueia com **409 `formato_divergente`**. |
| **Gestão de Usuários** (`GestaoUsuariosContent`) | Só superuser. Lista validade das contas e permite **renovar** (reseta expiração). |
| **Intertravamentos** (`IntertravamentosContent`) | Intertravamentos por linha. |
| **Comunicação / Chat** (`ComunicacaoContent`, `MachineChat`) | Chat por linha/turno, menções, resumo de turno. |
| **KPIs / Relatórios / Histórico** (`KpisContent`, `ReportsContent`, `HistoricoDataContent`, Insights modals) | Analytics de trocas e formatos. |
| **Status do Produto** (`ProductStatusContent`) | **Tela escondida** do menu, mas o **worker** correspondente segue rodando. |
| **Cartucho / Flexíveis / Andretti** (`CartuchoContent`, `FlexiveisContent`, `AndrettiContent`) | Agrupamentos por tipo de linha. |

Menu condicional em `Frontend/src/components/layout/Header.jsx`: "Gestão de Usuários" só aparece para `is_superuser`.

---

## 7. Estado do GitHub (IMPORTANTE)

- **Remoto:** `https://github.com/Ermirio/mis-core.git` — branch de trabalho **`mis-admin-modules`** (branch principal do repo é `master`).
- **Último commit:** `6e8ce325 feat(changeover): v8.5 …`
- **Realidade:** produção roda **v11.1**. Há **~164 arquivos modificados/não commitados** (todo o trabalho de v9→v11.1 está **apenas na árvore local**).
- **Consequência:** se um modelo/pessoa clonar o GitHub, verá **código v8.5 (defasado)**. Para revisão/feature fiel, use a **árvore local** OU **commite+faça push** antes.

**Recomendado antes de pedir revisão externa:** consolidar o estado atual no Git (commit + push da branch `mis-admin-modules`) para o GitHub virar a fonte da verdade. *(Isso é uma ação que altera o repositório — peça explicitamente que eu faça, ou rode você mesmo.)*

---

## 8. Forma de deploy adotada (offline, rede OT)

### 8.1 Conceito
A rede OT **não tem internet**. Deploy = **construir imagens no Windows (dev) → exportar para `.tar` → copiar por `scp` → carregar no servidor Linux → recriar containers**. Nada é buildado no servidor.

### 8.2 Ambientes
| | Dev (build) | Produção (OT) |
|---|---|---|
| Máquina | Windows 11 + Docker Desktop | Servidor Linux `administrator@192.168.30.71` |
| Papel | Compila as 3 imagens e gera o pacote | Carrega o `.tar` e sobe os containers |
| Hub (compose) | — | **`~/Documents/dist/`** (tem `.env`, `proxy-reverse/`, `mysql-init/`) |

### 8.3 Imagens (3)
`mis-backend:vX.Y` · `mis-frontend:vX.Y` · `mis-recipe-intelligent:vX.Y`
(os serviços no compose: `mis-changeover-backend`, `mis-changeover-frontend`, `mis-recipe-monitor` + `mis-redis`).

### 8.4 Passo a passo
**No Windows (gerar pacote):**
```bash
bash save-changeover-v11.1.sh        # build das 3 imagens + docker save -> dist/deploy/mis-changeover-v11.1.tar
```
Saídas em `dist/deploy/`: `mis-changeover-v11.1.tar` (~634 MB) e `restaurar-v11.1.sh`.

**Transferir para o servidor (SEMPRE por scp — NUNCA colar conteúdo em editor):**
```bash
scp dist/deploy/mis-changeover-v11.1.tar dist/deploy/docker-compose.hub-v11.1.yml dist/deploy/restaurar-v11.1.sh \
    administrator@192.168.30.71:~/Documents/dist/restore-v11.1/
```

**No servidor (restaurar/atualizar):**
```bash
cd ~/Documents/dist/restore-v11.1
chmod +x restaurar-v11.1.sh
sudo ./restaurar-v11.1.sh        # instala compose no hub (sanitiza), docker load, sobe redis+changeover+recipe, recarrega proxy
```
Confirmar no fim:
```bash
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -E 'changeover|recipe|redis'
```

### 8.5 Regras/lições aprendidas (NÃO repetir erros)
1. **Sempre subir o número da versão** (v11.0 → v11.1). Tag de imagem é ponteiro mutável; reusar a mesma tag faz o Compose achar que "já está atualizado" e **não recriar** → sintoma "carreguei e não mudou nada".
2. **Transferir por `scp` (binário), nunca copiar/colar** o conteúdo num editor. Paste injeta caracteres invisíveis → `yaml: control characters are not allowed`. O compose mestre é mantido **100% ASCII** por isso.
3. O compose do hub **precisa** conter `mis-redis` **e** `mis-recipe-monitor`; senão `docker compose up ... mis-recipe-monitor` falha com "no service" e **nada** é recriado.
4. O compose **mora no hub** (`~/Documents/dist/`) por causa dos caminhos relativos (`./.env`, `./proxy-reverse`, `./mysql-init`). Não rode de outra pasta.
5. Ao recriar o recipe-monitor, **subir o `mis-redis` junto** (não usar `--no-deps` sem incluir o redis).
6. Após recriar containers, **recarregar o nginx-proxy central** (`docker exec mis-core-proxy nginx -s reload`) — ele cacheia o IP do upstream e pode dar 502.
7. Frontend: se a tela não mudar, `Ctrl+Shift+R` (o bundle React tem hash, mas cache do navegador às vezes atrapalha na 1ª vez).

### 8.6 Pré-requisitos de infra (uma vez)
- Banco `mis_changeover_db` no MySQL compartilhado.
- nginx-proxy com `location /recipe-monitor/` + bloco `map $http_upgrade $connection_upgrade` (WebSocket) apontando para `mis-recipe-monitor:8100`.

---

## 9. Pendências / próximos passos (Fase 2)

- **Automação (CLP):** expor a tag **"caixas desde a troca"** (zerada na troca) mapeada em `Linha.tag_caixas_sku_opc`. Sem ela, a validação por caixas não conta de ponta a ponta.
- **Detecção de formato:** garantir `Linha.tag_sku_atual_opc` configurada por linha (senão o Monitor de Receita cai no fallback "última troca").
- **Proxy:** confirmar `location /recipe-monitor/` no `~/Documents/dist/proxy-reverse/nginx.conf` (a tela abre pelo frontend, mas os dados só chegam se o proxy rotear).
- **Git:** consolidar v9→v11.1 no repositório (commit + push) — ver §7.
- **Opcional (teste):** simulador de contagem de caixas para exercitar a validação sem a automação.

---

## 10. Como pedir revisão/feature a um modelo (instruções para o próximo modelo)

Ao usar este documento como contexto, o modelo deve:
1. Tratar a **árvore local** (`mis-change-over/`) como fonte da verdade — **não** o GitHub (defasado em v8.5).
2. Backend em `ips/` (models/views/serializers/services/urls) e frontend em `Frontend/src/components/`.
3. **Migrations sempre aditivas**; validar com `sqlmigrate` + `manage.py check` (não migrar do zero — há drift conhecido).
4. Ao entregar deploy: **novo número de versão**, gerar via `save-changeover-vX.Y.sh`, e instruir transferência por **scp** (nunca paste). Compose mestre em ASCII.
5. Testes rápidos sem Docker: `python -m py_compile` no backend; parse do JSX (o `node_modules` local costuma estar em placeholder do OneDrive — a validação real é o build da imagem frontend).
6. Confirmar resultado real (rodar/checar `docker ps`, health endpoints) antes de dizer "concluído".
