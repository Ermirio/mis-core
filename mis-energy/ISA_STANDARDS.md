# Padrões ISA-88 e ISA-101 Implementados no MIS-Energy

## ISA-88: Hierarquia de Equipamentos

A aplicação MIS-Energy segue a estrutura hierárquica definida pela norma ISA-88 para sistemas de controle de processos em batelada:

### Níveis Hierárquicos Suportados

1. **Enterprise (Empresa)** - Nível corporativo
2. **Site (Fábrica)** - `type: 'factory'`
3. **Area (Área)** - `type: 'area'`
4. **Process Cell (Linha de Produção)** - `type: 'line'`
5. **Unit (Grupo de Máquinas)** - `type: 'machine_group'`
6. **Equipment Module (Equipamento)** - Modelo `Equipment`

### Implementação no Banco de Dados

O modelo `Hierarchy` suporta estrutura recursiva com:
- `parent_id`: Referência ao nível hierárquico superior
- `type`: Tipo do nível hierárquico
- `code`: Código único para identificação (ex: FAC1, AREA2, LIN3)
- `name`: Nome descritivo

### Exemplo de Estrutura

```
Fábrica São Paulo (FAC1)
├── Área de Produção (AREA1)
│   ├── Linha 1 (LIN1)
│   │   ├── Grupo de Motores (MG1)
│   │   │   └── Motor Principal (EQ001)
│   │   └── Medidor de Energia (EQ002)
│   └── Linha 2 (LIN2)
└── Área de Utilidades (AREA2)
    └── Subestação (SUB1)
        └── Transformador (EQ003)
```

## ISA-101: Interface Humano-Máquina (HMI)

A aplicação segue as diretrizes da norma ISA-101 para design de interfaces industriais:

### Paleta de Cores Padronizada

#### Estados Operacionais
- **Verde (#10B981)**: Operação normal, valores dentro do esperado
- **Amarelo/Âmbar (#F59E0B)**: Atenção, valores próximos aos limites
- **Vermelho (#EF4444)**: Alerta, valores fora dos limites aceitáveis
- **Azul (#3B82F6)**: Informação, estado neutro
- **Roxo (#8B5CF6)**: Métricas de qualidade (ex: fator de potência)

#### Elementos de Interface
- **Cinza (#64748B)**: Equipamentos inativos ou desabilitados
- **Branco/Preto**: Texto e backgrounds (modo claro/escuro)

### Princípios de Design Aplicados

1. **Hierarquia Visual**: Informações mais críticas em destaque (tamanho, cor, posição)
2. **Consistência**: Mesmos padrões de cores e ícones em toda a aplicação
3. **Feedback Imediato**: Indicadores visuais de estado em tempo real
4. **Densidade de Informação**: Cards compactos com informações essenciais
5. **Navegação Contextual**: Filtros por hierarquia para navegação intuitiva

### Componentes Conformes

#### Cards de Equipamento
- Ícone diferenciado por tipo (energia vs produção)
- Badge de status (On/Off) com cores padronizadas
- Valor em tempo real com código de cores
- Métricas financeiras destacadas
- Barra de progresso para comparação com padrão

#### Dashboards
- Cards de resumo com métricas principais (KPIs)
- Gráficos de tendência com cores consistentes
- Filtros de período e hierarquia
- Alertas visuais para anomalias

#### Painel de Métricas
- Separação por abas (Tendência, Custo, Qualidade)
- Métricas específicas por tipo de medidor
- Tooltips informativos
- Atualização automática

## Conformidade e Boas Práticas

### Nomenclatura
- Tags de equipamentos seguem padrão: `{FACTORY}-{AREA}-{LINE}-{TYPE}-{NUMBER}`
- Exemplo: `F001-A001-L001-ENM-001` (Fábrica 001, Área 001, Linha 001, Energy Meter 001)

### Métricas
- **Energia**: power_kw, energy_kwh, demand_kw, power_factor
- **Produção**: flow_rate, total_production, efficiency, specific_consumption

### Alertas
- Fator de potência < 0.92: Alerta amarelo
- Demanda > limite configurado: Alerta vermelho
- Eficiência < 85%: Alerta para medidores de produção
- Consumo específico acima do padrão: Alerta financeiro

## Referências

- **ISA-88**: Batch Control Standard (ANSI/ISA-88.00.01-2010)
- **ISA-101**: Human Machine Interfaces for Process Automation Systems (ANSI/ISA-101.01-2015)
