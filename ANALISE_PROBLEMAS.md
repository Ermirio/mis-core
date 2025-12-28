# Análise de Problemas - Home e LineDeepView

## Data: 28/12/2025

## Problemas Identificados

### 1. **Home.tsx - Tratamento de Dados Frágil**

#### 1.1 Falta de Validação de Dados Nulos/Undefined
- **Linha 88-98**: `fetchConfiguracao()` não valida se `data.results` ou `data` são arrays válidos
- **Linha 112-151**: `fetchTempoReal()` retorna `null` em caso de erro, mas não há tratamento robusto
- **Linha 124-141**: Construção de `medicoes` sem validação de campos obrigatórios
- **Linha 304-308**: `eqLider` pode ser undefined se array estiver vazio

#### 1.2 Cálculos sem Proteção contra Divisão por Zero
- **Linha 212-228**: Cálculo de projeção sem verificar se `tempoDecorridoHoras > 0`
- **Linha 222**: `vazaoCalculada` pode ser NaN se `tempoDecorridoHoras === 0`

#### 1.3 Fallbacks Inconsistentes
- **Linha 317-330**: Múltiplos fallbacks encadeados sem garantia de tipo
- **Linha 323-328**: Dados podem vir de 3 fontes diferentes (ole_data, medicoes, metricas) sem priorização clara

#### 1.4 Estado de Loading Inadequado
- **Linha 263**: `if (linhas.length === 0)` só seta erro se não houver linhas, mas pode haver erro parcial
- **Linha 296-298**: Loading só mostra spinner, não indica qual etapa está carregando

### 2. **LineDeepView.tsx - Lógica de Busca e Resolução Frágil**

#### 2.1 Resolução de Linha Ambígua
- **Linha 127-136**: Busca por código e depois por nome, mas pode retornar múltiplos resultados
- **Linha 143-148**: Lógica de fuzzy match pode selecionar linha errada
- **Linha 154**: Uso de `codigo` para Flask API, mas fallback não é robusto

#### 2.2 Falta de Tratamento de Erros em Promises Paralelas
- **Linha 166-171**: `Promise.all()` sem try-catch individual
- **Linha 186-206**: Promises de equipamentos sem tratamento de erro individual
- Se um equipamento falhar, todo o array pode ficar inconsistente

#### 2.3 Cálculos Duplicados e Inconsistentes
- **Linha 257**: `vazaoCalculada` tem 3 fontes diferentes sem priorização clara
- **Linha 260-274**: Lógica de projeção duplicada entre Home.tsx e LineDeepView.tsx
- **Linha 280**: `ritmoNecessario` pode resultar em divisão por zero

#### 2.4 Estado Inicial Inadequado
- **Linha 231-233**: Condição de loading verifica `lineStatus` e `equipamentosDetalhados`, mas não `oleData`
- Pode renderizar componentes com dados parciais

### 3. **Componentes - Falta de Validação de Props**

#### 3.1 LineOverview.tsx
- Não verificado ainda, mas recebe props sem validação de tipo em runtime
- Props opcionais podem ser undefined e causar erros de renderização

#### 3.2 EquipamentoCard.tsx
- Recebe `estado` como string, mas pode vir como número
- Falta normalização de dados antes de passar para componente

#### 3.3 MultiEquipmentTimeline.tsx
- Recebe array de equipamentos sem validação de estrutura
- Pode falhar se equipamentos não tiverem campos esperados

### 4. **Problemas de Arquitetura de Dados**

#### 4.1 Múltiplas Fontes de Verdade
- Dados vêm de 3 APIs diferentes (Django Config, Flask Operação, Flask Equipamento)
- Não há estratégia clara de merge e priorização
- Campos duplicados com nomes diferentes (meta_turno vs producao_planejada_total)

#### 4.2 Falta de Tipagem Forte
- Interfaces definidas, mas não há validação em runtime
- `any` usado em vários lugares (linha 66-68, 86)

#### 4.3 Polling Agressivo sem Debounce
- **Home.tsx linha 271**: Polling de 5s sem verificar se request anterior terminou
- **LineDeepView.tsx linha 227**: Mesmo problema
- Pode causar race conditions e múltiplas requests simultâneas

## Prioridades de Correção

### Alta Prioridade (Impacto Crítico)
1. ✅ Adicionar validação de dados nulos/undefined em todas as funções de fetch
2. ✅ Proteger todos os cálculos matemáticos contra divisão por zero e NaN
3. ✅ Melhorar lógica de resolução de linha em LineDeepView
4. ✅ Adicionar tratamento de erro individual em Promise.all

### Média Prioridade (Impacto Moderado)
5. ✅ Normalizar dados antes de passar para componentes
6. ✅ Criar funções utilitárias para cálculos repetidos (projeção, vazão)
7. ✅ Adicionar debounce/flag para evitar múltiplas requests simultâneas
8. ✅ Melhorar estado de loading com indicadores mais específicos

### Baixa Prioridade (Melhorias)
9. ✅ Adicionar validação de runtime para interfaces críticas
10. ✅ Documentar priorização de fontes de dados
11. ✅ Criar testes unitários para funções de cálculo

## Próximos Passos

1. Criar funções utilitárias para validação e cálculos
2. Refatorar Home.tsx com validações robustas
3. Refatorar LineDeepView.tsx com lógica de busca melhorada
4. Adicionar tratamento de erro granular
5. Testar cenários de falha (API offline, dados parciais, etc.)
