# Sistema MIS - Monitoramento Industrial com OEE Real

## 📋 Visão Geral

Sistema completo de monitoramento industrial (MIS/MES) com cálculo real de OEE baseado em eventos de estado, turnos de produção e calendário programado. Arquitetura distribuída com separação clara de responsabilidades.

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend React (HMI)                      │
│  - Home.tsx (visão geral)                                    │
│  - LineOverview.tsx (resumo da linha)                        │
│  - LinhaDetalhes.tsx (detalhes da linha)                     │
│  - EquipamentoDetalhes.tsx (detalhes do equipamento)         │
│  - Design ISA 101                                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
┌──────────────┐      ┌──────────────┐
│    Flask     │      │   Django     │
│ (Real-time)  │◄────►│  (Config +   │
│              │      │   Métricas)  │
└──────┬───────┘      └──────┬───────┘
       │                     │
       │ InfluxDB            │ MySQL
       ▼                     ▼
┌─────────────┐      ┌──────────────┐
│  InfluxDB   │      │    MySQL     │
│ (Séries     │      │ (Config +    │
│  Temporais) │      │  Agregados)  │
└─────────────┘      └──────────────┘
       ▲                     ▲
       │                     │
       └──────────┬──────────┘
                  │
          ┌───────┴────────┐
          │  Coletor OPC   │
          │  - Lê tags     │
          │  - Detecta     │
          │    estados     │
          └────────────────┘
```

### Componentes

1. **Django (O Cérebro)**
   - Configuração centralizada (linhas, equipamentos, tags OPC, turnos, calendário)
   - Armazenamento de métricas agregadas
   - Gestão de eventos de estado
   - Admin interface para configuração

2. **Coletor OPC UA (O Trabalhador)**
   - Serviço standalone Python
   - Lê tags OPC UA configurados no Django
   - Detecta mudanças de estado automaticamente
   - Envia dados para Flask (tempo real) e Django (eventos)

3. **Flask (API Tempo Real)**
   - Broker de dados de alta velocidade
   - Armazena séries temporais no InfluxDB
   - Agrega métricas horárias com cálculo real de OEE
   - Envia agregados para Django

4. **React (HMI)**
   - Interface seguindo princípios ISA 101
   - Visualização em tempo real
   - Navegação hierárquica (Home → Linha → Equipamento)
   - Gráficos e KPIs

## 🎯 Cálculo Real de OEE

### Fórmula

```
OEE = (Disponibilidade × Performance × Qualidade) / 10000
```

### Componentes

#### Disponibilidade (A)
```
A = (Tempo Produção / Tempo Disponível) × 100

Onde:
- Tempo Disponível = Tempo Programado - Tempo Não Programado
- Tempo Produção = Soma dos tempos em estado RUN
- Tempo Não Programado = Soma dos tempos em MANUTENCAO + TESTE_PROJ
```

#### Performance (P)
```
P = (Produção Real / Produção Teórica) × 100

Onde:
- Produção Real = Contagem Saída
- Produção Teórica = Velocidade Planejada × Tempo Produção
```

#### Qualidade (Q)
```
Q = (Produção Saída / Produção Entrada) × 100

Onde:
- Produção Saída = Contagem Saída
- Produção Entrada = Contagem Entrada
```

### Estados Industriais

O sistema rastreia 10 estados diferentes:

| Estado | Código | Categoria | Impacto no OEE |
|--------|--------|-----------|----------------|
| Produzindo | RUN | Produção | Tempo Produção |
| Aguardando Anterior | WAIT_PREV | Parada | Tempo Parada |
| Bloqueado Próximo | BLOCK_NEXT | Parada | Tempo Parada |
| Falha | FAULT | Parada | Tempo Parada |
| Setup | SETUP | Setup | Tempo Setup |
| Teste de Projeto | TESTE_PROJ | Não Programado | Tempo Não Programado |
| Aguardando Manutenção | AGUARD_MNT | Parada | Tempo Parada |
| Manutenção | MANUTENCAO | Não Programado | Tempo Não Programado |
| Falta de Material | FALTA_MAT | Parada | Tempo Parada |
| Outro | OUTRO | - | - |

## 📊 Fluxo de Dados

### 1. Configuração (Admin Django)

```
Admin configura:
├── Linhas de Produção
├── Equipamentos
├── Conexões OPC
├── Tags de Coleta (Node IDs)
├── Turnos
└── Calendário de Produção
```

### 2. Coleta (Coletor OPC)

```
Coletor (a cada 2s):
├── Busca configuração do Django
├── Conecta aos servidores OPC UA
├── Lê tags configuradas
├── Detecta mudanças de estado
├── Envia dados para Flask (InfluxDB)
└── Envia eventos de estado para Django
```

### 3. Agregação (Flask)

```
Flask (a cada hora):
├── Consulta InfluxDB (contadores, velocidades)
├── Consulta Django (eventos de estado)
├── Calcula tempos por categoria
├── Calcula KPIs reais (A, P, Q, OEE)
└── Envia métricas consolidadas para Django
```

### 4. Visualização (React)

```
React (tempo real):
├── Busca configuração do Django
├── Busca dados tempo real do Flask
├── Busca métricas agregadas do Django
├── Combina e exibe
└── Atualiza automaticamente
```

## 🚀 Instalação e Configuração

### Pré-requisitos

- Python 3.9+
- Node.js 18+
- MySQL 8.0+
- InfluxDB 1.8+
- Servidor OPC UA (opcional para testes)

### 1. Django (Backend de Configuração)

```bash
cd django_app

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instalar dependências
pip install django djangorestframework django-cors-headers mysqlclient python-decouple

# Configurar .env
cat > .env << EOF
DEBUG=True
SECRET_KEY=sua-chave-secreta-aqui
DATABASE_NAME=mis_db
DATABASE_USER=root
DATABASE_PASSWORD=sua-senha
DATABASE_HOST=127.0.0.1
DATABASE_PORT=3306
EOF

# Criar banco de dados
mysql -u root -p -e "CREATE DATABASE mis_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Aplicar migrações
python manage.py makemigrations
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser

# Iniciar servidor
python manage.py runserver 0.0.0.0:8000
```

### 2. Flask (API Tempo Real)

```bash
cd flask_app

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate

# Instalar dependências
pip install flask flask-cors influxdb python-decouple requests apscheduler

# Configurar .env
cat > .env << EOF
INFLUXDB_HOST=127.0.0.1
INFLUXDB_PORT=8086
INFLUXDB_DATABASE=industrial_db
INFLUXDB_USER=
INFLUXDB_USER_PASSWORD=
DJANGO_API_URL=http://127.0.0.1:8000/api
AGREGACAO_HABILITADA=True
EOF

# Iniciar InfluxDB (se necessário)
# influxd

# Iniciar servidor
python app.py
```

### 3. Coletor OPC UA

```bash
cd coletor

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate

# Instalar dependências
pip install asyncua requests python-decouple

# Configurar .env
cat > .env << EOF
DJANGO_API_URL=http://127.0.0.1:8000/api
FLASK_API_URL=http://127.0.0.1:5000/api
INTERVALO_COLETA=2
TIMEOUT_REQUEST=10
EOF

# Iniciar coletor
python coletor.py
```

### 4. React (Frontend)

```bash
cd react_app

# Instalar dependências
npm install

# Configurar .env
cat > .env << EOF
VITE_DJANGO_API_URL=http://localhost:8000/api
VITE_FLASK_API_URL=http://localhost:5000/api
EOF

# Iniciar desenvolvimento
npm run dev

# Build para produção
npm run build
```

## 📝 Configuração Inicial

### 1. Acessar Django Admin

```
URL: http://localhost:8000/admin
```

### 2. Criar Turnos

```
Turnos → Adicionar Turno de Produção

Exemplo:
- Nome: Turno A
- Código: A
- Hora Início: 06:00
- Hora Fim: 14:00
- Duração: 8 horas
- Ativo: ✓
```

### 3. Criar Linha de Produção

```
Linhas de Produção → Adicionar Linha

Exemplo:
- Código: L01
- Nome: Linha 1 - Envase
- Velocidade Planejada: 100 un/min
- Meta Produção/Hora: 6000
- Meta Produção/Turno: 48000
- Meta OEE: 85%
- Ativa: ✓
```

### 4. Criar Conexão OPC

```
Conexões OPC → Adicionar Conexão

Exemplo:
- Nome: PLC Linha 1
- URL: opc.tcp://192.168.1.10:4840
- Namespace Prefix: ns=2;s=
- Timeout: 5s
- Ativa: ✓
```

### 5. Criar Equipamentos

```
Equipamentos → Adicionar Equipamento

Exemplo:
- Linha: L01
- Nome: Enchedora 01
- Código: L01_ENCH_01
- Tipo: ENCHEDORA
- Ordem na Linha: 1
- Velocidade Nominal: 100 un/min
- Meta OEE: 85%
- Status: ATIVO
```

### 6. Adicionar Tags de Coleta

```
No equipamento criado, adicionar tags inline:

Tag 1:
- Conexão: PLC Linha 1
- Nome Métrica: contagem_entrada
- Node ID: ns=2;s=Linha1.Enchedora.ContagemEntrada
- Tipo: INT
- Ativa: ✓

Tag 2:
- Conexão: PLC Linha 1
- Nome Métrica: contagem_saida
- Node ID: ns=2;s=Linha1.Enchedora.ContagemSaida
- Tipo: INT
- Ativa: ✓

Tag 3:
- Conexão: PLC Linha 1
- Nome Métrica: velocidade_atual
- Node ID: ns=2;s=Linha1.Enchedora.Velocidade
- Tipo: FLOAT
- Unidade: un/min
- Ativa: ✓

Tag 4:
- Conexão: PLC Linha 1
- Nome Métrica: estado
- Node ID: ns=2;s=Linha1.Enchedora.Estado
- Tipo: INT
- Ativa: ✓

Tag 5:
- Conexão: PLC Linha 1
- Nome Métrica: temperatura
- Node ID: ns=2;s=Linha1.Enchedora.Temperatura
- Tipo: FLOAT
- Unidade: °C
- Ativa: ✓
```

### 7. Configurar Calendário

```
Calendário de Produção → Adicionar

Exemplo:
- Data: 2024-01-15
- Linha: L01
- Turno: Turno A
- Programado: ✓
- Meta Produção Turno: 48000
```

## 🔍 Endpoints da API

### Django

```
GET  /api/linhas/                      - Lista linhas
GET  /api/linhas/{id}/                 - Detalhes da linha
GET  /api/equipamentos/                - Lista equipamentos
GET  /api/equipamentos/{id}/           - Detalhes do equipamento
GET  /api/metricas/                    - Lista métricas (filtros: linha_id, equipamento_id, periodo, data_inicio, data_fim)
GET  /api/eventos-estado/              - Lista eventos de estado
GET  /api/turnos/                      - Lista turnos
GET  /api/calendario/                  - Lista calendário

# Endpoints especiais
GET  /api/configuracao_coletor/        - Configuração completa para o Coletor
POST /api/eventos_estado/              - Registra evento de mudança de estado
POST /api/metricas_consolidadas/       - Recebe métricas agregadas do Flask
```

### Flask

```
GET  /api/health                                - Health check
POST /api/dados/inserir                         - Insere dados no InfluxDB
GET  /api/realtime/status/{equipamento_codigo}  - Status em tempo real
GET  /api/realtime/variaveis/{equipamento_codigo} - Variáveis de processo (últimos 2 min)
GET  /api/historico/{equipamento_codigo}        - Histórico agregado
```

## 🧪 Testes

### Teste de Integração Completa

```bash
# 1. Verificar Django
curl http://localhost:8000/api/linhas/

# 2. Verificar Flask
curl http://localhost:5000/api/health

# 3. Verificar configuração do Coletor
curl http://localhost:8000/api/configuracao_coletor/

# 4. Simular inserção de dados
curl -X POST http://localhost:5000/api/dados/inserir \
  -H "Content-Type: application/json" \
  -d '{
    "equipamento_codigo": "L01_ENCH_01",
    "linha_codigo": "L01",
    "medicoes": {
      "contagem_entrada": 1000,
      "contagem_saida": 995,
      "velocidade_atual": 98.5,
      "estado": 1,
      "temperatura": 25.3
    }
  }'

# 5. Simular evento de estado
curl -X POST http://localhost:8000/api/eventos_estado/ \
  -H "Content-Type: application/json" \
  -d '{
    "equipamento_codigo": "L01_ENCH_01",
    "estado": "RUN",
    "timestamp": "2024-01-15T10:00:00Z",
    "origem": "OPC"
  }'

# 6. Verificar dados em tempo real
curl http://localhost:5000/api/realtime/status/L01_ENCH_01

# 7. Verificar eventos de estado
curl "http://localhost:8000/api/eventos-estado/?equipamento_codigo=L01_ENCH_01"
```

## 📈 Monitoramento

### Logs

```bash
# Django
tail -f django_app/logs/django.log

# Flask
tail -f flask_app/logs/flask.log

# Coletor
tail -f coletor/coletor.log
```

### Métricas

- **Django Admin**: Visualizar métricas agregadas e eventos
- **InfluxDB**: Consultar séries temporais
- **React**: Visualização em tempo real

## 🔧 Troubleshooting

### Coletor não conecta ao OPC

```bash
# Verificar conectividade
ping 192.168.1.10

# Testar porta OPC
telnet 192.168.1.10 4840

# Verificar logs
tail -f coletor/coletor.log
```

### Flask não agrega métricas

```bash
# Verificar se agregação está habilitada
grep AGREGACAO_HABILITADA flask_app/.env

# Verificar logs do scheduler
tail -f flask_app/logs/flask.log | grep "agregação"

# Testar manualmente
python -c "from app import agregar_metricas_hora; agregar_metricas_hora()"
```

### React não exibe dados

```bash
# Verificar variáveis de ambiente
cat react_app/.env

# Verificar console do navegador
# F12 → Console → Procurar erros de CORS ou 404

# Verificar se APIs estão respondendo
curl http://localhost:8000/api/linhas/
curl http://localhost:5000/api/health
```

## 📚 Referências

- [ISA-101: Human Machine Interfaces](https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa101)
- [OEE Foundation](https://www.oee.com/)
- [OPC UA Specification](https://opcfoundation.org/about/opc-technologies/opc-ua/)
- [InfluxDB Documentation](https://docs.influxdata.com/influxdb/v1.8/)

## 📄 Licença

Propriedade do Sistema MIS. Todos os direitos reservados.

## 👥 Suporte

Para suporte, entre em contato com a equipe de TI Industrial.
