# Arquitetura das Novas Funcionalidades - MIS-AI

## Visão Geral

Este documento descreve a arquitetura técnica para ampliar as funcionalidades do sistema MIS-AI, focando em treinamento automatizado e controle preditivo de processos industriais.

## 1. Tipos de Variáveis OPC - Extensão

### 1.1 Estado Atual
Atualmente, o sistema possui variáveis OPC com `type_category`:
- **read**: Variáveis de entrada (features) para predição
- **write**: Variáveis de saída (escrita no OPC)

### 1.2 Novos Tipos Propostos

#### 1.2.1 Variável de Referência (Reference)
**Propósito**: Sincronização automática de valores medidos para treinamento contínuo do modelo.

**Características**:
- Sincroniza automaticamente valores do OPC com o banco de dados
- Elimina necessidade de inserção manual de valores medidos
- Permite treinamento automatizado e contínuo
- Associada a um `PredictionTarget` específico

**Exemplo de Uso**:
```
Target: Peso Final (kg)
Variável de Referência: ns=2;s=Balanca.PesoMedido
Sincronização: A cada leitura OPC, o valor é armazenado como measured_value
```

#### 1.2.2 Variável de Controle (Control)
**Propósito**: Ajuste automático de processo baseado em predições.

**Características**:
- Recebe recomendações de ajuste do sistema
- Calcula ajuste proporcional baseado no erro de predição
- Suporta lógica direta e reversa
- Possui fator de relação (0-100%) para controlar intensidade do ajuste

**Exemplo de Uso**:
```
Target: Peso Final = 2200 kg
Predição: 2230 kg (erro de +30 kg = +1.36%)
Variável de Controle: ns=2;s=Disco.Volume
Lógica: Reversa (aumentar controle diminui target)
Fator de Relação: 80%
Recomendação: Reduzir Volume em 1.09% (80% de 1.36%)
```

## 2. Modelo de Dados - Alterações

### 2.1 Extensão da Tabela `opc_variables`

```python
class OPCVariables(Base):
    __tablename__ = 'opc_variables'
    id = Column(Integer, primary_key=True)
    line_name = Column(String(50), ForeignKey('lines.name'), nullable=False)
    node_id = Column(String(100), nullable=False)
    variable_name = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False)
    
    # EXTENSÃO: Novos tipos de categoria
    type_category = Column(String(10), default='read')  
    # Valores: 'read', 'write', 'reference', 'control'
    
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # NOVO: Associação com target (para reference e control)
    target_id = Column(Integer, ForeignKey('prediction_targets.id'), nullable=True)
    
    # NOVO: Configurações de controle (apenas para type_category='control')
    control_config = Column(JSON, nullable=True)
    # Estrutura do JSON:
    # {
    #   "control_logic": "direct" | "reverse",
    #   "relation_factor": 0.0 - 1.0,
    #   "min_adjustment": float,
    #   "max_adjustment": float,
    #   "adjustment_unit": string
    # }
```

### 2.2 Nova Tabela: `control_recommendations`

```python
class ControlRecommendation(Base):
    """Histórico de recomendações de controle"""
    __tablename__ = 'control_recommendations'
    id = Column(Integer, primary_key=True)
    
    # Relacionamentos
    control_variable_id = Column(Integer, ForeignKey('opc_variables.id'), nullable=False)
    prediction_data_id = Column(Integer, ForeignKey('prediction_data.id'), nullable=False)
    
    # Valores da recomendação
    target_value = Column(Float, nullable=False)        # Valor alvo desejado
    predicted_value = Column(Float, nullable=False)     # Valor predito
    error_value = Column(Float, nullable=False)         # Erro absoluto
    error_percentage = Column(Float, nullable=False)    # Erro percentual
    
    # Ajuste recomendado
    current_control_value = Column(Float, nullable=True)  # Valor atual do controle
    recommended_adjustment = Column(Float, nullable=False) # Ajuste sugerido (%)
    recommended_value = Column(Float, nullable=True)      # Novo valor sugerido
    
    # Metadados
    timestamp = Column(DateTime, default=datetime.utcnow)
    applied = Column(Boolean, default=False)              # Se foi aplicado
    applied_at = Column(DateTime, nullable=True)
    
    # Configuração usada
    control_logic = Column(String(10), nullable=False)    # 'direct' ou 'reverse'
    relation_factor = Column(Float, nullable=False)       # 0.0 - 1.0
```

### 2.3 Extensão da Tabela `prediction_data`

```python
class PredictionData(Base):
    __tablename__ = 'prediction_data'
    # ... campos existentes ...
    
    # NOVO: Indicar se foi gerado automaticamente por referência
    auto_generated = Column(Boolean, default=False)
    
    # NOVO: Relacionamento com recomendações de controle
    control_recommendations = relationship('ControlRecommendation', back_populates='prediction_data_obj')
```

## 3. Fluxo de Treinamento Automatizado

### 3.1 Processo de Sincronização Automática

```
┌─────────────────────────────────────────────────────────────┐
│ 1. OPC Client lê variáveis (loop contínuo)                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Identifica variáveis tipo 'reference'                    │
│    - Verifica target_id associado                           │
│    - Captura valor medido                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Captura valores de todas as variáveis 'read' da linha    │
│    - Monta JSON opc_values com features                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Cria registro em PredictionData                          │
│    - target_id: da variável reference                       │
│    - measured_value: valor lido da reference                │
│    - opc_values: JSON com features                          │
│    - data_source: 'auto_reference'                          │
│    - auto_generated: True                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Trigger de Retreinamento (opcional)                      │
│    - A cada N registros novos                               │
│    - Ou em horário programado                               │
│    - Retreina modelo automaticamente                        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Configuração de Política de Retreinamento

```python
class RetrainingPolicy(Base):
    """Política de retreinamento automático"""
    __tablename__ = 'retraining_policies'
    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, ForeignKey('prediction_targets.id'), nullable=False)
    model_id = Column(Integer, ForeignKey('prediction_models.id'), nullable=False)
    
    # Gatilhos de retreinamento
    trigger_type = Column(String(20), nullable=False)  # 'record_count', 'time_interval', 'performance'
    trigger_value = Column(Integer, nullable=True)     # Ex: 100 registros, 24 horas
    
    # Controle
    is_active = Column(Boolean, default=True)
    last_retrain_at = Column(DateTime, nullable=True)
    next_retrain_at = Column(DateTime, nullable=True)
```

## 4. Fluxo de Controle Preditivo

### 4.1 Processo de Recomendação de Ajuste

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Modelo faz predição                                      │
│    - predicted_value = 2230 kg                              │
│    - target_value = 2200 kg (configurado pelo usuário)      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Calcula erro                                             │
│    - error_value = 2230 - 2200 = +30 kg                     │
│    - error_percentage = (30 / 2200) * 100 = +1.36%         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Identifica variáveis de controle associadas ao target    │
│    - Busca OPCVariables com type_category='control'        │
│    - Filtra por target_id                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Para cada variável de controle:                          │
│    a) Lê control_config:                                    │
│       - control_logic = "reverse"                           │
│       - relation_factor = 0.80 (80%)                        │
│    b) Calcula ajuste:                                       │
│       - Se logic = "direct":                                │
│         adjustment = error_percentage * relation_factor     │
│       - Se logic = "reverse":                               │
│         adjustment = -error_percentage * relation_factor    │
│    c) Exemplo:                                              │
│       adjustment = -1.36% * 0.80 = -1.09%                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Lê valor atual da variável de controle (opcional)        │
│    - current_value = 150.0 (unidade do processo)           │
│    - recommended_value = 150.0 * (1 - 0.0109) = 148.36     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Cria ControlRecommendation                               │
│    - Armazena no banco                                      │
│    - Exibe na interface                                     │
│    - Opcionalmente aplica automaticamente                   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Lógica de Controle

#### Lógica Direta (Direct)
- **Conceito**: Aumentar o controle aumenta o target
- **Exemplo**: Temperatura do forno → Temperatura do produto
- **Cálculo**: `adjustment = +error_percentage * relation_factor`

#### Lógica Reversa (Reverse)
- **Conceito**: Aumentar o controle diminui o target
- **Exemplo**: Velocidade da esteira → Peso por unidade
- **Cálculo**: `adjustment = -error_percentage * relation_factor`

### 4.3 Fator de Relação (Relation Factor)

O fator de relação controla a intensidade do ajuste:
- **0.0 (0%)**: Nenhum ajuste aplicado
- **0.5 (50%)**: Ajuste moderado (metade do erro)
- **1.0 (100%)**: Ajuste completo (todo o erro)

**Benefícios**:
- Evita overshooting (ajustes excessivos)
- Permite sintonia fina do controle
- Adaptação a processos com diferentes dinâmicas

## 5. API Endpoints - Novos

### 5.1 Variáveis de Referência

```
POST /api/opc/variables/reference
Body: {
  "line_name": "L01",
  "node_id": "ns=2;s=Balanca.PesoMedido",
  "variable_name": "Peso Medido",
  "target_id": 1,
  "type": "Float",
  "description": "Peso medido pela balança"
}

GET /api/opc/variables/reference?line=L01&target_id=1
Response: [lista de variáveis de referência]
```

### 5.2 Variáveis de Controle

```
POST /api/opc/variables/control
Body: {
  "line_name": "L01",
  "node_id": "ns=2;s=Disco.Volume",
  "variable_name": "Volume do Disco",
  "target_id": 1,
  "type": "Float",
  "control_config": {
    "control_logic": "reverse",
    "relation_factor": 0.80,
    "min_adjustment": -10.0,
    "max_adjustment": 10.0,
    "adjustment_unit": "%"
  }
}

GET /api/opc/variables/control?line=L01&target_id=1
Response: [lista de variáveis de controle]

PUT /api/opc/variables/control/{id}/config
Body: {
  "control_logic": "reverse",
  "relation_factor": 0.75
}
```

### 5.3 Recomendações de Controle

```
GET /api/control/recommendations?target_id=1&limit=20
Response: [lista de recomendações]

POST /api/control/recommendations/{id}/apply
Body: {
  "apply_to_opc": true
}
Response: {
  "message": "Ajuste aplicado com sucesso",
  "written_value": 148.36
}

GET /api/control/recommendations/active?line=L01
Response: [recomendações pendentes de aplicação]
```

### 5.4 Políticas de Retreinamento

```
POST /api/retraining/policies
Body: {
  "target_id": 1,
  "model_id": 1,
  "trigger_type": "record_count",
  "trigger_value": 100
}

GET /api/retraining/policies?target_id=1
Response: [lista de políticas]

POST /api/retraining/trigger/{policy_id}
Response: {
  "message": "Retreinamento iniciado",
  "job_id": "abc123"
}
```

## 6. Interface do Usuário - Melhorias

### 6.1 Tela de Configuração de Variáveis

**Seção: Tipo de Variável**
- [ ] Input (Leitura)
- [ ] Output (Escrita)
- [x] Referência (Treinamento Automático)
- [ ] Controle (Ajuste Preditivo)

**Se Referência:**
- Target Associado: [Dropdown]
- Frequência de Captura: [Input] segundos

**Se Controle:**
- Target Associado: [Dropdown]
- Lógica de Controle: ( ) Direta  (x) Reversa
- Fator de Relação: [Slider 0-100%] 80%
- Ajuste Mínimo: [Input] %
- Ajuste Máximo: [Input] %

### 6.2 Tela de Recomendações de Controle

**Dashboard de Controle Preditivo**

```
┌─────────────────────────────────────────────────────────────┐
│ Target: Peso Final (kg)                                     │
│ Valor Alvo: 2200 kg                                         │
│ Última Predição: 2230 kg (+30 kg, +1.36%)                  │
├─────────────────────────────────────────────────────────────┤
│ Recomendações de Ajuste:                                    │
│                                                             │
│ 🎛️ Volume do Disco                                          │
│   Valor Atual: 150.0 L                                     │
│   Ajuste Recomendado: -1.09% (-1.64 L)                     │
│   Novo Valor Sugerido: 148.36 L                            │
│   [Aplicar Ajuste] [Ignorar]                               │
│                                                             │
│ 🎛️ Velocidade da Esteira                                    │
│   Valor Atual: 2.5 m/s                                     │
│   Ajuste Recomendado: -0.82% (-0.02 m/s)                   │
│   Novo Valor Sugerido: 2.48 m/s                            │
│   [Aplicar Ajuste] [Ignorar]                               │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Tela de Treinamento Automático

**Status de Treinamento Contínuo**

```
┌─────────────────────────────────────────────────────────────┐
│ Target: Peso Final (kg)                                     │
│ Modelo Ativo: RandomForest_v2                               │
├─────────────────────────────────────────────────────────────┤
│ Dados de Treinamento:                                       │
│   Total de Registros: 1,247                                │
│   Registros Automáticos: 1,180 (94.6%)                     │
│   Registros Manuais: 67 (5.4%)                             │
│                                                             │
│ Última Atualização: 2026-01-31 14:32:15                    │
│ Próximo Retreinamento: Em 23 registros                     │
│                                                             │
│ [Treinar Agora] [Configurar Política]                      │
└─────────────────────────────────────────────────────────────┘
```

## 7. Melhorias Técnicas Adicionais

### 7.1 Sistema de Validação de Recomendações

Antes de aplicar um ajuste, o sistema deve validar:
- Limites de segurança (min/max)
- Taxa de mudança máxima
- Tempo mínimo entre ajustes
- Confirmação do operador (opcional)

### 7.2 Histórico e Análise de Efetividade

Rastrear efetividade dos ajustes:
- Erro antes do ajuste
- Erro depois do ajuste
- Taxa de sucesso (% de ajustes que melhoraram o resultado)
- Tempo de resposta do processo

### 7.3 Modo de Operação

**Manual**: Recomendações apenas exibidas
**Semi-Automático**: Recomendações aplicadas com confirmação
**Automático**: Recomendações aplicadas automaticamente

### 7.4 Integração com InfluxDB

Armazenar séries temporais de:
- Valores preditos vs medidos
- Ajustes aplicados
- Performance do modelo ao longo do tempo

## 8. Considerações de Implementação

### 8.1 Ordem de Implementação

1. **Fase 1**: Extensão do modelo de dados
2. **Fase 2**: Variáveis de referência + sincronização automática
3. **Fase 3**: Variáveis de controle + cálculo de recomendações
4. **Fase 4**: Interface de usuário
5. **Fase 5**: Políticas de retreinamento
6. **Fase 6**: Validação e testes

### 8.2 Compatibilidade Retroativa

Todas as alterações devem manter compatibilidade com:
- Variáveis OPC existentes (read/write)
- Dados históricos de treinamento
- Modelos já treinados

### 8.3 Performance

- Sincronização automática não deve impactar ciclo OPC
- Cálculo de recomendações deve ser assíncrono
- Cache de modelos em memória

## 9. Casos de Uso

### 9.1 Controle de Peso em Linha de Empacotamento

**Problema**: Peso final varia devido a densidade do material

**Solução**:
- Variável de Referência: Balança de saída
- Features: Volume dosado, velocidade, temperatura
- Variável de Controle: Volume do dosador (lógica reversa)
- Fator de Relação: 70% (ajuste conservador)

### 9.2 Controle de Temperatura em Extrusora

**Problema**: Temperatura do produto varia com condições ambientes

**Solução**:
- Variável de Referência: Sensor de temperatura do produto
- Features: Temperatura ambiente, velocidade, pressão
- Variável de Controle: Setpoint do aquecedor (lógica direta)
- Fator de Relação: 90% (resposta rápida)

### 9.3 Controle de Densidade em Misturador

**Problema**: Densidade do mix varia com proporção de ingredientes

**Solução**:
- Variável de Referência: Densímetro online
- Features: Proporções de ingredientes, tempo de mistura
- Variáveis de Controle: 
  - Ingrediente A (lógica direta, 80%)
  - Ingrediente B (lógica reversa, 60%)

## 10. Conclusão

Esta arquitetura proporciona:
- **Automação**: Treinamento contínuo sem intervenção manual
- **Controle Preditivo**: Ajustes proativos baseados em predições
- **Flexibilidade**: Configuração adaptável a diferentes processos
- **Segurança**: Validações e limites configuráveis
- **Rastreabilidade**: Histórico completo de recomendações e ajustes

O sistema evolui de um preditor passivo para um **controlador preditivo ativo**, agregando valor significativo ao processo industrial.
