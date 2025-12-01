# Alterações - Tela FactoryManagement com Vazão Necessária

**Branch:** `manus_review`  
**Data:** 01/12/2024  
**Commit:** 1b35290

## Resumo Executivo

Refatoração completa da tela **FactoryManagement** para implementar um sistema de **gerenciamento de vazão necessária** (throughput required). A tela agora exibe dados consolidados de planejamento de produção, produção realizada e calcula dinamicamente a vazão necessária para cumprir as metas em diferentes períodos (turno, dia, semana, mês).

## Mudanças Realizadas

### 1. Backend Django

#### Novo Arquivo: `vazao_helpers.py`

Implementa a classe `VazaoCalculator` com métodos para calcular vazão necessária:

**Métodos principais:**
- `get_turno_atual()` - Retorna o turno atual baseado na hora do sistema
- `calcular_horas_restantes_turno()` - Calcula horas restantes do turno
- `calcular_horas_restantes_dia()` - Calcula horas restantes do dia
- `calcular_horas_restantes_semana()` - Calcula horas restantes da semana
- `calcular_horas_restantes_mes()` - Calcula horas restantes do mês

**Métodos de dados:**
- `get_planejado_turno()` - Retorna planejado do turno
- `get_produzido_turno()` - Retorna produzido do turno
- `get_planejado_dia()` - Retorna planejado do dia
- `get_produzido_dia()` - Retorna produzido do dia
- `get_planejado_semana()` - Retorna planejado da semana
- `get_produzido_semana()` - Retorna produzido da semana
- `get_planejado_mes()` - Retorna planejado do mês
- `get_produzido_mes()` - Retorna produzido do mês

**Métodos de cálculo:**
- `calcular_vazao_necessaria_turno()` - Calcula vazão necessária para o turno
- `calcular_vazao_necessaria_dia()` - Calcula vazão necessária para o dia
- `calcular_vazao_necessaria_semana()` - Calcula vazão necessária para a semana
- `calcular_vazao_necessaria_mes()` - Calcula vazão necessária para o mês
- `calcular_todas_vazoes()` - Calcula vazão para todos os períodos

**Fórmula de cálculo:**
```
vazao_necessaria = (planejado_total - produzido_total) / horas_restantes
```

**Status:**
- `OK` - Vazão necessária ≤ Meta de vazão da linha
- `CRÍTICO` - Vazão necessária > Meta de vazão da linha

#### Modificações em `views.py`

Adicionados 3 novos endpoints:

1. **`vazao_necessaria_linha(request, linha_id)`**
   - Endpoint: `GET /api/linhas/{linha_id}/vazao-necessaria/`
   - Query param: `periodo` (TURNO, DIA, SEMANA, MÊS, ou TODOS)
   - Retorna vazão necessária de uma linha específica

2. **`vazao_necessaria_todas_linhas(request)`**
   - Endpoint: `GET /api/vazao-necessaria/`
   - Retorna vazão necessária de todas as linhas ativas

3. **`dashboard_factory_manage(request)`**
   - Endpoint: `GET /api/dashboard/factory-manage/`
   - Retorna dashboard consolidado com:
     - Dados de vazão para todas as linhas
     - Alertas críticos
     - Timestamp da atualização

#### Modificações em `urls.py`

Adicionadas 3 novas rotas:
```python
path('linhas/<int:linha_id>/vazao-necessaria/', views.vazao_necessaria_linha, name='vazao-necessaria-linha'),
path('vazao-necessaria/', views.vazao_necessaria_todas_linhas, name='vazao-necessaria-todas'),
path('dashboard/factory-manage/', views.dashboard_factory_manage, name='dashboard-factory-manage'),
```

### 2. Frontend React

#### Refatoração de `FactoryManagement.tsx`

**Mudanças principais:**
- Removido: Gerenciamento de "Iniciativas Estratégicas"
- Adicionado: Sistema de visualização de vazão necessária
- Adicionado: Seletor de período (TURNO, DIA, SEMANA, MÊS)
- Adicionado: Auto-refresh a cada 30 segundos
- Adicionado: Alertas consolidados
- Adicionado: Tabela interativa com dados de vazão

**Interfaces TypeScript:**
```typescript
interface VazaoData {
  periodo: 'TURNO' | 'DIA' | 'SEMANA' | 'MÊS';
  turno?: string;
  turno_codigo?: string;
  data: string;
  planejado: number;
  produzido: number;
  falta_produzir: number;
  horas_restantes: number;
  vazao_necessaria: number;
  meta_vazao: number;
  status: 'OK' | 'CRÍTICO';
}

interface LinhaVazao {
  linha_id: number;
  linha_codigo: string;
  linha_nome: string;
  turno: VazaoData;
  dia: VazaoData;
  semana: VazaoData;
  mes: VazaoData;
}

interface DashboardData {
  status: string;
  timestamp: string;
  total_linhas: number;
  alertas_criticos: number;
  linhas: LinhaVazao[];
  alertas: Array<{...}>;
}
```

**Componentes UI:**
- Card com seletor de período
- Tabela com dados consolidados
- Seção de alertas críticos
- Rodapé com legenda
- Indicadores visuais (ícones, cores, badges)

**Funcionalidades:**
- Auto-refresh habilitável/desabilitável
- Botão de atualização manual
- Filtro por período
- Codificação de cores por status
- Ícones informativos

## Estrutura de Dados Retornada

### Resposta do Endpoint `/api/dashboard/factory-manage/`

```json
{
  "status": "success",
  "timestamp": "2024-12-01T10:30:00Z",
  "total_linhas": 3,
  "alertas_criticos": 1,
  "linhas": [
    {
      "linha_id": 1,
      "linha_codigo": "L001",
      "linha_nome": "Linha Envase",
      "turno": {
        "periodo": "TURNO",
        "turno": "Turno A",
        "turno_codigo": "A",
        "data": "2024-12-01",
        "planejado": 1000,
        "produzido": 500.0,
        "falta_produzir": 500.0,
        "horas_restantes": 4.5,
        "vazao_necessaria": 111.11,
        "meta_vazao": 100.0,
        "status": "CRÍTICO"
      },
      "dia": {...},
      "semana": {...},
      "mes": {...}
    }
  ],
  "alertas": [
    {
      "linha_id": 1,
      "linha_codigo": "L001",
      "linha_nome": "Linha Envase",
      "periodo": "TURNO",
      "vazao_necessaria": 111.11,
      "meta_vazao": 100.0,
      "falta_produzir": 500.0,
      "horas_restantes": 4.5
    }
  ]
}
```

## Fluxo de Dados

```
CalendarioProducao (Planejado)
        ↓
VazaoCalculator.get_planejado_*()
        ↓
RegistroProducaoTurno (Produzido)
        ↓
VazaoCalculator.get_produzido_*()
        ↓
VazaoCalculator.calcular_vazao_necessaria_*()
        ↓
views.dashboard_factory_manage()
        ↓
Frontend FactoryManagement.tsx
        ↓
Visualização com Alertas
```

## Períodos Suportados

### TURNO
- Calcula baseado no turno atual
- Horas restantes até o fim do turno
- Planejado/Produzido do turno específico

### DIA
- Calcula para o dia corrente (00:00 até 23:59)
- Horas restantes até 23:59:59
- Soma de todos os turnos do dia

### SEMANA
- Calcula para a semana corrente (segunda até domingo)
- Horas restantes até domingo 23:59:59
- Soma de todos os dias da semana

### MÊS
- Calcula para o mês corrente
- Horas restantes até o último dia do mês 23:59:59
- Soma de todos os dias do mês

## Dependências

### Backend
- Django ORM (models.py)
- CalendarioProducao (modelo de planejamento)
- RegistroProducaoTurno (modelo de produção realizada)
- TurnoProducao (modelo de turnos)
- LinhaProducao (modelo de linhas)

### Frontend
- React 18+
- TypeScript
- UI Components (Button, Table, Card, Badge, Alert)
- Lucide Icons

## Testes Recomendados

1. **Teste de Cálculo:**
   - Verificar se vazão necessária = (planejado - produzido) / horas_restantes
   - Validar status OK/CRÍTICO baseado em meta_vazao

2. **Teste de Períodos:**
   - Turno: Verificar se calcula corretamente para turno atual
   - Dia: Verificar soma de todos os turnos
   - Semana: Verificar segunda-feira até domingo
   - Mês: Verificar primeiro até último dia do mês

3. **Teste de API:**
   - GET /api/linhas/{id}/vazao-necessaria/?periodo=TURNO
   - GET /api/vazao-necessaria/
   - GET /api/dashboard/factory-manage/

4. **Teste de UI:**
   - Auto-refresh funciona a cada 30 segundos
   - Seletor de período muda dados corretamente
   - Alertas críticos aparecem corretamente
   - Cores e status refletem dados

## Próximos Passos Sugeridos

1. **Integração com InfluxDB:**
   - Buscar dados de produção em tempo real do InfluxDB
   - Atualizar produzido em tempo real

2. **Notificações:**
   - Implementar alertas em tempo real quando status muda para CRÍTICO
   - Integrar com sistema de notificações

3. **Histórico:**
   - Manter histórico de vazão necessária
   - Gráficos de tendência

4. **Configuração:**
   - Permitir edição de meta_vazao por linha
   - Permitir ajuste de períodos

5. **Otimizações:**
   - Cache de dados
   - Paginação para muitas linhas
   - Filtros adicionais

## Notas Importantes

- A vazão necessária é calculada **em tempo real** baseada na hora atual
- O sistema assume que `CalendarioProducao` contém o planejamento correto
- O sistema assume que `RegistroProducaoTurno` é atualizado com produção realizada
- Horas restantes são calculadas dinamicamente
- Status CRÍTICO indica que a linha precisa aumentar velocidade para cumprir meta

## Arquivos Modificados

1. `backend-django/equipamentos/vazao_helpers.py` (NOVO)
2. `backend-django/equipamentos/views.py` (MODIFICADO)
3. `backend-django/equipamentos/urls.py` (MODIFICADO)
4. `frontend-react/client/src/pages/FactoryManagement.tsx` (REFATORADO)

## Commit

```
1b35290 feat: Implementar tela FactoryManagement com cálculo de vazão necessária
```

Branch: `manus_review`
