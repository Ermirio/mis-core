# 🩺 Diagnóstico Técnico — mis-core (HUB Industrial)

> **Gerado em:** 2026-04-23
> **Escopo:** frontend React, backend Django, backend Flask, coletor OPC UA, fórmulas KPI
> **Objetivo:** fotografia honesta do estado atual, com ponteiros precisos (arquivo:linha) para tudo que vamos consertar.

---

## 🎯 Sumário Executivo

O sistema está **funcional**, mas apresenta **três classes de dívida** que se reforçam mutuamente:

1. **Dívida de modelagem de dados** — contadores acumulados sendo exibidos sem `delta`, métricas que persistem valores antigos quando equipamento fica OFF, KPIs que rodam sem tratamento de estado.
2. **Dívida de arquitetura de UI** — Sidebar e Home crescem linearmente com o número de linhas; não há hierarquia ISA-101 (Fábrica → Área → Categoria → Linha → Equipamento).
3. **Dívida de resiliência** — coletor OPC não se recupera de quedas, sem buffer local de dados, sem health endpoint, sem métricas observáveis.

**Analogia WCM:** é como uma linha de envase que produz bem em regime estável, mas onde qualquer microparada do PLC derruba a linha inteira até alguém ir lá reiniciar — e onde os indicadores de OEE ainda mostram 95% porque o sensor congelou no último valor. Nosso trabalho é transformar isso em um **processo auto-regulado** (Jidoka) com capacidade de se recuperar e de mostrar a verdade.

---

## 1. Frontend React — `frontend-react/client/src`

### 1.1 Stack confirmada

| Item | Versão |
|---|---|
| React | 18.3.1 |
| React Router | 7.9.6 |
| Vite | 7.1.7 |
| TypeScript | 5.6.3 |
| Tailwind | 4.1.14 |
| Radix UI / shadcn | 1.2.x |
| Recharts | 2.15.2 |
| Plotly.js | 3.3.1 *(híbrido — reduntante com Recharts)* |
| date-fns | 4.1.0 |
| Fetch layer | `fetch()` nativo + axios (pontual). **Sem React Query.** |

### 1.2 Problemas identificados

| # | Severidade | Arquivo:Linha | Problema |
|---|---|---|---|
| F1 | 🔴 Alto | `components/layout/Sidebar.css:116-123` + `Sidebar.tsx:115-128` | `.sidebar-nav` tem `flex: 1` mas **não tem `overflow-y: auto`** — lista de linhas não rola. Com 50+ linhas, itens somem fora da viewport ou empurram o footer pra fora. |
| F2 | 🔴 Alto | `components/layout/Sidebar.tsx:109-128` | Renderização plana com `linhas.map()` — sem agrupamento por categoria (Envase/Empacotamento/Paletização) nem por área. |
| F3 | 🔴 Alto | `pages/Home.tsx:401-431` | Grid `grid-cols-1 2xl:grid-cols-2` renderiza cada linha como card grande. Home cresce linearmente → scroll ilimitado. |
| F4 | 🟡 Médio | `pages/Home.tsx:96-250` | Sem drill-down ISA-101 (Fábrica → Área → Linha → Equipamento). Toda a fábrica é exibida no mesmo nível visual. |
| F5 | 🔴 Alto | `pages/LineAnalytics.tsx:258-259` | `hoursBack = '8'` hardcoded. `DatePickerWithRange` existe no projeto (`components/DateRangePicker.tsx`) mas não está integrado à Analytics. |
| F6 | 🔴 Crítico | `components/ui/ProductionChart.tsx:54-68` | Cálculo `toneladas_acumuladas[i] = arr[i-1].toneladas_acumuladas + curr.toneladas_real` **sem zerar** quando equipamento vai OFF/reset de turno. É **a causa visível** do "gráfico sempre crescendo". |
| F7 | 🟡 Médio | `config/api.ts:10-15` | URLs hardcoded (`/api`, `/flask-api`). Tipos TypeScript duplicados em Home.tsx, LineAnalytics.tsx e outros — mudança de campo no Django quebra N telas. |
| F8 | 🟢 Baixo | `components/layout/Sidebar.css:1-14` | CSS variables redefinidas em CSS + Tailwind config. Sem arquivo único de design tokens (cores ISA-101, tipografia, spacing). |

### 1.3 O que aproveitar vs reescrever

| Componente | Reaproveitar | Reescrever |
|---|---|---|
| `Sidebar.tsx` | Estilo e ícones | Container rolável + agrupamento por categoria |
| `Home.tsx` | Lógica OLE / fetch | Substituir grid por árvore hierárquica + drill-down |
| `DateRangePicker.tsx` | Presets e popover prontos | Integrar em Analytics + persistir no URL (?from=…&to=…) |
| Charts Recharts | Componentes base | Camada de pré-processamento (delta, OFF-mask) |
| Hooks `useRealTimeData` | Padrão OK | Migrar para React Query (cache, invalidation, retry) |

---

## 2. Backend Analytics — Flask + Django

### 2.1 Endpoints mapeados

**Flask (`backend-flask/blueprints/analytics.py`):**
- `POST /analyze/stats` — descritivas + Cp/Cpk + histograma ✅
- `POST /analyze/correlation` — Pearson/Spearman + scatter ✅
- `POST /analyze/timeseries` — série temporal + UCL/LCL 3σ ✅ (aceita datetime range)

**Flask KPIs (`backend-flask/kpis_routes.py`):**
- `GET /api/linha/<linha>/kpis` — KPIs por linha
- `GET /api/equipamento/<eq>/kpis`
- `GET /api/fabrica/kpis?period=turno|dia|semana|mes` — **só períodos fixos**

**Flask Realtime (`backend-flask/routes.py`):**
- `GET /api/realtime/all`, `/api/linha/<linha>/status`, `.../ole-realtime`, `.../overview-status`, `.../kpis`, `.../timeline`, `.../historico`
- `GET /api/equipamento/<codigo>/historico-detalhado`

**Django (`backend-django/analytics/`):**
- CRUD de `/api/analytics-profiles/` — salvar perfis de análise (ok, útil).

### 2.2 Problemas críticos

| # | Severidade | Arquivo:Linha | Problema |
|---|---|---|---|
| B1 | 🔴 Crítico | `backend-flask/blueprints/analytics.py:95` | `combined.groupby('equipment')[influx_field].resample('1min').last().groupby(level=1).sum()` — pega o **último valor** por minuto e soma. Para **contadores acumulativos** (`refugo_op_acumulado`, `producao_acumulada`, etc.), isso produz série **sempre crescente**. Deveria aplicar `.apply(lambda x: x.iloc[-1] - x.iloc[0])` (delta no intervalo) ou `NON_NEGATIVE_DIFFERENCE()` no Flux. |
| B2 | 🔴 Crítico | `backend-flask/production_engine.py:413-419` | `qualidade = 1.0` por padrão, só recalcula se `total_prod_op > 0`. **Equipamento parado → Qualidade = 100% eternamente**, poluindo o EDA e inflando KPIs. |
| B3 | 🔴 Alto | `backend-flask/production_engine.py:302-304` | `if state['last_estado'] != 1: acc_time_stop_shift += delta` — mapeamento binário "parado/produzindo". Não distingue parada planejada (setup, manutenção agendada) da não planejada, o que a ISO 22400 exige. |
| B4 | 🔴 Alto | `backend-flask/factory_kpis_engine.py:252, 307` | TPH da linha usa `MAX(toneladas_turno)` dos equipamentos. **Conceitualmente errado:** TPH de linha = throughput do **gargalo** (bottleneck = equipamento mais lento ou com maior lead time), não o maior contador. |
| B5 | 🟡 Médio | `backend-flask/kpis_routes.py:34-42` | `/api/fabrica/kpis` só aceita `period=turno|dia|semana|mes`. Precisa aceitar `?from=ISO&to=ISO&agg=1m|5m|1h|1d`. |
| B6 | 🟡 Médio | `backend-flask/blueprints/analytics.py:259` | Heurística "≤15 valores únicos = variável discreta" quebra com sensores barulhentos. Usar `pd.Series.nunique()/len()` ratio como critério mais robusto. |
| B7 | 🟢 Baixo | `backend-flask/blueprints/analytics.py` | Falta de estatísticas EDA modernas: p50/p90/p99, IQR, Z-score outliers, decomposição de tendência (STL), autocorrelação. |

### 2.3 Raiz conceitual do "gráfico sempre crescendo"

```
Coletor grava: refugo_op_acumulado (contador cumulativo do CLP)
Analytics query: SELECT LAST(refugo_op_acumulado) BY 1min
Plot: série de LASTs → função monotônica não-decrescente

O que vemos: ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╱━╱━━╱
                                      (só sobe)
O que deveríamos ver: ▁▁▁▂▃▂▁▂▄▅▃▂▁▁▁  (refugo POR minuto)
```

**Fix estrutural:** pipeline de analytics precisa decidir, **por métrica**, se ela é:
- `gauge` (valor instantâneo — velocidade, temperatura, estado) → `MEAN`/`LAST` direto
- `counter` (contador cumulativo — refugo, produção, paradas) → **`NON_NEGATIVE_DIFFERENCE`**
- `state` (discreta — estado do equipamento) → `MODE` ou `LAST`

Hoje isso não existe. Precisamos de um **metadado por métrica** no dicionário `CONSOLIDATED_METRICS`.

---

## 3. Coletor OPC UA — `coletor/coletor.py`

### 3.1 Loop atual (resumido)

```
while True:
  atualizar_configuracao()          # busca lista de equips no Django
  gerenciar_conexoes()              # cria/fecha clientes asyncua
  for url in clientes:
    verificar_saude_conexao(url)    # lê tag de heartbeat
    if ok: coletar_dados()
    else:  força estado=999 (OFFLINE)
  enviar para Django + Flask
  sleep(max(0.1, INTERVALO - elapsed))
```

### 3.2 Pontos de falha

| # | Severidade | Arquivo:Linha | Problema |
|---|---|---|---|
| C1 | 🔴 Crítico | `coletor/coletor.py:145` | `await c.connect()` sem retry nem backoff. Se falha: cliente fica None, loop não tenta reconectar. |
| C2 | 🔴 Crítico | `coletor/coletor.py:177-181` | `verificar_saude_conexao()` retorna `False` mas não faz **nada** sobre a conexão morta. Ciclo seguinte tenta usar cliente zombie. |
| C3 | 🔴 Crítico | `coletor/coletor.py:211-213` | `except Exception` no loop principal → dorme 5s e tenta de novo. **Sem `exc_info=True`**, sem stack trace, causa-raiz invisível. |
| C4 | 🟡 Alto | `coletor/coletor.py:200-204` | Envio para Django/Flask sem retry, sem buffer. Se API cair → dado é descartado (perda irreversível). |
| C5 | 🟡 Médio | `coletor/coletor.py:87-107` | `atualizar_configuracao()` usa `requests.get` sem timeout → pode travar o loop todo se Django responder lento. |
| C6 | 🟢 Baixo | `coletor/requirements.txt` | `asyncua` sem pinning de versão → comportamento imprevisível em upgrades. |
| C7 | 🟢 Baixo | `coletor/Dockerfile` | Sem política de restart — em docker-compose precisa `restart: on-failure`, hoje container morto fica morto. |

### 3.3 O que falta (gap de arquitetura)

- **Reconexão exponencial com backoff** (tenacity)
- **Watchdog assíncrono** (task paralela lê heartbeat a cada 30s e derruba conexões mortas)
- **Buffer offline SQLite** para não perder leituras quando APIs caírem
- **Circuit breaker** para Django/Flask (evita cascata de falhas)
- **Health endpoint HTTP** (`GET /health` com estado por URL OPC, buffer size, último sync)
- **Métricas Prometheus** (`coletor_opc_connection_state`, `coletor_buffer_size`, etc.)

---

## 4. Fórmulas matemáticas de KPI

### 4.1 Auditoria versus ISO 22400-2

| KPI | Arquivo:Linha | Fórmula atual | Avaliação |
|---|---|---|---|
| OEE Realtime | `production_engine.py:421` | `A × P × Q × 100` | ⚠️ **Escala inconsistente** — A/P/Q já podem retornar 0-100, multiplica por 100 de novo = valores até 10.000 |
| Disponibilidade | `production_engine.py:390` | `(Planejado - Parado) / Planejado` | ✅ OK (clipping, div/0) |
| Performance | `production_engine.py:411` | `min(1.05, Vel_real / Vel_nominal)` | ⚠️ **Cap 105%** viola ISO 22400 — Performance em KPI consolidado deve ser ≤ 100% |
| Qualidade | `production_engine.py:419` | `(Saída - Refugo) / Saída` | ⚠️ Correta, **mas** retorna 1.0 quando Saída=0 (ver B2) |
| TPH Real | `kpis_engine.py:14` | `(Vel × 60 × Formato_g / 1M) × (Q/100)` | 🔴 **Qualidade multiplicada 2×** — uma vez em TPH, outra em OEE. Impacto duplo irreal |
| Descarte | `agregador.py:327` | `max(0, Entrada - Saída)` | ✅ OK (mass balance) |
| Give Away | `analytics.py:115-139` | `MEAN(peso) - LAST(nominal)` | ⚠️ **Sem ajuste estatístico** — ignora σ aceitável e tolerância legal INMETRO (±1%) |
| OEE Fábrica | `kpis_engine.py:471` | `Σ(OEE_eq × Prod_eq) / Σ(Prod_eq)` | ✅ Média ponderada correta |
| TPH Linha | `factory_kpis_engine.py:256, 307` | `MAX(toneladas_turno_eq) / horas` | 🔴 **Conceito errado** — TPH de linha = throughput do gargalo, não máximo |

### 4.2 Os 3 erros mais críticos

**Erro #1 — Escala OEE:**
```python
# production_engine.py:421  (errado se A,P,Q já em 0-100)
oee = disponibilidade * performance * qualidade * 100

# correto
oee = min(100.0, (A/100) * (P/100) * (Q/100) * 100)
```

**Erro #2 — TPH duplica qualidade:**
```python
# kpis_engine.py:14  (errado)
tph_real = tph_teorico * (qualidade / 100.0)

# correto: TPH é taxa física, Q já é contabilizada no OEE
tph_real = (velocidade * 60 * formato) / 1_000_000
```

**Erro #3 — Qualidade = 1.0 quando parado:**
```python
# production_engine.py:413-419  (errado)
qualidade = 1.0
if total_prod_op > 0:
    qualidade = max(0.0, (total_prod_op - total_waste_op) / total_prod_op)

# correto
if total_prod_op <= 0:
    qualidade = None   # ou omitir da agregação
else:
    qualidade = max(0.0, 1 - total_waste_op / total_prod_op)
```

### 4.3 Recomendação de refatoração

Extrair cada fórmula para uma classe pura testável (`kpis/formulas.py`):

```python
class OEECalculator:
    @staticmethod
    def calculate(a_pct: float, p_pct: float, q_pct: float) -> float:
        if min(a_pct, p_pct, q_pct) < 0:
            raise ValueError("componentes devem ser >= 0")
        return min(100.0, (a_pct/100) * (p_pct/100) * (q_pct/100) * 100)
```

**Ganho:** unit tests, reutilização em FastAPI e em notebooks pandas, versionamento explícito (`OEECalculator_v2` se ISO mudar).

---

## 5. Classificação por impacto e esforço

| ID | Problema | Impacto | Esforço | Prioridade |
|---|---|---|---|---|
| B1 | Gráfico sempre crescendo (delta não aplicado) | 🔴 Crítico | Baixo | **P0** |
| B2 | Qualidade=100% com máquina parada | 🔴 Crítico | Baixo | **P0** |
| C1-C3 | Coletor não reconecta | 🔴 Crítico | Médio | **P0** |
| B4/4.2-#2 | TPH linha e TPH duplica Q | 🔴 Alto | Baixo | P1 |
| F1-F2 | Sidebar sem scroll/categoria | 🔴 Alto | Baixo | P1 |
| F3-F4 | Home sem hierarquia ISA-101 | 🔴 Alto | Médio | P1 |
| F5 | Analytics sem range datetime | 🔴 Alto | Baixo | P1 |
| 4.2-#1 | Escala OEE (×100 duas vezes) | 🟡 Médio | Baixo | P1 |
| B5 | Endpoint KPI só com período fixo | 🟡 Médio | Baixo | P2 |
| C4-C5 | Buffer offline + timeouts | 🟡 Médio | Médio | P2 |
| F7-F8 | Tipos TS compartilhados + tokens | 🟢 Baixo | Médio | P3 |
| B7 | EDA moderno (IQR, STL, p90/p99) | 🟢 Baixo | Médio | P3 |

---

## 6. O que **não** foi auditado (gaps conhecidos)

- Testes automatizados (pytest, vitest) — inspecionar cobertura em próxima fase.
- Configuração do Node-RED (`node-red/`) — usado como complemento do coletor?
- InfluxDB schema — sem acesso ao bucket, só inferimos pelo código.
- Grafana dashboards existentes — `grafana/` contém JSONs que podem ser reutilizados.
- Autenticação/autorização — Django admin presente, mas fluxo end-to-end não avaliado.

---

> **Próximo passo:** ler `02_ARQUITETURA_ALVO.md` para ver a arquitetura-alvo, e `03_ROADMAP_EXECUCAO.md` para o plano faseado que endereça tudo isso.
