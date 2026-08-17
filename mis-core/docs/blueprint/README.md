# Blueprint mis-core — guia de leitura

Esta pasta reúne **diagnóstico, arquitetura alvo, roadmap e protótipos** que
direcionaram a repaginação do mis-core iniciada em abril/2026.

Ela NÃO é documentação de API — para API consulte `backend-fastapi/README.md`
ou o Swagger em `/api/v2/docs`. Aqui é o **"por que" e o "para onde"**.

---

## Ordem sugerida de leitura

| # | Arquivo                             | O que você encontra                                                       | Quanto tempo |
|---|-------------------------------------|---------------------------------------------------------------------------|--------------|
| 1 | [01_DIAGNOSTICO_TECNICO.md](./01_DIAGNOSTICO_TECNICO.md) | Achados P0–P2 em coletor, backend, frontend, fórmulas. É o "raio-X". | 20 min       |
| 2 | [02_ARQUITETURA_ALVO.md](./02_ARQUITETURA_ALVO.md)    | Camadas, contratos, decisões macro (por que FastAPI, por que Strangler). | 15 min       |
| 3 | [03_ROADMAP_EXECUCAO.md](./03_ROADMAP_EXECUCAO.md)    | Sprints S1..S5 com entregáveis verificáveis e gates de GO/NO-GO.          | 10 min       |
| 4 | [04_POC_UI.html](./04_POC_UI.html)                    | Protótipo navegável da nova Home/Sidebar em ISA-101. Abrir no browser.    | 5 min        |
| 5 | [05_EXEMPLO_FASTAPI_ANALYTICS.py](./05_EXEMPLO_FASTAPI_ANALYTICS.py) | Esboço do endpoint `/api/v2/analytics/timeseries` que inspirou o código em `backend-fastapi/`. | 5 min |
| — | [../adr/ADR-001-fastapi-strangler.md](../adr/ADR-001-fastapi-strangler.md) | A decisão "Strangler Pattern", com alternativas e consequências. | 8 min        |

> **Dica:** se você tem 15 minutos, leia o **01_DIAGNOSTICO** + **ADR-001**.
> O resto você consulta sob demanda.

---

## Mapa "problema → solução → onde está implementado"

| Problema (diagnóstico)                  | Como é resolvido                                       | Arquivo principal                                         |
|-----------------------------------------|--------------------------------------------------------|-----------------------------------------------------------|
| Fórmulas duplicadas de OEE              | SSOT em `app/core/formulas.py` + testes               | `backend-fastapi/app/core/formulas.py`                    |
| "Analytics que mente" (counter como gauge) | `metrics_catalog` + `pipelines.aggregate_series`     | `backend-fastapi/app/services/pipelines.py`               |
| Sem filtro OFF-mask                     | `OffMaskConfig` + default seguro                      | `backend-fastapi/app/services/pipelines.py::apply_off_mask` |
| Filtros de tempo fixos                  | `TimeRange` Grafana-style (start/end/last/granularity) | `backend-fastapi/app/schemas/time_range.py`               |
| Blocking I/O no Flask                   | httpx async + FastAPI                                 | `backend-fastapi/app/services/influx.py`                  |
| Coletor que não se recupera do OPC      | `CircuitBreaker` + `ConnectionWatchdog` + `OfflineBuffer` | `coletor/resilience.py`                                |
| Sidebar crescendo verticalmente         | `SidebarV2` com grupos + scroll + busca               | `frontend-react/client/src/components/layout/SidebarV2.tsx` |
| Contagem legal de give-away             | `compute_give_away` com tolerância INMETRO           | `backend-fastapi/app/core/formulas.py::compute_give_away` |

---

## Convenções deste blueprint

- **P0 / P1 / P2**: severidade. P0 = bug em produção; P1 = dívida técnica
  bloqueante de funcionalidade nova; P2 = "bom de ter".
- **"ISO 22400-2"**: sempre que citamos fórmulas de KPI, este é o padrão
  de referência (Automation Systems and Integration — KPIs for manufacturing
  operations management).
- **"ISA-101"**: referência para design de HMI industrial. Regra-mestra
  que aplicamos: "cores saturadas SÓ para estado de alarme".
- **Decisões grandes** viram ADRs em `docs/adr/` (um arquivo por decisão).

---

## Como contribuir com este blueprint

1. Para adicionar um novo problema descoberto, crie uma seção em
   `01_DIAGNOSTICO_TECNICO.md` com o padrão **P{n}.{sub} — título**.
2. Para decisões arquiteturais novas, crie um ADR em `docs/adr/ADR-00X-...md`
   copiando a estrutura do ADR-001.
3. O roadmap (`03_ROADMAP_EXECUCAO.md`) é atualizado no fim de cada sprint —
   mantenha as métricas "antes/depois" para provar evolução.
