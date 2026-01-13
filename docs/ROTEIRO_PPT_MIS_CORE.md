# Roteiro para Apresentação PowerPoint - MIS-Core
## Para geração via Manus AI

---

## INSTRUÇÕES PARA O MANUS AI

1. **Use as imagens fornecidas** para ilustrar cada slide
2. **Mantenha design moderno** com cores azul escuro (#1a1a2e) e acentos em azul elétrico (#4da3ff)
3. **Cada slide deve ter**: Título, 3-5 bullet points, e espaço para imagem/screenshot
4. **Total de slides sugerido**: 20-25 slides

---

## SLIDE 1: CAPA

**Título:** MIS-Core - Manufacturing Intelligence System

**Subtítulo:** Plataforma de Gestão e Análise de Linha de Produção

**Elementos visuais:**
- Logo MIS-Core
- Imagem de fundo sugerida: Linha de produção moderna com overlay escuro

---

## SLIDE 2: O DESAFIO DA INDÚSTRIA

**Título:** Os Desafios do Chão de Fábrica

**Pontos:**
- Falta de visibilidade em tempo real da produção
- Dificuldade em identificar gargalos e perdas
- Dados dispersos em sistemas isolados
- Tomada de decisão baseada em "feeling" ao invés de dados
- Tempo excessivo para gerar relatórios

**Imagem sugerida:** Ilustração de fábrica com interrogações ou ícones de problemas

---

## SLIDE 3: A SOLUÇÃO MIS-CORE

**Título:** MIS-Core: Sua Fábrica na Palma da Mão

**Pontos:**
- Sistema web de gestão de linhas de produção
- Coleta automática de dados via OPC-UA
- Dashboards em tempo real
- Análise de perdas e OEE
- Integração com ERPs e sistemas legados

**Imagem:** Screenshot da tela inicial do MIS-Core (Home.tsx)

---

## SLIDE 4: ARQUITETURA DA SOLUÇÃO

**Título:** Arquitetura Robusta e Escalável

**Diagrama com 4 camadas:**
1. **Camada de Coleta**: PLCs → OPC-UA → Coletor MIS-Core
2. **Camada de Dados**: MySQL + InfluxDB (time-series)
3. **Camada de Aplicação**: Django (API) + Flask (Analytics)
4. **Camada de Visualização**: React.js (Dashboards)

**Imagem:** Diagrama de arquitetura com ícones

---

## SLIDE 5: HOME - VISÃO GERAL DA FÁBRICA

**Título:** Dashboard Principal - Visão 360°

**Funcionalidades:**
- Mapa da fábrica com status das linhas
- Cards de KPIs em tempo real
- Indicadores de status por área
- Alertas e notificações
- Acesso rápido às linhas

**Imagem:** Screenshot da página Home.tsx

---

## SLIDE 6: GESTÃO DE LINHAS

**Título:** Factory Management Panel - Gestão Centralizada

**Funcionalidades:**
- Cadastro de fábricas, áreas e linhas
- Configuração de equipamentos
- Definição de metas (OEE, produção, toneladas)
- Hierarquia organizacional
- Histórico de configurações

**Imagem:** Screenshot do FactoryManagementPanel.tsx

---

## SLIDE 7: LINE DEEP VIEW - VISÃO PROFUNDA DA LINHA

**Título:** Line Deep View - Mergulhe nos Dados

**Componentes do dashboard:**
- **Header**: Linha selecionada, período, status atual
- **KPIs**: OEE, Disponibilidade, Performance, Qualidade
- **Progress**: Barra de progresso da meta
- **Timeline**: Histórico de estados em tempo real
- **Equipment Cards**: Status de cada equipamento

**Imagem:** Screenshot da LineDeepView.tsx

---

## SLIDE 8: TIMELINE DE ESTADOS

**Título:** Timeline Interativa de Estados

**Funcionalidades:**
- Visualização gráfica dos estados ao longo do tempo
- Cores por tipo de estado (RUN, FAULT, WAIT_PREV, etc.)
- Zoom temporal (hora, dia, semana)
- Click para detalhamento
- Múltiplos equipamentos simultâneos

**Imagem:** Screenshot do MultiEquipmentTimeline.tsx

**Legenda de estados:**
| Cor | Estado | Descrição |
|-----|--------|-----------|
| 🟢 Verde | RUN | Produzindo |
| 🔴 Vermelho | FAULT | Falha |
| 🟡 Amarelo | WAIT_PREV | Aguardando anterior |
| 🟠 Laranja | BLOCK_NEXT | Bloqueado posterior |
| 🔵 Azul | SETUP | Troca de SKU |

---

## SLIDE 9: DETALHES DO EQUIPAMENTO

**Título:** Equipamento Detalhes - Análise Individual

**Funcionalidades:**
- Informações técnicas do equipamento
- Histórico de estados
- Sensores associados (contagem, velocidade, temperatura)
- Tags OPC configuradas
- Gráficos de performance

**Imagem:** Screenshot de EquipamentoDetalhes.tsx

---

## SLIDE 10: GOLDEN STATE - DIAGNÓSTICO INTELIGENTE

**Título:** Golden State - O Estado Ideal da Máquina

**Conceito:**
- Perfil de operação "ideal" baseado em dados históricos
- Comparação tempo real vs. estado ótimo
- Detecção automática de anomalias
- Sugestões de ajuste

**Funcionalidades do DiagnosticsPanel:**
- Variáveis monitoradas
- Limites operacionais (LSL, USL, Target)
- Gráficos de tendência
- Alertas de desvio

**Imagem:** Screenshot do GoldenState/DiagnosticsPanel.tsx

---

## SLIDE 11: ANALYTICS - PERFIS DE ANÁLISE

**Título:** Analytics On-Click - Análise com Um Clique

**ProfileManager - Funcionalidades:**
- Criação de perfis de análise pré-configurados
- Seleção de variáveis para análise
- Salvamento de configurações favoritas
- Compartilhamento entre usuários

**Casos de uso:**
- Perfil "Velocidade x Qualidade"
- Perfil "Eficiência Energética"
- Perfil "Análise de Rejeitos"

**Imagem:** Screenshot do Analytics/ProfileManager.tsx

---

## SLIDE 12: LINE ANALYTICS - ANÁLISE AVANÇADA

**Título:** Line Analytics - Inteligência de Produção

**Funcionalidades (40k+ linhas de código):**
- Análise de correlação entre variáveis
- Gráficos de dispersão (Scatter plots)
- Análise de Pareto de paradas
- Comparação entre turnos
- Tendências de produção

**Imagem:** Screenshot de LineAnalytics.tsx com gráficos

---

## SLIDE 13: ANÁLISE DE PERDAS - LOSS ANALYSIS

**Título:** Loss Analysis - Onde Está Seu Dinheiro?

**Componentes:**
1. **LossWaterfallChart**: Cascata de perdas (tempo disponível → tempo produtivo)
2. **LossTreeCard**: Árvore hierárquica de perdas
3. **LossEquipmentRanking**: Ranking de equipamentos por perda
4. **LossWasteAnalysis**: Análise de desperdícios

**Imagem:** Screenshot dos gráficos de Loss Analysis

---

## SLIDE 14: WATERFALL DE PERDAS

**Título:** Waterfall Chart - Visualize Cada Perda

**Estrutura do gráfico:**
```
Tempo Calendário (24h)
  └─ (−) Paradas Planejadas = Tempo Disponível
      └─ (−) Paradas Não Planejadas = Tempo Operacional
          └─ (−) Perdas de Performance = Tempo Líquido
              └─ (−) Perdas de Qualidade = Tempo Produtivo Real
```

**Imagem:** Screenshot do LossWaterfallChart.tsx

---

## SLIDE 15: PARETO DE PARADAS

**Título:** Pareto de Paradas - Foco no que Importa

**Funcionalidades:**
- Ranking das principais causas de parada
- Tempo acumulado por causa
- % do total de paradas
- Filtro por período e equipamento
- Linha de acumulação 80/20

**Imagem:** Screenshot do ParetoChart.tsx

---

## SLIDE 16: COMPARAÇÃO DE TURNOS

**Título:** Shift Comparison - Compare Performance

**Funcionalidades:**
- Comparação entre turnos (manhã, tarde, noite)
- Métricas: produção, OEE, paradas
- Identificação de melhores práticas
- Benchmarking interno

**Imagem:** Screenshot do ShiftComparisonChart.tsx

---

## SLIDE 17: GRÁFICOS DE PRODUÇÃO

**Título:** Production Charts - Visualize sua Produção

**Tipos de gráficos disponíveis:**
- **ProductionChart**: Produção por hora/turno
- **SKUProductionChart**: Produção por produto (SKU)
- **SpeedChart**: Velocidade ao longo do tempo
- **ThroughputChart**: Vazão de produção
- **TonnageCard**: Toneladas produzidas

**Imagem:** Composição de screenshots dos gráficos

---

## SLIDE 18: CORRELAÇÃO DE VARIÁVEIS

**Título:** Correlation Scatter - Encontre Padrões

**Funcionalidades:**
- Scatter plot de duas variáveis
- Linha de tendência automática
- Coeficiente de correlação (R²)
- Identificação de outliers
- Filtro por período e condições

**Imagem:** Screenshot do CorrelationScatter.tsx

---

## SLIDE 19: STRATEGIC ANALYSIS

**Título:** Strategic Analysis - Visão Estratégica

**Funcionalidades (19k+ linhas de código):**
- Análise de tendências de longo prazo
- Projeções de produção
- Identificação de oportunidades de melhoria
- Simulações de cenários
- Relatórios executivos

**Imagem:** Screenshot do StrategicAnalysis.tsx

---

## SLIDE 20: INTEGRAÇÃO OPC-UA

**Título:** Coleta Automática via OPC-UA

**Benefícios:**
- Sem digitação manual de dados
- Dados em tempo real (1-2 segundos)
- Compatível com todos os PLCs modernos
- Seguro e confiável
- Configuração simples

**Diagrama:**
```
PLC (Siemens/Rockwell/etc.)
    ↓
OPC-UA Server (Kepware/etc.)
    ↓
MIS-Core Coletor
    ↓
InfluxDB (Time-series)
    ↓
Dashboards React
```

**Imagem:** Diagrama de integração OPC-UA

---

## SLIDE 21: ESTADOS DA MÁQUINA

**Título:** 12 Estados Industriais Padronizados

**Tabela:**
| Estado | Descrição | Impacto OEE |
|--------|-----------|-------------|
| RUN | Produzindo | ✅ Produtivo |
| FAULT | Falha | ❌ Perda |
| WAIT_PREV | Aguardando anterior | ❌ Perda |
| BLOCK_NEXT | Bloqueado posterior | ❌ Perda |
| SETUP | Troca de SKU | ⚠️ Planejado |
| MANUTENCAO | Em manutenção | ⚠️ Planejado |
| ... | (outros 6 estados) | ... |

**Imagem:** Diagrama de máquina de estados

---

## SLIDE 22: SISTEMA DE SENSORES

**Título:** Sensores e Contagem Automática

**Tipos suportados:**
- INPUT_BOOL: Digitais (liga/desliga)
- INPUT_FLOAT: Analógicos (temperatura, pressão)
- COUNTER: Contadores de produção
- TIMER: Temporizadores
- SETPOINT: Valores de ajuste

**Imagem:** Diagrama de sensores em equipamento

---

## SLIDE 23: NODE-RED INTEGRATION

**Título:** Node-RED - Automação e Regras

**Funcionalidades:**
- Criação de fluxos de automação visual
- Regras de alerta personalizadas
- Integração com sistemas externos
- Cálculos customizados
- Envio de notificações (email, SMS, etc.)

**Imagem:** Screenshot do Node-RED com fluxo de exemplo

---

## SLIDE 24: BENEFÍCIOS MENSURÁVEIS

**Título:** Resultados Comprovados

**Métricas típicas:**
- ⬆️ **+15% OEE** em 6 meses
- ⬇️ **-30% Tempo** de análise de paradas
- ⬆️ **+20% Produtividade** por turno
- ⬇️ **-25% Custos** de manutenção reativa
- ⬆️ **100% Visibilidade** do chão de fábrica

**Imagem:** Gráfico de antes/depois ou dashboard de resultados

---

## SLIDE 25: PRÓXIMOS PASSOS

**Título:** Vamos Começar?

**Call to Action:**
1. **Diagnóstico**: Avaliação gratuita da sua operação
2. **Piloto**: Implementação em uma linha piloto
3. **Expansão**: Rollout para toda a fábrica
4. **Otimização**: Melhoria contínua com AI/ML

**Contato:**
- Email: contato@empresa.com
- Tel: (11) XXXX-XXXX
- Site: www.empresa.com/mis-core

**Imagem:** Ícones de contato e logo

---

## NOTAS PARA O MANUS AI

### Paleta de Cores:
- **Primária**: #1a1a2e (Azul escuro)
- **Secundária**: #16213e (Azul marinho)
- **Acento**: #4da3ff (Azul elétrico)
- **Sucesso**: #10b981 (Verde)
- **Erro**: #ef4444 (Vermelho)
- **Alerta**: #f59e0b (Amarelo)

### Tipografia:
- **Títulos**: Inter Bold ou similar sans-serif
- **Corpo**: Inter Regular
- **Código**: JetBrains Mono ou Consolas

### Estilo Visual:
- Design moderno e limpo
- Cards com sombra suave
- Ícones flat (Material Icons ou Lucide)
- Gráficos com gradientes sutis
- Modo escuro preferencial

### Imagens para Capturar:
1. Home.tsx - Tela inicial
2. LineDeepView.tsx - Dashboard de linha
3. LineAnalytics.tsx - Gráficos analíticos
4. MultiEquipmentTimeline.tsx - Timeline de estados
5. EquipamentoDetalhes.tsx - Detalhes do equipamento
6. GoldenState/DiagnosticsPanel.tsx - Diagnósticos
7. LossWaterfallChart.tsx - Gráfico cascata
8. ParetoChart.tsx - Pareto de paradas
9. CorrelationScatter.tsx - Scatter plot
10. FactoryManagementPanel.tsx - Gestão de fábricas
