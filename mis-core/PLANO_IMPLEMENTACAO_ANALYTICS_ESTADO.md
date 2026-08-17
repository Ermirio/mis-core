# Plano de Implementação — Analytics: Variável `estado` e Value Mappings

**Projeto:** MIS Core
**Branch base:** `mis-admin-modules`
**Executante esperado:** Fullstack + Data Scientist (agente antigravity)
**Escopo:** Nenhuma refatoração estrutural. Mudanças cirúrgicas, localizadas.

---

## Contexto Técnico

O sistema coleta dados industriais via OPC UA e grava em InfluxDB (measurement `production`,
field `estado`). O estado do equipamento é **numérico** no InfluxDB:

| Valor | Significado |
|-------|-------------|
| 1 | Produzindo (RUN) |
| 2 | Aguardando equipamento anterior (WAIT_PREV) |
| 3 | Equipamento seguinte bloqueado (BLOCK_NEXT) |
| 4 | Falha / Parado (FAULT) |
| 5 | Setup / Troca SKU (SETUP) |
| 6 | Teste de Projeto (TESTE_PROJ) |
| 7 | Aguardando Manutenção (AGUARD_MNT) |
| 8 | Em Manutenção (MANUTENCAO) |
| 9 | Falta de Material (FALTA_MAT) |
| 11 | Partindo (PARTINDO) |
| 12 | Aguardando Condições (AGUARD_COND) |
| 13 | Parando (PARANDO) |
| 999 | Offline |

O mapeamento de legenda **já existe** em:
`mis-core/frontend-react/client/src/utils/equipmentStateUtils.tsx`
(funções `normalizeState` e `mapEstado`).

O backend Flask **já suporta** qualquer campo numérico do InfluxDB via
`pd.to_numeric(df[alias], errors='coerce')` em
`mis-core/backend-flask/blueprints/analytics.py:189`.

O problema: `estado` **nunca foi adicionado** à lista de variáveis do seletor
do analytics (`standardMetrics` em `LineAnalytics.tsx:381`).

---

## Arquivos que Serão Alterados

| Arquivo | Tipo de Alteração |
|---------|-------------------|
| `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx` | Principal — múltiplos pontos |
| `mis-core/backend-flask/blueprints/analytics.py` | Mínima — proteção para variável discreta em stats |

---

## Tarefa 1 — Adicionar `estado` ao seletor de variáveis

**Arquivo:** `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx`

### 1.1 Atualizar a interface `Tag`

Localizar a interface `Tag` em torno da linha 27 e adicionar dois campos opcionais:

```typescript
// ANTES (linha 26-35 aproximadamente)
interface Tag {
    id: number;
    nome: string;
    tag_influxdb: string;
    equipamento_nome: string;
    equipamento_code: string;
    linha_nome: string;
    lsl?: number;
    usl?: number;
    nominal?: number;
    isStandard?: boolean;
}

// DEPOIS
interface Tag {
    id: number;
    nome: string;
    tag_influxdb: string;
    equipamento_nome: string;
    equipamento_code: string;
    linha_nome: string;
    lsl?: number;
    usl?: number;
    nominal?: number;
    isStandard?: boolean;
    isDiscrete?: boolean;           // ← NOVO: flag para variável discreta/categórica
    valueMapping?: Record<number, { label: string; color: string }>;  // ← NOVO: mapeamento valor→legenda
}
```

### 1.2 Criar o mapeamento de estados como constante

Adicionar uma constante no topo do arquivo, antes do componente `LineAnalytics`,
logo após os imports (por volta da linha 23):

```typescript
// Mapeamento de valores numéricos de estado para legenda e cor
// Espelha exatamente equipmentStateUtils.tsx — não duplicar a lógica de ícones,
// apenas os dados necessários para o analytics (label + cor para Plotly).
const ESTADO_VALUE_MAPPING: Record<number, { label: string; color: string }> = {
    1:   { label: 'Produzindo',              color: '#16a34a' },
    2:   { label: 'Aguard. Anterior',        color: '#06b6d4' },
    3:   { label: 'Seguinte Bloqueado',      color: '#f97316' },
    4:   { label: 'Falha / Parado',          color: '#dc2626' },
    5:   { label: 'Setup / Troca SKU',       color: '#a855f7' },
    6:   { label: 'Teste de Projeto',        color: '#0ea5e9' },
    7:   { label: 'Aguard. Manutenção',      color: '#78716c' },
    8:   { label: 'Em Manutenção',           color: '#991b1b' },
    9:   { label: 'Falta de Material',       color: '#d97706' },
    11:  { label: 'Partindo',               color: '#84cc16' },
    12:  { label: 'Aguard. Condições',      color: '#64748b' },
    13:  { label: 'Parando',               color: '#f59e0b' },
    999: { label: 'Offline',               color: '#6b7280' },
};
```

### 1.3 Adicionar `estado` ao `standardMetrics`

Localizar `getEquipmentTags` (linha 378) e dentro de `standardMetrics` adicionar
o estado **como último item**, para que não quebre a posição dos outros:

```typescript
// ANTES
const standardMetrics = [
    { nome: 'Velocidade', tag: 'velocidade_atual' },
    { nome: 'OEE',        tag: 'oee'              },
    { nome: 'Produção',   tag: 'contagem_saida'   },
    { nome: 'Descarte',   tag: 'descarte'         }
];

// DEPOIS
const standardMetrics = [
    { nome: 'Velocidade', tag: 'velocidade_atual' },
    { nome: 'OEE',        tag: 'oee'              },
    { nome: 'Produção',   tag: 'contagem_saida'   },
    { nome: 'Descarte',   tag: 'descarte'         },
    { nome: 'Estado',     tag: 'estado',           isDiscrete: true, valueMapping: ESTADO_VALUE_MAPPING }
];
```

### 1.4 Propagar os novos campos no objeto tag gerado

Dentro de `standardMetrics.forEach(m => { tags.push({...}) })` (aprox. linha 388),
adicionar os campos no objeto:

```typescript
standardMetrics.forEach(m => {
    tags.push({
        id: `std-${eq.codigo}-${m.tag}`,
        nome: m.nome,
        tag_influxdb: m.tag,
        equipamento_nome: eq.nome,
        equipamento_code: eq.codigo,
        linha_nome: linha.nome,
        isStandard: true,
        isDiscrete: (m as any).isDiscrete ?? false,           // ← NOVO
        valueMapping: (m as any).valueMapping ?? undefined,   // ← NOVO
    });
});
```

---

## Tarefa 2 — Renderização do Trend Chart com Value Mappings

**Arquivo:** `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx`

O gráfico de trend usa `react-plotly.js` (Plot) com `type: 'scatter'`, `mode: 'lines'`,
e múltiplos eixos Y (um por variável).

Localizar o componente `Plot` dentro de `TabsContent value="trend"` (aprox. linha 947).

### 2.1 Separar variáveis contínuas e discretas antes de gerar os traces

Antes do `.map()` que gera os traces Plotly, adicionar a lógica de separação:

```typescript
// Dentro do render do TrendChart, antes do Plot
const selectedTagsForChart = chart.selectedAliases;

// Identifica quais aliases correspondem a variáveis discretas
// Busca nos selectedTags globais para obter os metadados
const isAliasDiscrete = (alias: string): boolean => {
    const tag = selectedTags.find(t => {
        const tagAlias = `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}`;
        return tagAlias === alias;
    });
    return tag?.isDiscrete ?? false;
};

const getAliasMapping = (alias: string): Record<number, { label: string; color: string }> | undefined => {
    const tag = selectedTags.find(t => {
        const tagAlias = `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}`;
        return tagAlias === alias;
    });
    return tag?.valueMapping;
};
```

### 2.2 Gerar traces diferenciados para variáveis discretas

Substituir o `.map()` dos traces (aprox. linha 948) para tratar `estado` diferentemente:

```typescript
// ANTES
data={chart.selectedAliases.map((alias: string, idx: number) => ({
    x: timeseriesData[alias]?.timestamps || [],
    y: timeseriesData[alias]?.values || [],
    type: 'scatter',
    mode: 'lines',
    name: alias.split(' - ').pop() || alias,
    hovertext: alias,
    yaxis: idx === 0 ? 'y' : `y${idx + 1}`,
}))}

// DEPOIS
data={chart.selectedAliases.map((alias: string, idx: number) => {
    const discrete = isAliasDiscrete(alias);
    const mapping = getAliasMapping(alias);
    const values: number[] = timeseriesData[alias]?.values || [];
    const timestamps: string[] = timeseriesData[alias]?.timestamps || [];

    if (discrete && mapping) {
        // Variável discreta: usar 'lines' com step, eixo próprio, com tickvals e ticktext
        return {
            x: timestamps,
            y: values,
            type: 'scatter',
            mode: 'lines',
            line: { shape: 'hv', width: 2 },  // hv = step horizontal (ideal para estados)
            name: alias.split(' - ').pop() || alias,
            yaxis: idx === 0 ? 'y' : `y${idx + 1}`,
            // Hover mostra o label semântico, não o número
            text: values.map(v => mapping[v]?.label ?? String(v)),
            hovertemplate: '%{text}<br>%{x}<extra></extra>',
            // Colorscale baseado nos valores de estado
            marker: {
                color: values.map(v => mapping[v]?.color ?? '#6b7280'),
            },
        } as any;
    }

    // Variável contínua: comportamento original
    return {
        x: timestamps,
        y: values,
        type: 'scatter',
        mode: 'lines',
        name: alias.split(' - ').pop() || alias,
        hovertext: alias,
        yaxis: idx === 0 ? 'y' : `y${idx + 1}`,
    };
})}
```

### 2.3 Adicionar tickvals/ticktext ao eixo Y do `estado` no layout

Ainda dentro do `Plot` do trend, o `layout` é gerado via `Object.fromEntries` para os eixos Y.
Modificar para que eixos de variáveis discretas tenham ticks semânticos:

```typescript
// ANTES (aprox. linha 965)
...Object.fromEntries(
    chart.selectedAliases.map((_: string, idx: number) => [
        idx === 0 ? 'yaxis' : `yaxis${idx + 1}`,
        {
            title: { text: '' },
            overlaying: idx === 0 ? undefined : 'y',
            side: idx % 2 === 0 ? 'left' : 'right',
            showgrid: idx === 0,
            autorange: true,
        }
    ])
)

// DEPOIS
...Object.fromEntries(
    chart.selectedAliases.map((alias: string, idx: number) => {
        const discrete = isAliasDiscrete(alias);
        const mapping = getAliasMapping(alias);
        const baseAxis = {
            title: { text: '' },
            overlaying: idx === 0 ? undefined : 'y',
            side: idx % 2 === 0 ? 'left' : 'right',
            showgrid: idx === 0,
            autorange: true,
        };

        if (discrete && mapping) {
            // Eixo com ticks semânticos (igual ao Value Mappings do Grafana)
            const numericValues = Object.keys(mapping).map(Number);
            return [
                idx === 0 ? 'yaxis' : `yaxis${idx + 1}`,
                {
                    ...baseAxis,
                    tickvals: numericValues,
                    ticktext: numericValues.map(v => mapping[v].label),
                    dtick: null,        // Desabilita auto-tick; usa tickvals
                    autorange: true,
                }
            ];
        }

        return [idx === 0 ? 'yaxis' : `yaxis${idx + 1}`, baseAxis];
    })
)
```

---

## Tarefa 3 — Adaptar o SPC Chart para variável discreta

**Arquivo:** `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx`

O SPC (Statistical Process Control) não faz sentido para variáveis discretas ordinais
como `estado`. UCL/LCL calculados sobre valores 1–13 são estatisticamente inválidos.

Localizar `TabsContent value="spc"` (aprox. linha 996).

### 3.1 Adicionar guarda condicional por tipo de variável

```typescript
// ANTES
{Object.entries(timeseriesData).map(([alias, d]: [string, any]) => (
    <Card key={alias}>
        ...Plot SPC...
    </Card>
))}

// DEPOIS
{Object.entries(timeseriesData).map(([alias, d]: [string, any]) => {
    const tag = selectedTags.find(t =>
        `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}` === alias
    );
    const discrete = tag?.isDiscrete ?? false;
    const mapping = tag?.valueMapping;

    if (discrete && mapping) {
        // Para estado: mostrar gráfico de frequência de estados (bar chart)
        const stateCounts: Record<string, number> = {};
        (d.values as number[]).forEach(v => {
            const label = mapping[v]?.label ?? String(v);
            stateCounts[label] = (stateCounts[label] ?? 0) + 1;
        });
        const labels = Object.keys(stateCounts);
        const counts = labels.map(l => stateCounts[l]);
        const colors = labels.map(l => {
            const entry = Object.values(mapping).find(m => m.label === l);
            return entry?.color ?? '#6b7280';
        });

        return (
            <Card key={alias}>
                <CardHeader>
                    <CardTitle>Frequência de Estados — {alias.split(' - ').pop()}</CardTitle>
                    <p className="text-xs text-gray-500">
                        Distribuição de tempo por estado. UCL/LCL não se aplicam a variáveis categóricas.
                    </p>
                </CardHeader>
                <CardContent>
                    <Plot
                        data={[{
                            x: labels,
                            y: counts,
                            type: 'bar',
                            marker: { color: colors },
                            name: 'Ocorrências',
                        }]}
                        layout={{
                            autosize: true,
                            height: 350,
                            xaxis: { title: { text: 'Estado' } },
                            yaxis: { title: { text: 'Nº de amostras' } },
                            showlegend: false,
                        }}
                        useResizeHandler={true}
                        className="w-full"
                    />
                </CardContent>
            </Card>
        );
    }

    // Variável contínua: comportamento original do SPC
    return (
        <Card key={alias}>
            <CardHeader><CardTitle>SPC - {alias}</CardTitle></CardHeader>
            <CardContent>
                <Plot
                    data={[
                        { x: d.timestamps, y: d.values, type: 'scatter', mode: 'lines+markers', name: 'Valor Real' },
                        { x: d.timestamps, y: Array(d.timestamps.length).fill(d.stats?.mean ?? 0), type: 'scatter', mode: 'lines', name: 'Média', line: { color: 'green', dash: 'dash' } },
                        { x: d.timestamps, y: Array(d.timestamps.length).fill(d.stats?.ucl ?? 0), type: 'scatter', mode: 'lines', name: 'UCL (+3σ)', line: { color: 'red' } },
                        { x: d.timestamps, y: Array(d.timestamps.length).fill(d.stats?.lcl ?? 0), type: 'scatter', mode: 'lines', name: 'LCL (-3σ)', line: { color: 'red' } },
                    ]}
                    layout={{ title: { text: `Carta de Controle: ${alias}` }, autosize: true, height: 400 }}
                    useResizeHandler={true}
                    className="w-full"
                />
            </CardContent>
        </Card>
    );
})}
```

---

## Tarefa 4 — Adaptar o Stats Tab para variável discreta

**Arquivo:** `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx`

Dentro de `TabsContent value="stats"` (aprox. linha 735), o histograma com
curva normal é gerado para cada variável. Para `estado`, isso produz um gráfico
sem sentido (Cp/Cpk de uma variável categórica é inválido).

O backend em `analyze_stats` calcula o histograma com `np.histogram`. Para `estado`,
os bins serão os valores discretos 1–13, e a curva normal sobreposta é enganosa.

### 4.1 Identificar variável discreta no retorno da stats API

O endpoint `/analyze/stats` retorna um array de objetos. Cada objeto contém
`variable` (que é o alias), `stats`, e `histogram`. A API não sabe se a variável
é discreta, pois essa informação está apenas no frontend.

Solução: usar `selectedTags` para cruzar o alias com o metadado `isDiscrete`.

```typescript
// No render de cada resultado de stats (aprox. linha 736):
{statsData.map((res, idx) => {
    // Determina se este alias é discreto consultando selectedTags
    const tag = selectedTags.find(t =>
        `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}` === res.variable
    );
    const isDiscrete = tag?.isDiscrete ?? false;
    const mapping = tag?.valueMapping;

    return (
        <Card key={idx}>
            <CardHeader>
                <CardTitle>{res.variable}</CardTitle>
                {res.error ? (
                    <div className="text-red-500 text-sm ...">...</div>
                ) : (
                    <div className="flex gap-4 text-sm text-gray-500">
                        {/* Mostrar Cp/Cpk apenas para variáveis contínuas */}
                        {!isDiscrete && (
                            <>
                                <span>Média: {res.stats?.mean?.toFixed(2) ?? 'N/A'}</span>
                                <span>Std: {res.stats?.std?.toFixed(2) ?? 'N/A'}</span>
                                {res.stats?.cpk !== undefined && res.stats.cpk !== null && (
                                    <span className={res.stats.cpk < 1.33 ? 'text-red-500 font-bold' : 'text-green-600 font-bold'}>
                                        Cpk: {res.stats.cpk.toFixed(2)}
                                    </span>
                                )}
                            </>
                        )}
                        {isDiscrete && (
                            <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded">
                                Variável categórica — Cp/Cpk não aplicável
                            </span>
                        )}
                    </div>
                )}
            </CardHeader>
            <CardContent>
                {!res.error && res.histogram && !isDiscrete && (
                    // Histograma com curva normal — somente para variáveis contínuas
                    (() => {
                        // ... código original do histograma sem alteração ...
                    })()
                )}
                {!res.error && isDiscrete && mapping && (
                    // Para estado: tabela de frequências + bar chart com cores semânticas
                    (() => {
                        const bins: number[] = res.histogram?.bins ?? [];
                        const counts: number[] = res.histogram?.counts ?? [];
                        // bins contém os valores numéricos dos estados
                        const labels = bins.slice(0, counts.length).map(
                            (v: number) => mapping[Math.round(v)]?.label ?? String(v)
                        );
                        const colors = bins.slice(0, counts.length).map(
                            (v: number) => mapping[Math.round(v)]?.color ?? '#6b7280'
                        );
                        return (
                            <Plot
                                data={[{
                                    x: labels,
                                    y: counts,
                                    type: 'bar',
                                    marker: { color: colors },
                                    name: 'Amostras por Estado',
                                }]}
                                layout={{
                                    autosize: true,
                                    height: 320,
                                    title: { text: 'Distribuição de Estados' },
                                    xaxis: { title: { text: 'Estado' } },
                                    yaxis: { title: { text: 'Nº de amostras' } },
                                    showlegend: false,
                                }}
                                useResizeHandler={true}
                                className="w-full"
                            />
                        );
                    })()
                )}
            </CardContent>
        </Card>
    );
})}
```

---

## Tarefa 5 — Proteção no Backend para Stats de Variável Discreta

**Arquivo:** `mis-core/backend-flask/blueprints/analytics.py`

O endpoint `/analyze/stats` (linha 204) calcula histograma via `np.histogram` e
Cp/Cpk. Para `estado`, esses cálculos são tecnicamente válidos mas semanticamente
incorretos. O frontend já resolve a exibição, mas é boa prática sinalizar no payload
que a variável tem poucos valores únicos (característica de variável discreta).

### 5.1 Adicionar campo `n_unique` ao retorno de stats

Dentro do loop de variáveis em `analyze_stats`, após calcular as estatísticas,
adicionar ao `result`:

```python
# Localizar onde result é montado (aprox. linha 260-280)
# Após calcular mean, std, etc., adicionar:

n_unique = int(series.nunique())
result = {
    'variable': alias,
    'stats': {
        'mean': ...,
        'std': ...,
        # ... campos existentes ...
        'n_unique': n_unique,                         # ← NOVO
        'is_discrete': n_unique <= 20,                # ← NOVO heurística: <= 20 valores únicos
    },
    'histogram': { ... }
}
```

Isso permite que o frontend confirme o tipo da variável via API, criando resiliência
caso o metadado `isDiscrete` no frontend não esteja disponível (ex: perfil salvo
antes desta feature).

> **Nota para o implementador:** o campo `is_discrete` do backend é apenas informativo.
> A fonte primária de verdade continua sendo o campo `isDiscrete` no `selectedTags`
> do frontend, pois o backend não conhece a semântica dos campos OPC UA.

---

## Tarefa 6 — Correlação: recomendação de método para variáveis mistas

**Arquivo:** `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx`

Quando `estado` (variável ordinal discreta) está selecionado junto com variáveis
contínuas, **Spearman é mais adequado** que Pearson. Pearson assume distribuição
normal e relação linear — `estado` viola ambas as premissas.

### 6.1 Detectar presença de variável discreta e sugerir Spearman

Adicionar lógica que detecta se alguma tag selecionada é discreta e exibe aviso:

```typescript
// Dentro de TabsContent value="correlation", antes dos controles (aprox. linha 1022)
const hasDiscreteVariable = selectedTags.some(t => t.isDiscrete);

{hasDiscreteVariable && (
    <div className="flex items-center gap-2 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700 mb-3">
        <Info className="h-4 w-4 flex-shrink-0" />
        <span>
            Variável categórica detectada (Estado).
            <strong> Spearman</strong> é recomendado para correlação entre variáveis ordinais e contínuas.
        </span>
        <Button
            size="sm"
            variant="outline"
            className="h-6 text-xs border-amber-400 text-amber-700 ml-auto"
            onClick={() => setCorrMethod('spearman')}
        >
            Usar Spearman
        </Button>
    </div>
)}
```

---

## Tarefa 7 — Preservar `isDiscrete` e `valueMapping` no AnalyticsProfile

**Arquivo:** `mis-core/frontend-react/client/src/components/Analytics/ProfileManager.tsx`

O `ProfileManager` salva e carrega `selectedTags` no Django via
`POST /analytics-profiles/`. Os novos campos `isDiscrete` e `valueMapping`
precisam ser preservados no JSON de perfil para que perfis salvos continuem
funcionando corretamente.

### 7.1 Verificar serialização atual

No `ProfileManager.tsx`, localizar onde `currentState` é enviado:

```typescript
// Aprox. linha 69
await axios.post(`${DJANGO_API}/analytics-profiles/`, {
    nome: profileName,
    linha: linhaId,
    config: currentState,  // selectedTags está aqui como parte de currentState
});
```

Como `selectedTags` é um array de objetos e `config` é um `JSONField` no Django,
**não há nada a fazer**: os campos `isDiscrete` e `valueMapping` serão automaticamente
incluídos no JSON e preservados ao salvar/carregar.

### 7.2 Verificar deserialização no `loadProfile`

Localizar onde o perfil é carregado (aprox. linha 530 em LineAnalytics.tsx):

```typescript
// ANTES
setSelectedTags(config.selectedTags || []);

// APÓS — verificação defensiva de compatibilidade retroativa:
// Perfis salvos antes desta feature não terão isDiscrete/valueMapping.
// O código abaixo restaura os campos para tags de estado já salvas.
setSelectedTags(
    (config.selectedTags || []).map((t: any) => {
        if (t.tag_influxdb === 'estado' && !t.isDiscrete) {
            return { ...t, isDiscrete: true, valueMapping: ESTADO_VALUE_MAPPING };
        }
        return t;
    })
);
```

---

## Ordem de Execução Recomendada

```
Tarefa 1  → Exposição da variável (sem ela, nada mais funciona)
Tarefa 7  → Retrocompatibilidade de perfis (sem isso, perfis carregados perdem metadados)
Tarefa 2  → Trend Chart com step e ticks semânticos
Tarefa 3  → SPC com frequência de estados
Tarefa 4  → Stats com bar chart de frequência
Tarefa 5  → Backend: campo n_unique (mínimo invasivo, pode ficar por último)
Tarefa 6  → Aviso de Spearman (UX, pode ficar por último)
```

---

## Critérios de Aceitação

- [ ] `Estado` aparece no seletor de variáveis dentro de cada equipamento, após `Descarte`
- [ ] Ao selecionar `Estado` e clicar em "Gerar Gráficos", o trend exibe a série com degraus (linha step `hv`)
- [ ] O eixo Y do `Estado` no trend mostra labels semânticos ("Produzindo", "Falha", etc.) em vez de números
- [ ] O tooltip ao passar o mouse em um ponto de `Estado` mostra o nome do estado, não o número
- [ ] Na aba SPC, `Estado` exibe bar chart de frequência por estado com cores correspondentes
- [ ] Na aba Stats, `Estado` não exibe Cp/Cpk nem histograma com curva normal; exibe bar chart de frequências
- [ ] Ao selecionar `Estado` na correlação, aparece aviso sugerindo Spearman com botão de aplicação rápida
- [ ] Perfis salvos que incluem `Estado` carregam corretamente com os metadados `isDiscrete`/`valueMapping`
- [ ] Perfis salvos **antes** desta feature que incluem `Estado` (sem `isDiscrete`) são retroativamente corrigidos no `loadProfile`
- [ ] Nenhuma variável contínua existente teve seu comportamento alterado

---

## Premissas e Restrições

- O field `estado` no InfluxDB (measurement `production`) **já é numérico** — a coleta OPC UA já converte para inteiro antes de gravar
- O `pd.to_numeric(df[alias], errors='coerce')` no backend **já trata** o campo corretamente — não alterar o backend de query
- Não criar novos endpoints, não alterar o schema Django, não criar novos componentes React — tudo deve ser feito nos arquivos existentes identificados
- O gráfico usa `react-plotly.js` (já importado como `Plot` no topo do arquivo) — não introduzir nenhuma nova biblioteca de charting
- Os testes existentes em `mis-core/backend-django/equipamentos/tests/` não cobrem analytics — não é necessário criar novos testes, mas não quebrar os existentes
- Manter o comportamento para todas as tags que **não são** `estado` exatamente como está hoje

---

## Referências de Código

| O quê | Onde |
|--------|------|
| Mapeamento de estados (fonte de verdade para UI) | `mis-core/frontend-react/client/src/utils/equipmentStateUtils.tsx:69` |
| Lista de standardMetrics (ponto de entrada principal) | `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx:381` |
| Geração de objetos tag | `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx:388` |
| Plot do trend chart | `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx:947` |
| Layout multi-eixo Y | `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx:965` |
| Plot do SPC | `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx:1003` |
| Histograma em Stats | `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx:762` |
| Correlação - controles | `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx:1022` |
| loadProfile | `mis-core/frontend-react/client/src/pages/LineAnalytics.tsx:530` |
| Backend stats endpoint | `mis-core/backend-flask/blueprints/analytics.py:204` |
| pd.to_numeric (já trata estado) | `mis-core/backend-flask/blueprints/analytics.py:189` |
