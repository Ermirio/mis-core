# 🗺️ Roadmap de Execução — mis-core v2

> **Horizonte:** 4 trimestres (12 meses)
> **Abordagem:** strangler pattern — nada quebra, valor entregue toda sprint
> **Analogia WCM:** cada fase é um pilar do edifício TPM/WCM. Começamos por *Qualidade do Dado* (o alicerce), depois *Autonomia da Máquina* (coletor), depois *Melhoria Focada* (UI) e por fim *Inovação* (IA/ML).

---

## Princípios do roadmap

1. **Valor primeiro.** A cada fase o usuário vê diferença. Nada de 3 meses de refatoração invisível.
2. **Nada quebra.** Sistema atual continua operando em paralelo. Novo vira default só depois de validado.
3. **Observável desde o primeiro dia.** Cada componente novo nasce com `/health` e métricas.
4. **Testável.** Fórmulas, queries e lógica de negócio têm testes automatizados desde a P0.
5. **Documentado inline.** ADRs (Architecture Decision Records) curtos para cada decisão grande.

---

## P0 — "Parar de mentir" (Semanas 1–4)

**Objetivo:** corrigir **o que está mostrando dado errado** e estabilizar o coletor. Dor do usuário zero, zero. É o kaizen de 5 dias aplicado ao sistema.

### Entregáveis

| # | Entregável | Arquivo(s) afetados | Esforço |
|---|---|---|---|
| P0.1 | **Delta em contadores acumulados** | `backend-flask/blueprints/analytics.py:95` — aplicar `apply(lambda x: max(0, x.iloc[-1]-x.iloc[0]))` por janela. Alternativa: mudar para Flux com `nonNegativeDerivative()`. | S |
| P0.2 | **Qualidade = null quando produção=0** | `backend-flask/production_engine.py:413-419` — retornar `None` ao invés de 1.0. Ajustar agregador Django para ignorar `None`. | S |
| P0.3 | **OFF-mask no analytics** | `backend-flask/blueprints/analytics.py` — adicionar parâmetro `exclude_states=[OUTRO,OFFLINE]` no endpoint e aplicar filtro antes de agregar. | M |
| P0.4 | **Coletor: reconexão exponencial** | `coletor/coletor.py` — envolver `connect()` em `tenacity.retry(wait=wait_exponential(1,32), stop=stop_after_attempt(10))`. Logar stack trace (`exc_info=True`). | M |
| P0.5 | **Coletor: watchdog assíncrono** | `coletor/coletor.py` — `asyncio.create_task(watchdog(url))` por URL, derruba conexões mortas a cada 30s. | M |
| P0.6 | **Coletor: buffer SQLite** | `coletor/coletor.py` + novo `coletor/buffer.py` — aiosqlite com tabela `pending_readings`; sync task a cada 60s. | L |
| P0.7 | **Escala OEE + TPH correto** | `backend-flask/production_engine.py:421` e `backend-flask/kpis_engine.py:14` — remover `× 100` duplo e `× qualidade` em TPH. | S |
| P0.8 | **Sidebar com scroll** | `frontend-react/client/src/components/layout/Sidebar.tsx:115` — `overflow-y: auto; max-height: calc(100vh - 160px)`. | S |
| P0.9 | **ADR-001: decisão pelo FastAPI incremental** | `docs/adr/ADR-001-fastapi-strangler.md` | S |
| P0.10 | **Testes pytest para fórmulas corrigidas** | `backend-flask/tests/test_formulas.py` — cobrir os 3 bugs corrigidos. | M |

### Métricas de sucesso (DoD)

- ✅ Gráfico de tendência em `/analytics` mostra **oscilação real** (não monotônico crescente)
- ✅ Equipamento desligado por 1h não contribui com `Qualidade=100%` no EDA
- ✅ Matando PLC (simulado): coletor volta a subir sozinho em < 60s após PLC voltar
- ✅ Matando Django temporariamente: coletor continua rodando, buffer local enche, sincroniza depois
- ✅ `pytest backend-flask/tests/` passa 100%
- ✅ Sidebar rola com 50+ linhas mockadas

**Ganhos concretos:** confiabilidade dos dados + operação mais autônoma.

---

## P1 — "Construir a nova frente" (Semanas 5–10)

**Objetivo:** subir o FastAPI v2 ao lado dos backends atuais, com **o endpoint mais crítico** (analytics de tendência com tudo que P0 arrumou). Redesenhar Home + Sidebar com ISA-101.

### Entregáveis

| # | Entregável | Descrição | Esforço |
|---|---|---|---|
| P1.1 | **Scaffold FastAPI v2** | Nova pasta `backend-fastapi/` com Uvicorn, Pydantic v2, pytest, ruff, mypy. Endpoint `/api/v2/health`. | M |
| P1.2 | **Metric Catalog** | `backend-fastapi/app/metrics_catalog.py` — centraliza todas as métricas, com tipo (gauge/counter/state) e flag `zero_when_off`. | M |
| P1.3 | **Endpoint `/api/v2/analytics/trends`** | Recebe `from`, `to`, `granularity`, `metrics`, `equipamentos`, aplica lógica do Metric Catalog. Retorna série tidy. | L |
| P1.4 | **Endpoint `/api/v2/analytics/stats`** | EDA moderno: min/max/mean/std/p50/p90/p99, IQR, outliers (Z-score + IQR), histograma, Cp/Cpk (mantém do Flask). | L |
| P1.5 | **Endpoint `/api/v2/kpis/factory`** | `?from=…&to=…` — substitui endpoint legado com `period=turno\|dia\|…`. | M |
| P1.6 | **Formulas lib (`kpis/formulas.py`)** | Classes `OEE`, `LineTPH` (bottleneck), `GiveAway` (com tolerância INMETRO). Testes pytest parametrizados. | M |
| P1.7 | **Gateway nginx com rotas** | Configurar `/api/v2/*` → FastAPI, outras rotas legadas preservadas. | S |
| P1.8 | **Sidebar ISA-101** | `Sidebar.tsx` refatorada: busca + 5 níveis de hierarquia (Fábrica→Área→Categoria→Linha→Equipamento) com Radix Accordion. | L |
| P1.9 | **Home redesenhada** | Faixa de KPIs da fábrica (6 cards) + grid de áreas com status agregado + drill-down + lista de alertas. | L |
| P1.10 | **Frontend: React Query** | Substituir `fetch + useState` por `useQuery` com cache e retry. | M |
| P1.11 | **Frontend: DateRange persistido** | Integrar `DateRangePicker` existente em Analytics, persistir no URL (`?from=…&to=…`). | M |
| P1.12 | **Design tokens unificados** | `client/src/design-tokens.css` com cores ISA-101 (cinza dominante, vermelho contido, amarelo atenção). Consumido por Tailwind + componentes. | M |

### Métricas de sucesso (DoD)

- ✅ `/api/v2/analytics/trends` responde com delta aplicado, <500ms para 24h de dados
- ✅ Contract tests (schemathesis) passam no FastAPI v2
- ✅ Nova Home renderiza < 1s com 100 linhas mockadas
- ✅ Navegação até um equipamento leva ≤ 3 cliques
- ✅ Sidebar rola e agrupa por categoria
- ✅ Analytics aceita range datetime arbitrário (testado com from=2026-01-01, to=2026-04-23)

**Ganhos concretos:** novo stack funcional, UX hierárquica, fundação pronta para escalar.

---

## P2 — "Migrar de vez" (Semanas 11–18)

**Objetivo:** aposentar a maioria dos endpoints Flask. Manter só Django (admin) + FastAPI (tudo novo). Introduzir observabilidade completa.

### Entregáveis

| # | Entregável | Esforço |
|---|---|---|
| P2.1 | **Migrar `/analyze/stats`, `/correlation`, `/timeseries`** do Flask para FastAPI v2 | L |
| P2.2 | **Migrar `/api/fabrica/kpis`, `/api/linha/<id>/*`** para FastAPI | L |
| P2.3 | **Decomissionar Flask** (manter um Dockerfile "freeze" apenas para rollback) | S |
| P2.4 | **Prometheus + Grafana em docker-compose** com 4 dashboards: Infra, API, Coletor, KPIs | M |
| P2.5 | **Loki para logs estruturados** (structlog no Python, winston no Node Express) | M |
| P2.6 | **Alertmanager**: regras para OPC disconnect > 5min, buffer coletor > 1000 reads, erro 5xx > 1% | M |
| P2.7 | **Equipment detail page refatorada** | M |
| P2.8 | **WebSocket realtime** (`/api/v2/realtime/{line_id}`) substitui polling de `/ole-realtime` | L |
| P2.9 | **Auth JWT compartilhado Django↔FastAPI** com `rest_framework_simplejwt` | M |
| P2.10 | **Calendário de produção** (Django Admin) com tempos planejados por linha/turno — alimenta Disponibilidade correta | M |
| P2.11 | **Testes E2E** com Playwright para 5 fluxos principais | L |

### Métricas de sucesso

- ✅ Flask reduzido a < 10% do tráfego (medido via nginx access logs)
- ✅ 4 dashboards Grafana operacionais
- ✅ Alertas chegando no canal certo em < 2min
- ✅ Disponibilidade ISO 22400 real (planejado vs não planejado) visível no dashboard
- ✅ Latência p95 do novo backend < 300ms

---

## P3 — "Inteligência" (Semanas 19–30)

**Objetivo:** o core vira **central de inteligência**. ML básico, detecção de anomalias, Golden Batch automatizado, sugestões proativas.

### Entregáveis

| # | Entregável | Detalhes |
|---|---|---|
| P3.1 | **Golden State automatizado** | Serviço que, dado janela de tempo com OEE alto + Give Away baixo + refugo baixo, calcula envelope de parâmetros (velocidade, temperatura, pressão, setpoints) e expõe `/api/v2/golden/{line_id}` |
| P3.2 | **Detecção de anomalias por equipamento** | Isolation Forest ou autoencoder simples treinado em Airflow/Prefect, inference online via FastAPI. Alertas: "anomalia em velocidade da Enchedora 3 há 8min" |
| P3.3 | **Previsão de falha (PdM MVP)** | Modelo simples (XGBoost) treinado em histórico: entrada = métricas últimas 2h, saída = probabilidade de FAULT nas próximas 30min |
| P3.4 | **Decomposição STL + sazonalidade** | Analytics mostra tendência, sazonalidade (turno/dia/semana) e resíduo — essencial para EDA real |
| P3.5 | **Comparador de linhas** | "Linha A vs Linha B no mesmo SKU" — grande player clássico |
| P3.6 | **Relatórios automatizados** | Geração de PDF diário/semanal por linha (jinja2 + weasyprint), envio por e-mail |
| P3.7 | **MCP Server interno** | Expor metadados do sistema como MCP para que um agente (Claude/outro) possa operar como "copiloto" ao engenheiro de processo: "Claude, por que a Linha 3 caiu 20% de OEE ontem?" |
| P3.8 | **Análise de perdas estruturada** | Árvore de perdas WCM visual (paradas → planejadas / não planejadas / microparadas / velocidade < nominal / refugo / retrabalho) |

### Métricas de sucesso

- ✅ 3 modelos ML em produção com acurácia monitorada
- ✅ Golden Batch sendo consultado pelo menos 10× por semana
- ✅ Pelo menos 1 caso real de anomalia detectada antes da parada

---

## P4 — "Escalar e consolidar" (Semanas 31–52)

**Objetivo:** maturar. Performance, escala para múltiplas plantas, extensibilidade.

### Entregáveis

| # | Entregável |
|---|---|
| P4.1 | Avaliar TimescaleDB para histórico > 90 dias (Influx fica só para hot data) |
| P4.2 | Multi-tenant: mesmo core servindo múltiplas plantas (header `X-Plant-Id` + RLS) |
| P4.3 | MQTT Sparkplug B no coletor para suportar brokers além de OPC UA |
| P4.4 | Edge computing: coletor rodando em mini-PC por linha (redundância) |
| P4.5 | Integrações: SAP PM, MES principal, Weighing systems |
| P4.6 | Mobile app (React Native) para supervisores em chão de fábrica |
| P4.7 | Plugin system — cada tipo de equipamento com "pacote" (tags OPC + fórmulas + dashboard padrão) |
| P4.8 | Documentação pública (mkdocs) |
| P4.9 | Performance: cache Redis agressivo em queries recorrentes; paginar endpoints de lista |
| P4.10 | Segurança: audit log, Vault para secrets, pen test anual |

---

## Cronograma visual

```
Sem:  1      4      8     12     16     20     24     28     32      52
      │      │      │      │      │      │      │      │      │       │
P0  ▓▓▓▓▓▓▓▓│
            │
P1         ▓▓▓▓▓▓▓▓▓▓▓▓▓▓│
                         │
P2                      ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│
                                         │
P3                                      ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│
                                                              │
P4                                                           ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
```

---

## Governança e qualidade

### Definition of Ready (DoR)

Toda história só entra no sprint se tem:
- Descrição clara + critério de aceite
- Impacto estimado (alto/médio/baixo)
- Esforço estimado (S/M/L = 1d / 3d / 1-2 semanas)
- Dependências mapeadas

### Definition of Done (DoD)

Toda entrega só é marcada pronta quando:
- Testes automatizados passam (pytest + vitest)
- Cobertura de testes da feature nova ≥ 70%
- `ruff check` + `mypy` + `tsc --noEmit` sem erro
- Revisão de código (mínimo 1 aprovação)
- Métrica e health endpoint expostos se for serviço novo
- Documentação atualizada (README ou ADR)

### Rituais sugeridos

| Ritual | Frequência | Saída |
|---|---|---|
| Planning | semanal (1h) | sprint com 3-5 histórias |
| Standup | diário (15min) | bloqueios expostos |
| Review | semanal (30min) | demo ao usuário |
| Retro | quinzenal (1h) | 1 ação de melhoria |
| ADR review | mensal (1h) | decisões documentadas |

---

## Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Dados antigos do InfluxDB incompatíveis com novo pipeline | Média | Alto | Testes com snapshot de produção logo na P0. Flag de compatibilidade no Metric Catalog |
| Coletor em produção não tolera restart para trocar código | Alta | Médio | Deploy canário: 1 linha migrada por vez. Rollback via docker-compose |
| Usuários acostumados com KPIs "inflados" vão reclamar quando virem números reais | Alta | Médio | Comunicar antes: "os números vão baixar porque agora estão corretos". Rodar paralelo por 2 semanas mostrando old vs new |
| FastAPI e Django compartilhando DB causa conflito de migrations | Média | Alto | FastAPI **lê** via asyncpg, **escreve** via Django ORM quando precisa. Nunca migrations duplicadas |
| Engenheiro único operando tudo | Alta | Alto | Documentação obsessiva, ADRs, pairing programming em features críticas |

---

## Investimento estimado

| Fase | Duração | Perfis envolvidos | Custo relativo |
|---|---|---|---|
| P0 | 4 sem | 1 full-stack + você | 1x |
| P1 | 6 sem | 1 full-stack + 1 designer part-time | 2x |
| P2 | 8 sem | 1 full-stack + 1 SRE part-time | 2x |
| P3 | 12 sem | 1 full-stack + 1 ciêntista de dados | 3x |
| P4 | 22 sem | 1-2 full-stack + 1 SRE + 1 DS | 4-5x |

---

## Próximo passo imediato

Abrir `04_POC_UI.html` (duplo-clique no arquivo) para ver o **protótipo da nova UI navegável** e `05_EXEMPLO_FASTAPI_ANALYTICS.py` para o **código-exemplo do endpoint de analytics**. Depois, ataca-se **P0.1 a P0.7** — são 2 semanas de esforço real para ganhar meses de confiança.
