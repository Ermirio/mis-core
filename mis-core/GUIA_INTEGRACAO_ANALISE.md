# Guia de Integração Final - Análise Avançada

## ✅ O Que Foi Implementado

### Backend (Django)
1. **3 Novas APIs** em `equipamentos/views.py`:
   - `linha_analise_producao` - Dados de produção acumulada
   - `linha_analise_velocidade` - Dados de velocidade real vs ideal
   - `linha_analise_sku` - Produção agrupada por SKU

2. **Rotas Registradas** em `equipamentos/urls.py`:
   - `/api/linhas/{id}/analise/producao/`
   - `/api/linhas/{id}/analise/velocidade/`
   - `/api/linhas/{id}/analise/sku/`

### Frontend (React)
1. **4 Novos Componentes**:
   - `FilterBar.tsx` - Filtros avançados
   - `ProductionChart.tsx` - Gráfico de produção acumulada
   - `SpeedChart.tsx` - Gráfico de velocidade
   - `SKUProductionChart.tsx` - Gráfico de produção por SKU

2. **Serviço de API** em `services/analiseApi.ts`:
   - Funções para buscar dados das APIs
   - Cálculo de períodos rápidos

---

## 🔧 Integração na LinhaDetalhes.tsx

### Passo 1: Adicionar Estados (após linha 111)

```typescript
// Estados de análise
const [periodoTipo, setPeriodoTipo] = useState<'rapido' | 'personalizado'>('rapido');
const [periodoRapido, setPeriodoRapido] = useState('turno_atual');
const [dataInicio, setDataInicio] = useState(new Date().toISOString().split('T')[0]);
const [dataFim, setDataFim] = useState(new Date().toISOString().split('T')[0]);
const [granularidade, setGranularidade] = useState<'hora' | 'turno' | 'dia' | 'semana'>('turno');

const [dadosProducao, setDadosProducao] = useState<any[]>([]);
const [dadosVelocidade, setDadosVelocidade] = useState<any[]>([]);
const [dadosSKU, setDadosSKU] = useState<any[]>([]);
const [analiseLoading, setAnaliseLoading] = useState(false);
```

### Passo 2: Adicionar Import do Serviço (no topo)

```typescript
import {
  fetchAnaliseProducao,
  fetchAnaliseVelocidade,
  fetchAnaliseSKU,
  calcularPeriodoRapido
} from '@/services/analiseApi';
```

### Passo 3: Adicionar Funções de Fetch

```typescript
const fetchDadosAnalise = async () => {
  if (!linhaId) return;
  
  setAnaliseLoading(true);
  try {
    const id = parseInt(linhaId);
    
    // Calcula período
    let inicio = dataInicio;
    let fim = dataFim;
    
    if (periodoTipo === 'rapido' && periodoRapido !== 'turno_atual' && periodoRapido !== 'turno_anterior') {
      const periodo = calcularPeriodoRapido(periodoRapido);
      inicio = periodo.dataInicio;
      fim = periodo.dataFim;
    }
    
    // Busca dados em paralelo
    const [producao, velocidade, sku] = await Promise.all([
      fetchAnaliseProducao(id, inicio, fim, granularidade),
      fetchAnaliseVelocidade(id, inicio, fim, granularidade),
      fetchAnaliseSKU(id, inicio, fim)
    ]);
    
    setDadosProducao(producao.dados);
    setDadosVelocidade(velocidade.dados);
    setDadosSKU(sku.dados);
    
  } catch (err) {
    console.error('Erro ao buscar dados de análise:', err);
  } finally {
    setAnaliseLoading(false);
  }
};

const aplicarFiltros = () => {
  fetchDadosAnalise();
};

const limparFiltros = () => {
  setPeriodoTipo('rapido');
  setPeriodoRapido('turno_atual');
  setGranularidade('turno');
  setDataInicio(new Date().toISOString().split('T')[0]);
  setDataFim(new Date().toISOString().split('T')[0]);
};

const exportarDados = () => {
  // TODO: Implementar exportação
  console.log('Exportar dados...');
};
```

### Passo 4: Adicionar useEffect para Buscar Dados

```typescript
useEffect(() => {
  if (linhaId) {
    fetchDadosAnalise();
  }
}, [linhaId]);
```

### Passo 5: Adicionar Nova Aba (na linha 412, após TabsTrigger "visao-geral")

```typescript
<TabsList className="mb-6">
  <TabsTrigger value="visao-geral">Visão Geral</TabsTrigger>
  <TabsTrigger value="analise">Análise</TabsTrigger>  {/* NOVO */}
  <TabsTrigger value="tonelagem">Tonelagem</TabsTrigger>
  <TabsTrigger value="equipamentos">Equipamentos</TabsTrigger>
  <TabsTrigger value="historico">Histórico</TabsTrigger>
</TabsList>
```

### Passo 6: Adicionar Conteúdo da Aba (após TabsContent "visao-geral")

```typescript
{/* ABA ANÁLISE - NOVO */}
<TabsContent value="analise" className="space-y-6">
  {/* Filtros */}
  <FilterBar
    periodoTipo={periodoTipo}
    setPeriodoTipo={setPeriodoTipo}
    periodoRapido={periodoRapido}
    setPeriodoRapido={setPeriodoRapido}
    dataInicio={dataInicio}
    setDataInicio={setDataInicio}
    dataFim={dataFim}
    setDataFim={setDataFim}
    granularidade={granularidade}
    setGranularidade={setGranularidade}
    turno={turnoFiltro}
    setTurno={setTurnoFiltro}
    turnos={turnos}
    onAplicar={aplicarFiltros}
    onLimpar={limparFiltros}
    onExportar={exportarDados}
  />

  {/* Gráficos */}
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <ProductionChart
      data={dadosProducao}
      meta={linha?.meta_producao_turno}
      periodo={granularidade}
      loading={analiseLoading}
    />
    
    <SpeedChart
      data={dadosVelocidade}
      periodo={granularidade}
      loading={analiseLoading}
    />
  </div>

  <SKUProductionChart
    data={dadosSKU}
    loading={analiseLoading}
  />
</TabsContent>
```

---

## 🧪 Testando

### 1. Testar APIs no Backend

```bash
# Testar API de produção
curl "http://127.0.0.1:8000/api/linhas/1/analise/producao/?granularidade=turno"

# Testar API de velocidade
curl "http://127.0.0.1:8000/api/linhas/1/analise/velocidade/?granularidade=turno"

# Testar API de SKU
curl "http://127.0.0.1:8000/api/linhas/1/analise/sku/"
```

### 2. Verificar Frontend

1. Abra a página de detalhes da linha
2. Clique na aba "Análise"
3. Teste os filtros
4. Verifique se os gráficos aparecem

---

## 📝 Próximos Passos (Opcional)

1. **Persistência de Filtros**: Salvar filtros no localStorage
2. **Exportação**: Implementar exportação para CSV/Excel
3. **Insights**: Adicionar painel de insights automáticos
4. **Árvore de Paradas**: Implementar análise de downtime
5. **Heatmap**: Adicionar mapa de calor de produção

---

## 🐛 Troubleshooting

### APIs retornam erro 500
- Verificar se há dados de métricas no banco
- Verificar logs do Django
- Confirmar que `HistoricoSKU` tem registros

### Gráficos não aparecem
- Abrir console do navegador (F12)
- Verificar erros de importação
- Confirmar que APIs retornam dados

### Filtros não funcionam
- Verificar se funções `aplicarFiltros` e `limparFiltros` estão definidas
- Confirmar que estados estão sendo atualizados
