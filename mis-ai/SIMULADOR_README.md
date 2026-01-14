# Simulador de Futuro (Digital Twin) - MIS-AI

## Visão Geral

O **Simulador de Futuro** é uma interface interativa que permite aos operadores e engenheiros manipular variáveis de processo e visualizar o impacto em tempo real nas predições do modelo de Machine Learning, sem afetar o processo físico.

## Funcionalidades Implementadas

### Backend (Flask)

#### 1. Endpoint de Simulação
**Rota:** `POST /api/models/<model_id>/simulate`

**Descrição:** Executa uma predição usando valores de features fornecidos manualmente.

**Request Body:**
```json
{
  "features": {
    "res=2s=PackagingBox_...": 123.45,
    "res=2s=PackagingBox_...": 67.89,
    ...
  }
}
```

**Response:**
```json
{
  "predicted_value": 727.5432
}
```

#### 2. Endpoint de Metadados
**Rota:** `GET /api/models/<model_id>/metadata`

**Descrição:** Retorna informações sobre as features do modelo, suas importâncias e ranges históricos.

**Response:**
```json
{
  "features": ["feature1", "feature2", ...],
  "feature_importances": [
    {"feature": "feature1", "importance": 0.35},
    {"feature": "feature2", "importance": 0.28},
    ...
  ],
  "feature_ranges": {
    "feature1": {"min": 10.5, "max": 150.2, "mean": 80.3},
    "feature2": {"min": 5.0, "max": 100.0, "mean": 50.0},
    ...
  }
}
```

### Frontend (React)

#### Componentes Principais

1. **Painel de Controle de Features**
   - Sliders interativos para cada variável de processo
   - Campos numéricos editáveis
   - Ranges dinâmicos baseados em dados históricos

2. **Gauge de Predição**
   - Exibição em tempo real do valor predito
   - Atualização automática ao ajustar sliders

3. **Gráfico de Feature Importance**
   - Visualização horizontal (BarChart)
   - Mostra o impacto percentual de cada variável
   - Cores diferenciadas para facilitar identificação

#### Navegação

A página do simulador está acessível através do menu lateral:
- **Ícone:** Play (▶️)
- **Label:** "Simulador"
- **Rota:** `/simulation`

## Como Usar

### Pré-requisitos

1. Ter uma **Linha** criada e configurada
2. Ter um **Target** associado à linha
3. Ter um **Modelo treinado** para o target

### Passo a Passo

1. **Selecione Linha e Target** no cabeçalho da aplicação
2. Navegue até **"Simulador"** no menu lateral
3. **Selecione o modelo** que deseja simular
4. **Ajuste os sliders** das features para testar diferentes cenários
5. **Observe a predição** em tempo real no gauge central
6. **Analise o Feature Importance** para entender quais variáveis têm maior impacto

## Casos de Uso

### 1. Treinamento de Operadores
- Permite que novos operadores entendam o comportamento do processo sem risco
- "Videogame da Fábrica" para aprendizado seguro

### 2. Otimização de Processo
- Teste diferentes combinações de parâmetros antes de aplicar na planta real
- Identifique setpoints ideais para maximizar qualidade ou minimizar custos

### 3. Análise de Sensibilidade
- Descubra quais variáveis têm maior impacto no resultado
- Foque esforços de controle nas variáveis mais críticas (Princípio de Pareto)

### 4. Simulação "What-If"
- "E se eu aumentar a temperatura em 10°C?"
- "Qual será a densidade se eu reduzir a velocidade?"

## Arquitetura Técnica

### Fluxo de Dados

```
[Frontend] Slider Ajustado
    ↓
[React State] featureValues atualizado
    ↓
[useEffect] Detecta mudança
    ↓
[API POST] /api/models/{id}/simulate
    ↓
[Backend] GenericPredictor.simulate()
    ↓
[ML Model] model.predict(X)
    ↓
[Response] {"predicted_value": 727.54}
    ↓
[Frontend] Atualiza Gauge e Histórico
```

### Tecnologias Utilizadas

- **Backend:** Flask, Scikit-learn, Pandas
- **Frontend:** React, Recharts, Radix UI, Tailwind CSS
- **Comunicação:** REST API (JSON)

## Melhorias Futuras

1. **Histórico de Simulações**
   - Salvar cenários testados para comparação posterior

2. **Alertas de Segurança**
   - Indicar quando uma combinação de parâmetros pode ser perigosa

3. **Exportação de Relatórios**
   - Gerar PDFs com os resultados das simulações

4. **Modo Multi-Modelo**
   - Comparar predições de diferentes modelos lado a lado

5. **Integração com MIS Analytics**
   - Sugerir cenários de otimização baseados em análises históricas

## Suporte

Para dúvidas ou problemas, consulte a documentação principal do MIS-AI ou abra uma issue no repositório.
