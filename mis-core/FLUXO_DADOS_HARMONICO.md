# Fluxo de Dados Harmônico - MIS-Core

**Versão:** 2.0 - Restauração Completa  
**Data:** 28 de Novembro de 2025  
**Status:** ✅ PRONTO PARA PRODUÇÃO

---

## 1. Visão Geral da Arquitetura

O MIS-Core funciona com um fluxo de dados harmônico que conecta o CLP (Controlador Lógico Programável) até a interface do usuário no React. Este documento descreve como cada camada se comunica e como os dados fluem de forma simples e clara.

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLP / Máquina                            │
│                    (Dados Brutos em Tempo Real)                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OPC Server                                  │
│              (Lê dados do CLP via protocolo OPC-UA)             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Coletor (Aplicação)                         │
│         (Lê OPC, formata dados, envia para InfluxDB)            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      InfluxDB                                    │
│              (Armazena séries temporais em tempo real)          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
        ┌──────────────┐          ┌──────────────┐
        │ Flask API    │          │ Django API   │
        │ (Tempo Real) │          │(Configuração)│
        └──────┬───────┘          └──────┬───────┘
               │                         │
               └────────────┬────────────┘
                            ▼
                    ┌──────────────────┐
                    │  React Frontend  │
                    │   (Dashboard)    │
                    └──────────────────┘
```

---

## 2. Camada 1: CLP / OPC Server

### 2.1 O que é?
O CLP (Controlador Lógico Programável) é o "cérebro" da máquina. Ele controla todos os equipamentos e coleta dados em tempo real, como:
- Estado do equipamento (ligado/desligado)
- Velocidade de produção
- Temperatura e pressão
- Contagem de peças produzidas
- Erros e alarmes

### 2.2 Como funciona?
O OPC Server é um intermediário que lê os dados do CLP usando o protocolo OPC-UA (padrão industrial). O CLP não se comunica diretamente com a aplicação; sempre passa pelo OPC Server.

**Dados típicos do CLP:**
```
Equipamento: L01_ENCH_01
├── Estado: 1 (Produzindo)
├── Velocidade: 95 unid/min
├── Temperatura: 45°C
├── Pressão: 2.5 bar
├── Contagem de Entrada: 1000
├── Contagem de Saída: 950
└── Descarte: 50
```

---

## 3. Camada 2: Coletor (Aplicação)

### 3.1 O que é?
O Coletor é uma aplicação que:
1. Lê dados do OPC Server
2. Formata os dados
3. Envia para o InfluxDB

### 3.2 Fluxo de Dados

```
OPC Server
    │
    │ (Lê dados a cada 1-5 segundos)
    ▼
Coletor
    │
    ├─ Formata dados
    ├─ Adiciona timestamp
    ├─ Calcula métricas simples
    │
    ▼
InfluxDB (Escrita)
    └─ Armazena série temporal
```

### 3.3 Exemplo de Dados Formatados

```json
{
  "equipamento": "L01_ENCH_01",
  "timestamp": "2025-11-28T10:30:45Z",
  "medicoes": {
    "estado": 1,
    "velocidade_atual": 95,
    "temperatura": 45,
    "pressao": 2.5,
    "contagem_entrada": 1000,
    "contagem_saida": 950,
    "descarte": 50,
    "percentual_descarte": 5.0
  }
}
```

---

## 4. Camada 3: InfluxDB (Banco de Dados de Séries Temporais)

### 4.1 O que é?
InfluxDB é um banco de dados otimizado para armazenar dados que mudam ao longo do tempo (séries temporais). Ele é perfeito para dados de produção porque:
- Armazena muitos dados rapidamente
- Permite consultas rápidas por intervalo de tempo
- Compacta dados automaticamente

### 4.2 Estrutura de Dados

```
Database: efficiency
├── Measurement: equipamento_metrics
│   ├── Tags (indexados para busca rápida):
│   │   ├── equipamento: "L01_ENCH_01"
│   │   ├── linha: "L01"
│   │   └── tipo: "Enchedor"
│   │
│   └── Fields (valores numéricos):
│       ├── estado: 1
│       ├── velocidade_atual: 95
│       ├── temperatura: 45
│       ├── pressao: 2.5
│       ├── contagem_entrada: 1000
│       ├── contagem_saida: 950
│       └── descarte: 50
│
└── Measurement: linha_metrics
    ├── Tags:
    │   └── linha: "L01"
    │
    └── Fields:
        ├── oee: 85.5
        ├── toneladas_produzidas: 500
        └── vazao: 100
```

---

## 5. Camada 4: Flask API (Tempo Real)

### 5.1 O que é?
Flask é um framework Python leve que fornece endpoints HTTP para acessar dados em tempo real do InfluxDB.

### 5.2 Endpoints Principais

#### 5.2.1 Status em Tempo Real de um Equipamento
```
GET /api/realtime/status/{equipamento_codigo}

Exemplo:
GET /api/realtime/status/L01_ENCH_01

Resposta:
{
  "equipamento": "L01_ENCH_01",
  "status": "online",
  "timestamp": "2025-11-28T10:30:45Z",
  "medicoes": {
    "estado": 1,
    "velocidade_atual": 95,
    "temperatura": 45,
    "pressao": 2.5,
    "contagem_entrada": 1000,
    "contagem_saida": 950,
    "descarte": 50,
    "percentual_descarte": 5.0,
    "oee": 85.5
  }
}
```

#### 5.2.2 Histórico de um Equipamento
```
GET /api/realtime/history/{equipamento_codigo}?hours=24

Retorna dados dos últimos 24 horas
```

#### 5.2.3 Métricas Consolidadas de uma Linha
```
GET /api/realtime/linha/{linha_id}/metrics

Retorna OEE, tonelagem, vazão consolidados
```

### 5.3 Como Funciona

```
React Frontend
    │
    │ (Requisição HTTP)
    ▼
Flask API
    │
    ├─ Recebe requisição
    ├─ Consulta InfluxDB
    ├─ Formata resposta
    │
    ▼
JSON Response
    │
    ▼
React Frontend (Renderiza)
```

---

## 6. Camada 5: Django API (Configuração)

### 6.1 O que é?
Django é um framework Python robusto que fornece:
1. **Configuração** - Dados que não mudam frequentemente (equipamentos, linhas, sensores)
2. **Cálculos** - OEE, métricas consolidadas, projeções
3. **Persistência** - Dados salvos em banco de dados relacional (PostgreSQL/SQLite)

### 6.2 Endpoints Principais

#### 6.2.1 Listar Equipamentos
```
GET /api/equipamentos/

Resposta:
[
  {
    "id": 1,
    "codigo": "L01_ENCH_01",
    "nome": "Enchedor 01",
    "tipo": "Enchedor",
    "linha": 1,
    "linha_nome": "Linha 01",
    "velocidade_nominal": 100,
    "velocidade_maxima": 120,
    "meta_oee": 85,
    "temperatura_min": 40,
    "temperatura_max": 50,
    "pressao_min": 2.0,
    "pressao_max": 3.0
  }
]
```

#### 6.2.2 Status Completo dos Equipamentos
```
GET /api/full_equipment_status/

Retorna estado numérico (0-9), velocidade, OEE de TODOS os equipamentos
```

#### 6.2.3 Métricas Consolidadas da Linha
```
GET /api/metricas_linha_consolidadas/?linha_id=1

Resposta:
{
  "linha_id": 1,
  "linha_nome": "Linha 01",
  "oee": 85.5,
  "sku_codigo": "SKU001",
  "sku_descricao": "Suco Natural 1L",
  "ordem_producao": "OP-2025-001",
  "formato_gramas": 1000,
  "toneladas_produzidas_turno": 500,
  "toneladas_produzidas_op": 250,
  "meta_producao": 600,
  "vazao_real_ton_hora": 100,
  "disponibilidade": 95,
  "performance": 90,
  "qualidade": 99,
  "equipamentos_online": 4,
  "total_equipamentos": 4,
  "projecao": {
    "produzido": 250,
    "meta": 600,
    "projecao_realista": 500,
    "projecao_otimista": 550,
    "status": "em_dia"
  }
}
```

#### 6.2.4 Métricas Consolidadas da Fábrica
```
GET /api/metricas_fabrica_consolidadas/

Retorna métricas consolidadas de TODAS as linhas
```

### 6.3 Modelos Django

#### 6.3.1 Equipamento
```python
class Equipamento(models.Model):
    codigo = CharField(max_length=50)
    nome = CharField(max_length=100)
    tipo = CharField(max_length=50)
    linha = ForeignKey(LinhaProducao)
    velocidade_nominal = FloatField()
    velocidade_maxima = FloatField()
    meta_oee = FloatField()
    temperatura_min = FloatField(null=True)
    temperatura_max = FloatField(null=True)
    pressao_min = FloatField(null=True)
    pressao_max = FloatField(null=True)
```

#### 6.3.2 MetricaProducao
```python
class MetricaProducao(models.Model):
    equipamento = ForeignKey(Equipamento)
    linha = ForeignKey(LinhaProducao)
    ordem_producao = ForeignKey(OrdemProducao, null=True)
    
    # Componentes do OEE
    disponibilidade = FloatField()  # 0-100
    performance = FloatField()      # 0-100
    qualidade = FloatField()        # 0-100
    oee = FloatField()              # (Disp × Perf × Qual) / 10000
    
    # Produção
    toneladas_produzidas = FloatField()
    tempo_producao = FloatField()
    
    # Timestamp
    data_hora = DateTimeField(auto_now_add=True)
    turno = CharField(max_length=20)
```

---

## 7. Camada 6: React Frontend

### 7.1 O que é?
React é a interface que o usuário vê. Ela consome dados de DUAS fontes:
1. **Django** - Configuração e cálculos consolidados
2. **Flask** - Dados em tempo real do InfluxDB

### 7.2 Fluxo de Dados no Frontend

```
Home.tsx (Página Principal)
    │
    ├─ useEffect (ao carregar)
    │   └─ fetchEquipamentos()
    │       │
    │       ├─ Busca configuração do Django
    │       │   GET /api/equipamentos/
    │       │
    │       ├─ Busca status em tempo real do Flask
    │       │   GET /api/realtime/status/{equipamento}
    │       │
    │       └─ Busca métricas consolidadas do Django
    │           GET /api/metricas_fabrica_consolidadas/
    │
    ├─ Agrupa dados por linha
    │
    ├─ Renderiza LineOverview (visão consolidada da linha)
    │   └─ Exibe: OEE, SKU, Ordem de Produção, Tonelagem, Vazão
    │
    ├─ Renderiza EquipamentoCard[] (cards de equipamento)
    │   └─ Exibe: Estado (0-9), Velocidade, OEE, Contagem
    │
    └─ Renderiza MultiEquipmentTimeline (gráfico de timeline)
        └─ Exibe: Histórico de estados dos equipamentos
```

### 7.3 Atualização em Tempo Real

```
Home.tsx
    │
    └─ useEffect
        └─ setInterval(fetchEquipamentos, 5000)  // A cada 5 segundos
            │
            ├─ Busca dados novamente
            ├─ Atualiza estado (setLinhas)
            └─ React re-renderiza automaticamente
```

### 7.4 Componentes Principais

#### 7.4.1 LineOverview
Exibe visão consolidada de uma linha:
- OEE médio
- SKU e descrição do produto
- Ordem de produção
- Tonelagem produzida (turno e OP)
- Vazão (ton/hora)
- Equipamentos online/total
- Projeção de produção

#### 7.4.2 EquipamentoCard
Exibe informações de um equipamento:
- Nome e tipo
- Estado numérico (0-9) com cor
- Velocidade atual vs nominal
- OEE
- Contagem de entrada/saída
- Peças ruins

#### 7.4.3 MultiEquipmentTimeline
Exibe gráfico de timeline com histórico de estados de todos os equipamentos da linha

#### 7.4.4 FactoryDashboard
Exibe visão consolidada de TODAS as linhas com abas:
- **Visão Geral** - LineOverview de cada linha
- **Análise Estratégica** - Análise de perdas e oportunidades

---

## 8. Fluxo Completo: Do CLP ao Dashboard

### 8.1 Exemplo Prático: Mudança de Estado de um Equipamento

```
1. CLP detecta mudança de estado
   └─ Estado: 0 (Parado) → 1 (Produzindo)

2. OPC Server lê a mudança
   └─ Transmite ao Coletor

3. Coletor recebe e formata
   └─ Envia ao InfluxDB

4. InfluxDB armazena
   └─ timestamp: 2025-11-28T10:30:45Z
      estado: 1
      velocidade_atual: 95

5. Flask API lê do InfluxDB
   └─ Disponível em: /api/realtime/status/L01_ENCH_01

6. React Frontend faz requisição
   └─ GET /api/realtime/status/L01_ENCH_01

7. React recebe resposta
   └─ Atualiza estado (setLinhas)

8. React re-renderiza
   └─ EquipamentoCard mostra:
      - Estado: 1 (Produzindo) - cor verde
      - Velocidade: 95 unid/min
      - OEE: 85.5%

9. Usuário vê a mudança no dashboard
   └─ Tudo em tempo real!
```

**Latência Total:** ~2-5 segundos (dependendo do intervalo de leitura do CLP)

---

## 9. Dados que Fluem por Cada Camada

### 9.1 CLP → OPC Server
- Estado do equipamento (0-9)
- Velocidade de produção
- Temperatura e pressão
- Contadores (entrada, saída, descarte)
- Alarmes e erros

### 9.2 OPC Server → Coletor
- Mesmos dados do CLP
- Formatados em estrutura padrão

### 9.3 Coletor → InfluxDB
- Dados formatados com timestamp
- Métricas calculadas (percentual de descarte, etc)
- Estruturado em measurements e tags

### 9.4 InfluxDB → Flask API
- Dados de tempo real
- Histórico (últimas horas/dias)
- Agregações (média, máximo, mínimo)

### 9.5 Flask API → React Frontend
- JSON com status em tempo real
- Dados estruturados para renderização

### 9.6 Django API → React Frontend
- Configuração dos equipamentos
- Cálculos consolidados (OEE, tonelagem)
- Projeções e análises

---

## 10. Checklist de Funcionamento

Para garantir que o fluxo está funcionando corretamente:

### 10.1 CLP / OPC
- [ ] CLP está ligado e funcionando
- [ ] OPC Server está rodando
- [ ] Coletor consegue se conectar ao OPC

### 10.2 InfluxDB
- [ ] InfluxDB está rodando
- [ ] Dados estão sendo gravados (verificar via CLI ou UI)
- [ ] Banco de dados "efficiency" existe

### 10.3 Flask API
- [ ] Flask está rodando na porta 5000
- [ ] Endpoint `/api/realtime/status/{equipamento}` retorna dados
- [ ] Dados estão atualizados (timestamp recente)

### 10.4 Django API
- [ ] Django está rodando na porta 8000
- [ ] Endpoint `/api/equipamentos/` retorna lista
- [ ] Endpoint `/api/metricas_fabrica_consolidadas/` retorna métricas
- [ ] Banco de dados PostgreSQL/SQLite está acessível

### 10.5 React Frontend
- [ ] React está rodando na porta 5173
- [ ] Console do navegador não tem erros
- [ ] Dados aparecem nos cards
- [ ] Dados atualizam a cada 5 segundos
- [ ] Tema claro/escuro funciona

---

## 11. Troubleshooting

### 11.1 Dados não aparecem no frontend

**Verificar:**
1. Flask está rodando? `curl http://localhost:5000/api/realtime/status/L01_ENCH_01`
2. Django está rodando? `curl http://localhost:8000/api/equipamentos/`
3. InfluxDB tem dados? Verificar via `influx` CLI
4. Console do navegador tem erros? Abrir DevTools (F12)

### 11.2 Dados não atualizam

**Verificar:**
1. Intervalo de fetch está correto (5 segundos no Home.tsx)
2. CLP está enviando dados novos
3. Coletor está gravando no InfluxDB

### 11.3 OEE está zerado

**Verificar:**
1. MetricaProducao tem dados no Django
2. Disponibilidade, Performance e Qualidade estão calculados
3. Fórmula: OEE = (Disp × Perf × Qual) / 10000

---

## 12. Resumo

O fluxo de dados harmônico do MIS-Core é simples:

1. **CLP** produz dados brutos
2. **OPC Server** lê do CLP
3. **Coletor** formata e envia ao InfluxDB
4. **InfluxDB** armazena série temporal
5. **Flask** fornece acesso em tempo real
6. **Django** fornece configuração e cálculos
7. **React** consome de ambos e exibe ao usuário

Cada camada tem uma responsabilidade clara, e os dados fluem de forma harmônica e previsível.

---

**Desenvolvido por:** Manus AI  
**Última atualização:** 28 de Novembro de 2025  
**Versão:** 2.0 - Restauração Completa
