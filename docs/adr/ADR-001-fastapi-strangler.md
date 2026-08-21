# ADR-001 — Migração Flask/Django → FastAPI via Strangler Pattern

- **Status:** Aceito
- **Data:** 2026-04-23
- **Autores:** Ermírio (PO/Arquitetura), Claude (consultoria técnica)
- **Contexto desta decisão:** documento 01_DIAGNOSTICO_TECNICO.md (achados P0.1–P0.10)

---

## 1. Contexto

O backend do mis-core hoje é híbrido:

- **Django** (`backend-django/`) — ORM/admin, modelos de linhas, equipamentos,
  ordens, conexões OPC, usuários.
- **Flask** (`backend-flask/`) — endpoints de analytics, KPIs, produção,
  integração com InfluxDB.

Problemas documentados:

1. **Duplicação crítica de fórmulas de OEE** (`production_engine` vs
   `kpis_engine`), gerando discrepâncias visíveis para os operadores.
2. **Blocking I/O no event loop** — o Flask é síncrono (WSGI), e chamadas
   paralelas ao Influx serializam, elevando o p95 de latência.
3. **Falta de tipos fortes nos contratos** — hoje as requests são `dict`s
   livres; o usuário passa `exclude_states: "oi"` e o servidor retorna 500.
4. **Analytics "que mente"** — Flask usa `groupby.mean()` em contadores
   cumulativos, produzindo gráficos "sempre crescentes". Corrigido parcialmente
   em P0.1 (counter-delta) e P0.3 (OFF-mask).
5. **Filtros de tempo fixos** (24h/7d/30d) em vez de um TimeRange Grafana-style.

Uma reescrita completa (big-bang) foi considerada e rejeitada: mis-core está
em produção, com integrações externas (coletor OPC, Node-RED, dashboards
Grafana). Um freeze de 3–6 meses para reescrever é **inaceitável** para
operação.

---

## 2. Decisão

Adotar **Strangler Pattern** (Martin Fowler, 2004) para migrar incrementalmente
Flask/Django → FastAPI, com três princípios inegociáveis:

1. **Legado e novo coexistem** por no mínimo 3 releases. Nada é desligado
   enquanto o equivalente v2 não estiver em produção há ≥ 2 semanas sem
   regressão.
2. **Roteamento por prefixo na borda** (nginx):
   - `/api/*`     → Flask/Django legado (status quo)
   - `/api/v2/*`  → FastAPI novo
3. **Fonte única de verdade para lógica de negócio** — todas as fórmulas
   vivem em `backend-fastapi/app/core/formulas.py`. Quando o Flask precisar
   destas fórmulas, ele **chama o FastAPI via HTTP interno** (ou imita os
   testes) — não reimplementa.

---

## 3. Arquitetura alvo

```
┌────────────────┐     /api/*         ┌─────────────────────┐
│  React SPA     │ ─────────────────> │ Flask + Django v1   │  (legado)
│                │                    │ (Postgres + Influx) │
│                │     /api/v2/*      ├─────────────────────┤
│                │ ─────────────────> │ FastAPI v2          │
└────────────────┘                    │ (Postgres + Influx) │
        │                             └─────────────────────┘
        │ WebSocket /ws (futuro)                 │
        ▼                                        ▼
┌────────────────┐                    ┌─────────────────────┐
│ Live KPI panel │                    │ Coletor OPC UA      │
│ (read-only)    │                    │ (Python asyncua)    │
└────────────────┘                    └─────────────────────┘
```

---

## 4. Ordem de migração (Strangler, por verticais)

Cada etapa entrega valor **sozinha** — regra de ouro.

| Sprint | Vertical migrada para v2              | Flask ainda atende                     | Crítério de desligamento do v1   |
|-------:|---------------------------------------|----------------------------------------|----------------------------------|
| S1     | `/api/v2/analytics/{stats,timeseries,correlation}` | `/api/analytics/*` (fallback)          | ≥ 14 dias sem divergência > 1 %  |
| S2     | `/api/v2/kpis/{oee,tph,give-away}`   | `/api/oee`, `/api/tph` legados         | Idem + test-coverage ≥ 90 %     |
| S3     | `/api/v2/healthz`, `/ready`, `/metrics` | (Flask perde o `/health`)              | Observabilidade cobrindo 100 %   |
| S4     | Modelos de leitura Django → SQL async | Django ORM mantém escrita              | Read-path com p95 ≤ Django p95   |
| S5     | Escrita OPC events → FastAPI          | Flask morre                            | Nginx sem `location /api/`       |

---

## 5. Alternativas consideradas

### (a) Migração big-bang (reescrever tudo, trocar num deploy)
- Pros: Sem débito de conviver com dois stacks.
- Contras: Risco inaceitável — mis-core é *operacional*; janela de manutenção
  longa custa turnos de produção; rollback caro.
- **Rejeitado.**

### (b) Ficar em Flask + Django "para sempre"
- Pros: Zero migração, time já conhece.
- Contras: Os problemas P0 não vão sumir sozinhos; Flask síncrono não escala
  para WebSocket e streaming; Pydantic/FastAPI dão muito mais garantia de
  contrato; Swagger auto-gerado.
- **Rejeitado.**

### (c) Migrar para outra stack (Go/Node/.NET)
- Pros: performance melhor que Python em CPU-bound.
- Contras: Perdemos a compatibilidade com o ecossistema científico
  (pandas/numpy/scipy) que o Analytics precisa. Nosso bottleneck é I/O
  (Influx), não CPU. FastAPI + asyncio resolve o I/O.
- **Rejeitado.**

---

## 6. Consequências

### Positivas
- Reduz risco operacional (pode rollback por endpoint).
- OEE consistente — uma fórmula em um lugar com testes.
- Tipagem forte (Pydantic v2 → 422 no cliente em vez de 500 no server).
- Abre porta para WebSocket (/ws/live) e streaming.
- Swagger UI automático em `/api/v2/docs` — documentação sempre viva.

### Negativas / custos
- Dois runtimes Python em produção por vários meses (~150 MB extra RAM).
- DevOps precisa manter dois pipelines de build e CI.
- Regras do nginx ficam mais complexas durante a transição.
- Código novo precisa espelhar comportamento legado onde diverge — isso
  é documentado via "compat test" (comparar v1 × v2 em staging).

### Mitigações
- **Observabilidade**: Prometheus conta requests por prefixo — dá para ver
  volume caindo no /api/* legado ao longo das sprints.
- **Feature flag de frontend**: `localStorage.apiVariant = "v2"` permite
  que o próprio Ermírio troque de lado em tempo real durante testes.
- **Shadow traffic**: por 2 semanas, um middleware no Flask poderá chamar
  também o FastAPI (`mirror=true`) e logar diferenças sem afetar o usuário.

---

## 7. Referências

- Fowler, "StranglerFigApplication" (2004).
- Newman, *Building Microservices*, cap. "Decomposing a Monolith".
- ISO 22400-2 (KPIs para manufacturing).
- [docs/blueprint/02_ARQUITETURA_ALVO.md](../blueprint/02_ARQUITETURA_ALVO.md).
- [docs/blueprint/03_ROADMAP_EXECUCAO.md](../blueprint/03_ROADMAP_EXECUCAO.md).
