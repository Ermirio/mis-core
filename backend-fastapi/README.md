# mis-core FastAPI v2

> Camada **nova** do backend do mis-core. Substitui progressivamente Flask/Django
> usando **Strangler Pattern** — coexiste com o legado sob prefixos diferentes
> (`/api/*` = Flask; `/api/v2/*` = FastAPI).

---

## Por que existe

O backend legado em Flask/Django tinha três dívidas críticas que este serviço resolve:

1. **Analytics que mente** — tratava contadores cumulativos (COUNTER) como
   sensores contínuos (GAUGE), gerando gráficos "sempre crescentes". Aqui,
   cada métrica passa por um *catálogo de kind* e recebe a agregação certa
   (`MEAN`, `DELTA` reset-tolerante, `LAST`, `COUNT`). Veja
   [`app/core/metrics_catalog.py`](./app/core/metrics_catalog.py) e
   [`app/services/pipelines.py`](./app/services/pipelines.py).
2. **KPIs inconsistentes** — OEE vivia em dois lugares do Flask com cappings
   diferentes. Aqui, *uma* fonte de verdade em
   [`app/core/formulas.py`](./app/core/formulas.py), com testes.
3. **Filtros de tempo fixos** — "Últimas 24h / 7d / 30d" apenas. Agora há
   `TimeRange` Grafana-style com `start`/`end`/`last` e granularidade auto
   ([`app/schemas/time_range.py`](./app/schemas/time_range.py)).

---

## Estrutura

```
backend-fastapi/
├── app/
│   ├── main.py                  # factory create_app() + CORS + routers
│   ├── config.py                # pydantic-settings (.env)
│   ├── core/
│   │   ├── formulas.py          # OEE, TPH, GiveAway, counter_delta (SSOT)
│   │   └── metrics_catalog.py   # kinds, EquipState, DEFAULT_EXCLUDE_STATES
│   ├── schemas/
│   │   ├── time_range.py        # TimeRange Grafana-style
│   │   └── analytics.py         # contratos da API v2
│   ├── services/
│   │   ├── influx.py            # httpx async -> Influx 1.x
│   │   └── pipelines.py         # OFF-mask + aggregate_series + stats
│   └── routers/
│       ├── health.py            # /healthz (liveness) + /ready (Influx check)
│       ├── analytics.py         # /analytics/{stats,timeseries,correlation}
│       └── kpis.py              # /kpis/{oee,tph,tph/line,give-away}
├── tests/
│   ├── conftest.py
│   ├── test_formulas.py         # testes dos 4 bugs P0
│   ├── test_time_range.py
│   └── test_pipelines.py        # OFF-mask + agregação kind-aware
├── Dockerfile
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Como rodar

### 1. Local (desenvolvimento)

```bash
cd backend-fastapi
python -m venv .venv && source .venv/bin/activate   # Linux/Mac
# ou .venv\Scripts\activate  (Windows)
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Acesse:
- `http://localhost:8000/api/v2/docs` — Swagger UI
- `http://localhost:8000/api/v2/healthz` — liveness
- `http://localhost:8000/api/v2/ready` — readiness (testa Influx)

### 2. Docker

```bash
docker build -t mis-core-api:v2 .
docker run --rm -p 8000:8000 --env-file .env mis-core-api:v2
```

### 3. Testes

```bash
pytest -v
# com cobertura:
pytest --cov=app --cov-report=term-missing
```

---

## Endpoints da API v2

| Método | Rota                           | O que faz                                              |
|--------|--------------------------------|--------------------------------------------------------|
| GET    | `/api/v2/healthz`              | Liveness — confirma processo vivo                      |
| GET    | `/api/v2/ready`                | Readiness — valida Influx, etc                         |
| POST   | `/api/v2/analyze/stats`      | Descritiva + Cp/Cpk + histograma                       |
| POST   | `/api/v2/analyze/timeseries` | Série agregada com UCL/LCL (Shewhart)                  |
| POST   | `/api/v2/analyze/correlation`| Matriz de correlação (pearson/spearman) + scatter data |
| POST   | `/api/v2/kpis/oee`             | OEE ISO 22400-2 + flags de validade                    |
| POST   | `/api/v2/kpis/tph`             | TPH de equipamento (sem quality — anti double-counting)|
| POST   | `/api/v2/kpis/tph/line`        | TPH da linha = gargalo                                 |
| POST   | `/api/v2/kpis/give-away`       | Give-Away INMETRO-aware                                |

### Exemplo — `/api/v2/analyze/timeseries`

```json
POST /api/v2/analyze/timeseries     # mesma forma de URL do Flask /api/analyze/timeseries
{
  "variables": [
    { "tag_influx": "velocidade_atual", "equipamento_code": "ENV01", "alias": "v" }
  ],
  "time_range": { "last": "24h" },
  "exclude_states": null
}
```

Resposta (recortada):

```json
{
  "v": {
    "timestamps": ["2026-04-22T00:00:00+00:00", "..."],
    "values": [62.3, 61.9, null, 63.1, ...],
    "stats": { "mean": 62.0, "std": 1.4, "ucl": 66.2, "lcl": 57.8, ... }
  }
}
```

Os `null` nos `values` não são bug — são janelas em que o equipamento
estava em estado excluído pela OFF-mask (FAULT/MAINTENANCE/etc.), portanto
não devem "poluir" a média nem aparecerem como zero.

---

## Strangler Pattern — plano de migração

```
Hoje                           Intermediário                   Destino
────                           ─────────────                   ───────
nginx → Flask (/api/*)         nginx → Flask (/api/*)          nginx → FastAPI (/api/*)
                               nginx → FastAPI (/api/v2/*)     (Flask morre)
React chama /api/*             React chama /api/v2/* novos     React chama /api/*
                               /api/* legados p/ compat
```

1. Frontend começa chamando `/api/v2/analyze/*` nos componentes novos.
2. Endpoint a endpoint, o legado é desligado e o Flask perde volume.
3. Quando `/api/v2` cobrir 100% da UI nova, nginx troca o prefixo.

Ver [`docs/adr/ADR-001-fastapi-strangler.md`](../docs/adr/ADR-001-fastapi-strangler.md)
(a ser criado junto com a documentação do projeto).

---

## Observações importantes

- **Segurança**: `JWT_SECRET` deve ser idêntico ao do Django para permitir
  validação cruzada de tokens durante o período híbrido.
- **Pool Influx**: o `InfluxAsyncClient` usa `httpx.AsyncClient` efêmero por
  request. Quando o tráfego aumentar, promover a pool global (ver TODO em
  `app/services/influx.py`).
- **Prometheus**: `/metrics` é exposto automaticamente se
  `prometheus-fastapi-instrumentator` estiver instalado (Dockerfile já instala).
- **Testes não cobrem Influx real**: os testes de `pipelines` usam DataFrames
  sintéticos; a integração com Influx deve ser testada em staging.

---

## Próximos passos

- [ ] Integração com `asyncpg` para metadados de linhas/equipamentos
- [ ] Endpoint `/api/v2/eda/compare` — comparar dois turnos lado a lado
- [ ] WebSocket `/ws/live` para streaming de KPIs em tempo real
- [ ] Integração com OPC UA direto (bypass do coletor em Python)
