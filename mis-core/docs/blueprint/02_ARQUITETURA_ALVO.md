# 🏗️ Arquitetura Alvo — mis-core v2

> **Princípio de design:** strangler pattern, zero downtime, observabilidade por padrão, fórmulas testáveis, UI orientada a status (ISA-101).
> **Inspirações:** Rockwell FactoryTalk ProductionCentre, Siemens Opcenter Execution, GE Proficy Plant Applications, AVEVA MES, Tulip.

---

## 1. Visão em 30 segundos

Hoje temos **Django + Flask + Coletor + React** acoplados. A arquitetura alvo separa claramente **4 domínios** e introduz um **plano de controle** (inteligência) acima do **plano de dados** (coleta/armazenamento).

**Analogia WCM:** pense no modelo "Célula → Linha → Fábrica → Corporação" do WCM. O core hoje é a **célula**, tudo rodando junto. Vamos subir o nível para termos uma **fábrica digital** com pilares bem definidos (coleta, armazenamento, analítica, apresentação, controle).

---

## 2. Diagrama de arquitetura (texto)

```
┌───────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React + TS)                     │
│   ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌────────────────┐   │
│   │ HomeHMI  │  │ Analytics│  │ Equipmnt  │  │ Admin/Settings │   │
│   │ (ISA-101)│  │  (EDA)   │  │  Detail   │  │                │   │
│   └────┬─────┘  └────┬─────┘  └─────┬─────┘  └────┬───────────┘   │
│        │             │              │             │               │
│        └─────────────┴──────┬───────┴─────────────┘               │
│                             │                                     │
│              React Query + TS types compartilhados                │
└─────────────────────────────┼─────────────────────────────────────┘
                              │
                              │ REST / WebSocket
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│                         API GATEWAY (nginx)                       │
│                /api/v2 ──▶ FastAPI (novo)                         │
│                /api      ──▶ Django (admin, ORM, auth legado)     │
│                /flask-api──▶ Flask (realtime legado, em retirada) │
└──────┬─────────────────────┬────────────────────────┬─────────────┘
       │                     │                        │
┌──────▼──────────┐  ┌───────▼──────────┐  ┌──────────▼──────────┐
│ FastAPI         │  │ Django Admin/ORM │  │ Flask (strangle)    │
│ - /analytics/*  │  │ - Models         │  │ - Endpoints sendo   │
│ - /kpis/*       │  │ - Auth/Perm      │  │   migrados para v2  │
│ - /realtime WS  │  │ - Admin site     │  │ - Manter até P3     │
│ - /golden/*     │  │                  │  │                     │
│ Pydantic schemas│  │ PostgreSQL       │  │                     │
└───┬──────┬──────┘  └────┬─────────────┘  └──────────┬──────────┘
    │      │              │                            │
    │      └──────┬───────┴──────────┬─────────────────┘
    │             │                  │
┌───▼──┐   ┌──────▼──────┐   ┌───────▼────────┐
│Redis │   │ PostgreSQL  │   │ InfluxDB       │
│cache │   │ (cadastros, │   │ (time-series:  │
│      │   │  config)    │   │  coleta OPC)   │
└──────┘   └─────────────┘   └───────┬────────┘
                                     │
          ┌──────────────────────────▼──────────────────────────┐
          │           COLETOR OPC UA v2 (resiliente)            │
          │  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌────────┐ │
          │  │Reconnect│  │Watchdog │  │ Buffer   │  │Health  │ │
          │  │ backoff │  │ async   │  │ SQLite   │  │ +Prom  │ │
          │  └─────────┘  └─────────┘  └──────────┘  └────────┘ │
          │            ┌───────────────────┐                    │
          │            │ Circuit Breaker   │                    │
          │            └───────────────────┘                    │
          └──────────────────┬────────────────────────────────────┘
                             │
                      ┌──────▼───────┐
                      │ OPC UA Server│ (PLCs Siemens/Rockwell)
                      └──────────────┘

             ┌─────────────────────────────────────┐
             │ OBSERVABILIDADE                     │
             │ Prometheus + Grafana + Loki + Alert │
             │ (dashboards: coletor, API, InfluxDB)│
             └─────────────────────────────────────┘
```

---

## 3. Stack alvo por camada

| Camada | Tecnologia | Por quê |
|---|---|---|
| Frontend | React 18 + TS + Vite + Tailwind + shadcn + React Query 5 + Recharts | Já é o stack. Adicionar React Query (cache/retry) e **remover Plotly duplicado** |
| API Gateway | nginx (já existe) | Roteamento por path → stranglerpattern |
| API Moderna | **FastAPI** 0.110+, Pydantic v2, Uvicorn, asyncpg, httpx | Performance, typing, OpenAPI auto, async nativo |
| API Legado | Flask (estrangular), Django (manter admin/auth) | Não reescrever até hora certa |
| ORM | SQLAlchemy 2.x (FastAPI) ou Django ORM consultado via Django-only path | Não duplicar modelos — FastAPI lê via asyncpg direto ou via Django API |
| Cache | Redis | Queries de analytics recorrentes, sessão WebSocket |
| Time-series | InfluxDB 2.x (mantido) + **TimescaleDB** como opção para histórico longo | Flux para realtime, SQL para analytics complexo |
| Coletor | Python 3.11 + asyncua + tenacity + aiohttp (health) + prometheus_client + aiosqlite | Resiliência + observabilidade |
| Observabilidade | Prometheus + Grafana + Loki + Alertmanager | Padrão indústria, já tem Grafana |
| Mensageria (futuro) | NATS ou Redis Streams | Se precisar desacoplar coletor de API |

---

## 4. Fronteiras dos serviços (strangler pattern)

### 4.1 FastAPI v2 — nasce responsável por **novas features**

- `POST /api/v2/analytics/trends` — séries com delta aplicado, range datetime, OFF-mask, agregação configurável
- `POST /api/v2/analytics/stats` — descritivas + EDA moderna (p50/p90/p99, IQR, outliers, STL)
- `GET /api/v2/analytics/correlation` — Pearson/Spearman com bootstrap CI
- `GET /api/v2/kpis/line/{id}?from=…&to=…` — KPI com range datetime
- `GET /api/v2/kpis/factory?from=…&to=…` — substitui `period=turno|dia|…`
- `WS /api/v2/realtime/{line_id}` — WebSocket de realtime (opcional, P3)

### 4.2 Django — continua dono de

- Admin site (cadastro de linhas, equipamentos, sensores, calendários de produção)
- Modelos ORM (source of truth para metadados)
- Autenticação e permissões (JWT compartilhado com FastAPI via SimpleJWT)
- CRUD de `analytics_profiles` (já existe e funciona)

### 4.3 Flask — **em retirada**

Ordem de morte (cada endpoint é migrado para `/api/v2` e depois removido):
1. `GET /api/fabrica/kpis` → `GET /api/v2/kpis/factory`
2. `GET /api/linha/<id>/ole-realtime` → `GET /api/v2/kpis/line/<id>`
3. `POST /analyze/*` → `POST /api/v2/analytics/*`
4. Realtime endpoints → WebSocket ou manter HTTP polling, caso a caso

Mantido até migração completa: rotas de suporte/debug (`/debug/*`).

### 4.4 Coletor v2 — redesign com 6 componentes

| Componente | Responsabilidade |
|---|---|
| `OpcConnectionManager` | Conecta, reconecta (tenacity backoff exp. 1→32s), valida heartbeat |
| `Watchdog` | Task paralela, verifica cada URL OPC a cada 30s, derruba conexões zumbi |
| `ReadingBuffer` | SQLite local com leituras pendentes quando APIs caem |
| `ApiClient` | Envia para Django/Flask/FastAPI com circuit breaker (pybreaker) |
| `HealthServer` | aiohttp simples, `GET /health` e `GET /metrics` (Prometheus) |
| `StateMapper` | Centraliza `MAPEAMENTO_ESTADOS` + regras de "parado/produzindo/planejado/não planejado" |

---

## 5. Contrato de dados (essencial)

### 5.1 Metadado de métricas (novo)

Cria `backend/fastapi/app/metrics_catalog.py`:

```python
from enum import Enum
from pydantic import BaseModel

class MetricKind(str, Enum):
    GAUGE = "gauge"        # valor instantâneo (velocidade, temp, estado)
    COUNTER = "counter"    # cumulativo (refugo, produção, paradas)
    STATE = "state"        # discreta (RUN, FAULT, SETUP, ...)

class MetricDef(BaseModel):
    field: str                # nome no InfluxDB
    kind: MetricKind
    unit: str | None          # "kg", "tons", "%", "rpm"
    convert: float = 1.0      # fator (ex: gramas → toneladas)
    zero_when_off: bool = True  # se o equipamento está OFF, valor deve ser 0 ou nulo
    agg_default: str = "mean"   # agregação padrão se for gauge/state

CATALOG: dict[str, MetricDef] = {
    "descarte_linha_tons": MetricDef(
        field="refugo_op_acumulado",
        kind=MetricKind.COUNTER,
        unit="tons",
        convert=1e-6,
        zero_when_off=True,
    ),
    "velocidade": MetricDef(
        field="velocidade_real",
        kind=MetricKind.GAUGE,
        unit="rpm",
        zero_when_off=True,
        agg_default="mean",
    ),
    "estado": MetricDef(
        field="estado_codigo",
        kind=MetricKind.STATE,
        unit=None,
        zero_when_off=False,
        agg_default="mode",
    ),
    # ...
}
```

**Com isso resolvemos B1 e B2 em tempo de query.** Pipeline:

```
input: métrica + [from, to] + agg_window
  ↓
lookup MetricDef
  ↓
if COUNTER: aplica delta por janela (NON_NEGATIVE_DIFFERENCE)
if GAUGE:   aplica mean/max/min por janela
if STATE:   aplica mode/last
  ↓
aplica OFF-mask: quando estado == OFF e zero_when_off=True → valor = 0
  ↓
retorna DataFrame tidy para charts
```

### 5.2 Contrato de filtro de tempo (estilo Grafana)

```python
class TimeRange(BaseModel):
    from_: datetime  # ISO 8601 com TZ
    to: datetime
    granularity: Literal["1s","10s","1m","5m","15m","1h","1d"] | None = None
    # None = auto-escolhe baseado em range (<6h→1m, <7d→15m, etc.)
```

Frontend manda `?from=2026-04-22T06:00:00-03:00&to=2026-04-23T06:00:00-03:00&granularity=15m`. Auto-granularity no backend evita pontos demais (>5000) ou poucos (<20).

### 5.3 Formato de estado

```python
class EquipState(str, Enum):
    RUN = "RUN"
    SETUP = "SETUP"
    FAULT = "FAULT"
    PLANNED_STOP = "PLANNED_STOP"    # manutenção, refeição, troca turno
    UNPLANNED_STOP = "UNPLANNED_STOP" # falha, falta material
    OFFLINE = "OFFLINE"              # coletor sem conexão

# mapeamento de código legado (0-12, 999) → EquipState
# vive em StateMapper, único lugar
```

Isso resolve B3 (mapeamento binário) — agora Disponibilidade pode distinguir planejado vs não planejado como ISO 22400 manda.

---

## 6. Fórmulas como serviço (`app/kpis/formulas.py`)

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class OEEInputs:
    tempo_planejado_min: float
    tempo_parado_nao_planejado_min: float
    producao_boa: float
    producao_total: float
    tempo_ciclo_ideal_s: float  # ISO 22400

class OEE:
    @staticmethod
    def availability(i: OEEInputs) -> float:
        if i.tempo_planejado_min <= 0:
            return 0.0
        tempo_produtivo = max(0, i.tempo_planejado_min - i.tempo_parado_nao_planejado_min)
        return min(100.0, 100 * tempo_produtivo / i.tempo_planejado_min)

    @staticmethod
    def performance(i: OEEInputs) -> float:
        tempo_produtivo_s = max(0, (i.tempo_planejado_min - i.tempo_parado_nao_planejado_min) * 60)
        if tempo_produtivo_s <= 0:
            return 0.0
        return min(100.0, 100 * (i.producao_total * i.tempo_ciclo_ideal_s) / tempo_produtivo_s)

    @staticmethod
    def quality(i: OEEInputs) -> float:
        if i.producao_total <= 0:
            return 0.0   # corrige B2 — não inventa 100% quando parado
        return min(100.0, 100 * i.producao_boa / i.producao_total)

    @staticmethod
    def oee(i: OEEInputs) -> float:
        a = OEE.availability(i)
        p = OEE.performance(i)
        q = OEE.quality(i)
        return min(100.0, (a/100) * (p/100) * (q/100) * 100)
```

**Cobrimos com pytest parametrizado** (casos: equipamento parado 100%, OEE ideal 100%, divisão por zero, valores fora de faixa). Ver arquivo `05_EXEMPLO_FASTAPI_ANALYTICS.py` para o endpoint que consome essas classes.

---

## 7. Frontend — arquitetura de informação ISA-101

### 7.1 Princípios ISA-101 aplicados

1. **Hierarquia:** Fábrica → Área → Categoria → Linha → Equipamento (drill-down consistente)
2. **Cores semânticas contidas:** cinza para estado normal, cores saturadas **só** para desvio (vermelho=falha, amarelo=atenção)
3. **Densidade da informação por papel:** operador ≠ supervisor ≠ engenheiro de processo ≠ cientista de dados
4. **Navegação previsível:** breadcrumb, back, URL persistente (filtros no `?from=…`)

### 7.2 Estrutura da Home nova

- **Faixa superior fixa:** cards de KPI da **Fábrica** (OEE, Disponibilidade, Performance, Qualidade, Give Away, Descarte) — 6 cards, sempre na mesma ordem
- **Grid de Áreas:** cada área como card com mini-sparkline de OEE e status agregado (verde/amarelo/vermelho)
- **Drill-down:** clicar em área → ver linhas daquela área em lista compacta
- **Lista de alertas:** últimos eventos anormais (FAULT, microparada > X min, setup longo) — timeline compacta à direita

### 7.3 Sidebar nova

- **Primeiro nível:** Fábrica (expansível)
- **Segundo nível:** Áreas (A1, A2, …)
- **Terceiro nível:** Categorias (Envase / Empacotamento / Paletização) — usando `linha.categoria`
- **Quarto nível:** Linhas
- **Quinto nível:** Equipamentos (pop-out)
- Com **scroll vertical** na seção de navegação (`max-height: calc(100vh - header - footer)`)
- **Busca** no topo da sidebar (cmd+k style)

### 7.4 Analytics nova

- Range picker datetime (de/até) com presets rápidos (15min, 1h, 8h, turno, dia, semana) — estilo Grafana
- URL persistente: `?from=…&to=…&metrics=velocidade,estado&lines=L01,L02`
- Switch "ignorar quando OFF" (default: ON)
- Switch "aplicar delta em contadores" (default: ON — gerenciado pelo `MetricDef.kind`, mas visível para usuário avançado)
- Gráficos: linha (tendência), histograma, boxplot, scatter (correlação), heatmap de disponibilidade por hora × dia
- Download CSV/Parquet do filtro aplicado

---

## 8. Observabilidade

| Sinal | Ferramenta | Dashboard |
|---|---|---|
| Métricas técnicas (CPU, RAM, latência) | Prometheus + Grafana | "MIS Core / Infra" |
| Métricas de aplicação (tempo de resposta, QPS, erros 5xx) | FastAPI middleware + Prometheus | "MIS Core / API" |
| Métricas de coleta (conexão OPC, buffer SQLite, sync) | `coletor_*` Prometheus | "MIS Core / Coletor" |
| Logs estruturados | Loki | busca ad-hoc |
| Alertas | Alertmanager → Slack/email | triagem por severidade |

Cada componente **expõe `/metrics`** e **`/health`** — padronização via dependência única.

---

## 9. Segurança (sem regressão)

- JWT compartilhado Django ↔ FastAPI (via `rest_framework_simplejwt` chave pública)
- HTTPS obrigatório em produção (nginx faz terminação)
- Secrets em `.env` → migrar para **HashiCorp Vault** ou **Docker secrets** no longo prazo
- CSP headers no frontend
- Rate limiting no gateway (nginx ou Traefik)

---

## 10. O que esta arquitetura resolve (rastreamento dos problemas do diagnóstico)

| ID Diagn. | Resolução |
|---|---|
| F1-F2 (sidebar) | Item 7.3 — sidebar com 5 níveis, scroll, categorias |
| F3-F4 (home) | Item 7.2 — grid de áreas + drill-down |
| F5 (analytics fixo) | Item 5.2 — TimeRange com from/to |
| F6 (gráfico crescente) | Item 5.1 — `MetricDef.kind=COUNTER` → delta automático |
| F7-F8 (tipos, tokens) | Item 3 — `types/backend.ts` e Tailwind v4 CSS vars unificadas |
| B1 (delta) | Item 5.1 |
| B2 (Q=1 parado) | Item 6 — `quality` retorna 0 se produção=0 |
| B3 (parado planejado) | Item 5.3 — `EquipState` distingue planejado vs não |
| B4 (TPH bottleneck) | Implementar no Item 6 como `LineTPH.calculate` usando min(throughput) |
| B5 (período fixo) | Item 5.2 |
| B6 (discreta) | Refatorar em `CATALOG` explícito |
| B7 (EDA) | Item 4.1 — `/api/v2/analytics/stats` moderno |
| C1-C7 (coletor) | Item 4.4 — coletor v2 |
| Fórmulas 4.2-#1,2,3 | Item 6 — classes puras, testadas |

---

## 11. Não-objetivos (o que explicitamente **não** vamos fazer agora)

- Reescrever Django admin (funciona bem, deixa quieto)
- Trocar InfluxDB por Timescale imediatamente (avaliar só na P4 se a performance justificar)
- Migrar frontend para Next.js (não agrega, custo alto)
- Kubernetes (docker-compose resolve 80% da dor hoje)
- Microserviços distribuídos em N processos (monólito modular basta para escala atual)

---

> **Próximo passo:** ver `03_ROADMAP_EXECUCAO.md` para plano faseado com entregáveis por trimestre.
