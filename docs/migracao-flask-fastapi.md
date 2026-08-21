# Migração Flask → FastAPI (Flask-out)

## Contexto

A aplicação MIS Core convive hoje com três backends Python:

| Container        | Porta | Papel hoje                                            |
|------------------|------:|-------------------------------------------------------|
| `mis-core-django` | 8000 | Admin, ORM/migrations, ViewSets REST principais       |
| `mis-core-flask`  | 5000 | KPIs ad-hoc, realtime, analytics, scheduler, golden  |
| `mis-core-fastapi`| 8000 | FastAPI v2 — analytics novos, formulários ISO 22400  |

O objetivo é **eliminar completamente o Flask**, transferindo as responsabilidades para FastAPI (ou, em casos pontuais, para o próprio Django). A migração segue o padrão **Strangler**: Flask continua respondendo enquanto cada endpoint é portado, testado em paralelo, validado pelo frontend e finalmente desligado.

Este documento é o ponto único de verdade para o track Flask-out. Não muda código.

## Estado atual (verificado em 2026-05-16)

### Arquivos Flask em uso

`backend-flask/` — 15 módulos Python importam Flask, agrupados em três blocos:

**Bloco 1 — Analytics (Pronto para Migração)**
- `backend-flask/blueprints/analytics.py` (`/api/analyze/{stats,correlation,timeseries}`).
- **JÁ existe equivalente** em `backend-fastapi/app/routers/analytics.py`. Falta apenas mudar o frontend para `/api/v2/analyze/*`.

**Bloco 2 — KPIs (Parcialmente migrado)**
- `backend-flask/kpis_routes.py` (`/api/linha/<linha>/kpis`, `/api/equipamento/<eq>/kpis`, `/api/fabrica/kpis`).
- `backend-flask/kpis_engine.py` e `backend-flask/factory_kpis_engine.py` têm a lógica.
- FastAPI tem fórmulas em `backend-fastapi/app/core/formulas.py` mas não as rotas HTTP equivalentes.

**Bloco 3 — Operacional / não migrado**
- `backend-flask/routes.py::/api/health/system`, `/api/realtime/all`, `/api/shift/reset`.
- `backend-flask/scheduler.py` (APScheduler — reset de turno, consolidação).
- `backend-flask/blueprints/golden_state.py` (`/api/golden-state/apply`, `/capture`).
- `backend-flask/services/diagnostics_engine.py` (regras MicroStops, Starvation, GoldenStateDeviation).

### Roteamento atual

`frontend-react/nginx.conf` separa:

```nginx
location /api/      → http://django:8000
location /flask-api/ → http://flask:5000     # com rewrite /flask-api/(.*) → /api/$1
location /api/v2/   → http://fastapi:8000
```

Frontend usa as constantes `FLASK_API_URL = '/flask-api'` e `FASTAPI_V2_URL = '/api/v2'` em `frontend-react/client/src/config/api.ts`.

### Dependências exclusivas do Flask

`backend-flask/requirements.txt`:
- `Flask==3.0.0`, `Flask-Cors==4.0.0` — substituídas por FastAPI nativo + `CORSMiddleware`.
- `scipy==1.15.3`, `pandas==2.3.3`, `numpy==2.3.5` — **JÁ presentes** no `backend-fastapi/Dockerfile`. Não exigem nova compatibilidade.
- `influxdb==5.3.1` — também presente no FastAPI (cliente Influx 1.x).

Nenhuma barreira técnica impede a remoção.

### Cobertura de testes

| Backend    | Pasta                     | Cobertura                                     |
|------------|---------------------------|-----------------------------------------------|
| Flask      | `backend-flask/tests/`    | `test_routes.py` (~100 linhas, health/realtime) |
| FastAPI v2 | `backend-fastapi/tests/`  | `test_formulas.py`, `test_pipelines.py`       |

**Gap crítico:** FastAPI não tem testes para `/api/v2/analyze/*` nem para os endpoints de KPI ainda não portados. Esse gap precisa ser fechado **antes** de desligar o Flask correspondente.

## Plano por endpoint

Tabela completa: rota Flask atual → rota FastAPI alvo → status → consumidores frontend → ordem de execução.

| # | Flask                              | FastAPI (alvo)                              | Status     | Consumidor frontend                                  | Ordem |
|---|------------------------------------|---------------------------------------------|------------|-----------------------------------------------------|-------|
| 1 | `/api/analyze/stats`               | `/api/v2/analyze/stats` ✓ existe            | **Migrar frontend** | `LineAnalytics.tsx` (`handleRunAnalysis('stats')`)  | A     |
| 2 | `/api/analyze/correlation`         | `/api/v2/analyze/correlation` ✓ existe      | **Migrar frontend** | `LineAnalytics.tsx` (`handleRunAnalysis('correlation')`) | A     |
| 3 | `/api/analyze/timeseries`          | `/api/v2/analyze/timeseries` ✓ existe       | **Migrar frontend** | `LineAnalytics.tsx` (`handleRunAnalysis('timeseries')`) | A     |
| 4 | `/api/realtime/all`                | `/api/v2/production/realtime` (criar)       | **Portar**         | `SidebarV2.tsx`, `HomeV2.tsx`                       | B     |
| 5 | `/api/linha/<linha>/kpis`          | `/api/v2/kpis/linha/{codigo}` (criar)       | **Portar**         | `LineDeepView.tsx`                                  | C     |
| 6 | `/api/equipamento/<eq>/kpis`       | `/api/v2/kpis/equipamento/{codigo}` (criar) | **Portar**         | `EquipamentoDetalhes.tsx`                           | C     |
| 7 | `/api/fabrica/kpis`                | `/api/v2/kpis/fabrica` (criar)              | **Portar**         | `FactoryManagementPanel.tsx`                        | C     |
| 8 | `/api/fabrica/mapa`                | `/api/v2/fabrica/mapa` (criar) ou Django    | **Portar**         | `FactoryManagementPanel.tsx`                        | C     |
| 9 | `/api/linha/<linha>/historico`     | `/api/v2/linha/{codigo}/historico` (criar)  | **Portar**         | `VariablesTab.tsx`, `LineDeepView.tsx`              | D     |
| 10 | `/api/health` e `/api/health/system` | `/api/v2/healthz` ✓ existe / criar `/system` | **Migrar frontend** | `useSystemHealth` hook                              | A     |
| 11 | `/api/shift/reset`                 | Celery beat no Django **ou** lifespan task FastAPI | **Reescrever**     | Nenhum (cron, chamado pelo `scheduler.py`)         | E     |
| 12 | `/api/diagnostics/*`               | `/api/v2/diagnostics/*` (criar)             | **Portar regras**   | `DiagnosticosLogs.tsx`                              | F     |
| 13 | `/api/golden-state/apply`/`/capture` | Decisão pendente (Django via OPC service ou FastAPI) | **Pendente**       | UI específica (não localizada nesta tranche)        | G     |

Legenda da coluna **Ordem**: A → G na ordem em que os PRs devem ser feitos.

## Ordem de execução

Cada item abaixo corresponde a um PR (branch separada, descrição PT-BR, testes próprios).

### PR-A: Migrar frontend de analytics + healthz para FastAPI v2

**Branch sugerida:** `chore/flask-out-A-analytics-frontend`

1. Em `frontend-react/client/src/pages/LineAnalytics.tsx`, trocar `${FLASK_API_URL}/analyze/{stats,correlation,timeseries}` por `${FASTAPI_V2_URL}/analyze/...`.
2. Em `useSystemHealth` (`frontend-react/client/src/hooks/useSystemHealth.ts`), trocar chamadas de health para `/api/v2/healthz`. Manter fallback para `/api/health/` Django.
3. Não tocar no Flask — apenas redirecionar.
4. Teste manual: rodar análise stats/correlation/timeseries com FastAPI up e Flask **desligado** temporariamente.

**Risco:** baixo. Strangler nativo do nginx, basta mudar a URL.

### PR-B: Portar `/realtime/all` para FastAPI

**Branch:** `feat/flask-out-B-realtime-fastapi`

1. Criar `backend-fastapi/app/routers/realtime.py` com rota `GET /api/v2/production/realtime` que devolve o **mesmo shape** que o Flask hoje (`{ equipamento_codigo: { medicoes, linha, ... } }`).
2. A leitura de Influx pode reutilizar `backend-fastapi/app/services/influx.py`. Se não tem helper equivalente ao Flask, copiar do `backend-flask/services/realtime_store.py`.
3. Criar `backend-fastapi/tests/test_realtime.py` com fixtures mockadas.
4. Em `SidebarV2.tsx` e `HomeV2.tsx`, adicionar feature flag `USE_FASTAPI_REALTIME` (env var `VITE_USE_FASTAPI_REALTIME`) que troca entre Flask e FastAPI. Defaults a `false` por uma semana.

**Risco:** médio. Mudança de shape pode quebrar o `aggregateLineStates`. Validar payload byte-a-byte primeiro.

### PR-C: Portar KPIs (`kpis_routes.py`, `kpis_engine.py`, `factory_kpis_engine.py`)

**Branch:** `feat/flask-out-C-kpis-fastapi`

1. Criar `backend-fastapi/app/routers/kpis.py` com rotas:
   - `GET /api/v2/kpis/linha/{codigo}?period=turno|dia|semana|mes`
   - `GET /api/v2/kpis/equipamento/{codigo}?period=...`
   - `GET /api/v2/kpis/fabrica?period=...`
2. Portar funções de `kpis_engine.py` (compute_oee, compute_tph, etc.) para `backend-fastapi/app/services/kpi_engine.py`. Reusar `formulas.py` quando existe.
3. Portar `factory_kpis_engine.py` para `backend-fastapi/app/services/factory_kpi_engine.py`.
4. Criar `backend-fastapi/tests/test_kpis.py` validando contra dados históricos.
5. Atualizar consumidores frontend (`LineDeepView`, `EquipamentoDetalhes`, `FactoryManagementPanel`) para chamar `/api/v2/kpis/*`.

**Risco:** alto. KPIs são consumidos por várias telas e têm regras de período (alinhamento de turno).

### PR-D: Portar `/linha/<linha>/historico` para FastAPI

**Branch:** `feat/flask-out-D-historico-fastapi`

1. Criar `GET /api/v2/linha/{codigo}/historico?start&end&interval` em `backend-fastapi/app/routers/historico.py`.
2. Resampling com pandas igual ao Flask atual.
3. Atualizar `VariablesTab.tsx` e `LineDeepView.tsx`.

**Risco:** médio.

### PR-E: Migrar scheduler para Celery beat (Django) ou FastAPI lifespan

**Branch:** `chore/flask-out-E-scheduler`

1. Decidir entre:
   - **Opção 1 (recomendada):** Celery beat no Django. Já há `django_apscheduler` instalado (vide migrations).
   - **Opção 2:** FastAPI `app/main.py` lifespan task que dispara reset de turno.
2. Mover lógica de `backend-flask/scheduler.py::shift_reset` para o novo lugar.
3. Testar disparo manual via management command.

**Risco:** alto se mal-feito (reset de turno errado corrompe `MetricaProducao`). Não derrubar Flask até estar 100% testado.

### PR-F: Portar diagnostics engine

**Branch:** `feat/flask-out-F-diagnostics-fastapi`

1. Criar `backend-fastapi/app/services/diagnostics/` com módulos:
   - `rules.py`: classes `MicroStopsRule`, `StarvationRule`, `GoldenStateDeviationRule`.
   - `engine.py`: orquestrador.
2. Criar `GET /api/v2/diagnostics/equipamento/{codigo}` e `/linha/{codigo}`.
3. Criar `backend-fastapi/tests/test_diagnostics.py` com cenários sintéticos.
4. Atualizar `DiagnosticosLogs.tsx`.

**Risco:** médio.

### PR-G: Decisão e migração do golden_state

**Branch:** `chore/flask-out-G-golden-state-decision`

1. Decisão arquitetural: golden_state é um fluxo de **escrita no CLP** via OPC. Provavelmente faz sentido manter no Django (que já tem o cadastro de equipamentos e `ConexaoOPC`) ou criar um serviço dedicado em FastAPI.
2. Documentar decisão (ADR) em `docs/adr/`.
3. Implementar conforme decisão.

**Risco:** alto. Comando indevido no CLP é problema operacional sério.

### PR-cutover (final): desligar Flask

**Branch:** `chore/flask-out-cutover`

Quando A → F estiverem mergeados e estáveis por **2 semanas em produção**:

1. Remover `location /flask-api/` de `frontend-react/nginx.conf`.
2. Remover serviço `flask` de `docker-compose.yml` (linhas ~134-162).
3. Remover diretório `backend-flask/` inteiro.
4. Remover `mis-core-flask` da imagem offline (`mis-core-offline/*.sh`, `mis-core-offline/build-demo.ps1`).
5. Atualizar `README.md` e `docs/DEPLOY_OT.md`.
6. PR-G fechando golden_state (se ainda dependia do Flask).

**Risco:** baixo na cutover propriamente, alto se o monitoramento não confirmar 2 semanas saudáveis.

## Plano de testes

Cada PR (A → G) deve:

1. **Adicionar testes próprios** em `backend-fastapi/tests/test_<dominio>.py` espelhando os do Flask (`backend-flask/tests/test_routes.py`).
2. **Comparar respostas Flask vs FastAPI** numa janela paralela. Script sugerido em `backend-fastapi/tests/compare_endpoints.py`:
   ```python
   # Pseudocodigo: GET dos dois backends, normalizar, diff JSON
   for url in urls:
       flask_resp = httpx.get(f"http://flask:5000{url}").json()
       fastapi_resp = httpx.get(f"http://fastapi:8000/api/v2{url}").json()
       assert canonical_diff(flask_resp, fastapi_resp) == []
   ```
3. **Smoke test pós-cutover**: rodar `make smoke-flask-out` antes de cada deploy.

## Cronograma sugerido

| Semana | PRs                                                |
|--------|----------------------------------------------------|
| 1      | PR-A (analytics + healthz frontend)                |
| 2      | PR-B (realtime/all)                                |
| 3-4    | PR-C (KPIs)                                        |
| 5      | PR-D (historico)                                   |
| 6      | PR-E (scheduler)                                   |
| 7      | PR-F (diagnostics)                                 |
| 8      | PR-G (decisão golden_state) + observação           |
| 9-10   | Observação em produção                             |
| 11     | PR-cutover                                         |

Cronograma é otimista; cada semana é uma rodada de PR/revisão/deploy, não trabalho contínuo.

## Métricas de sucesso

Antes de mergear `PR-cutover`:

- [ ] `docker compose ps` mostra `mis-core-fastapi` healthy há 14 dias consecutivos.
- [ ] Nenhuma chamada para `/flask-api/*` no nginx logs por 7 dias (`grep "/flask-api/" nginx-access.log`).
- [ ] Todos os testes `backend-fastapi/tests/` passam no CI.
- [ ] Tela `/mis-core/analytics`, `/mis-core/factory-panel`, `/mis-core/linha/*/detalhes`, `/mis-core/diagnosticos` funcionando sem regressão visual.
- [ ] Diff de KPI consolidado por linha (Flask vs FastAPI) está dentro de 0,1 ponto percentual em 5 cenários históricos.

## Anexos

- Caminhos absolutos verificados: `backend-flask/`, `backend-fastapi/app/`, `frontend-react/client/src/`, `docker-compose.yml`, `frontend-react/nginx.conf`.
- Documento gerado como parte do PR 15 do plano principal (ver `~/.claude/plans/codex-estou-listando-aqui-rustling-karp.md` item 18).
