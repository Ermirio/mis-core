# Guia Completo de Execução - MIS-Core v2.0

**Status:** ✅ PRONTO PARA PRODUÇÃO  
**Data:** 28 de Novembro de 2025

---

## 1. Pré-requisitos

### 1.1 Softwares Necessários
- Python 3.11+
- Node.js 18+
- Git
- InfluxDB 2.x
- PostgreSQL 12+ (opcional, pode usar SQLite para desenvolvimento)

### 1.2 Portas Necessárias
- **8000** - Django API
- **5000** - Flask API (Tempo Real)
- **5173** - React Frontend
- **8086** - InfluxDB
- **5432** - PostgreSQL (se usar)

---

## 2. Estrutura do Projeto

```
mis-core/
├── backend-django/          # API de configuração e cálculos
│   ├── config/              # Configurações do Django
│   ├── equipamentos/        # App principal
│   ├── manage.py
│   ├── requirements.txt
│   └── db.sqlite3           # Banco de dados (desenvolvimento)
│
├── backend-flask/           # API de tempo real
│   ├── app.py
│   ├── requirements.txt
│   └── .env
│
├── frontend-react/          # Interface do usuário
│   └── client/
│       ├── src/
│       │   ├── pages/       # Páginas (Home, FactoryDashboard, etc)
│       │   ├── components/  # Componentes reutilizáveis
│       │   └── services/    # Serviços de API
│       ├── package.json
│       └── vite.config.ts
│
└── docs/                    # Documentação
    └── FLUXO_DADOS_HARMONICO.md
```

---

## 3. Instalação e Configuração

### 3.1 Clonar o Repositório

```bash
# Clonar o repositório
git clone https://github.com/Ermirio/mis-core.git
cd mis-core

# Mudar para a branch dev_manus
git checkout dev_manus
git pull origin dev_manus
```

### 3.2 Configurar Backend Django

```bash
# Entrar na pasta do Django
cd backend-django

# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
# No Windows:
venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Aplicar migrações
python manage.py migrate

# Criar superusuário (opcional, para Django Admin)
python manage.py createsuperuser

# Iniciar servidor Django
python manage.py runserver
```

**Saída esperada:**
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

### 3.3 Configurar Backend Flask

```bash
# Em OUTRO terminal, entrar na pasta do Flask
cd backend-flask

# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
# No Windows:
venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Criar arquivo .env (se necessário)
# Adicionar variáveis de ambiente:
# INFLUXDB_URL=http://localhost:8086
# INFLUXDB_TOKEN=seu_token
# INFLUXDB_ORG=sua_org
# INFLUXDB_BUCKET=efficiency

# Iniciar servidor Flask
python app.py
```

**Saída esperada:**
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

### 3.4 Configurar Frontend React

```bash
# Em OUTRO terminal, entrar na pasta do React
cd frontend-react/client

# Instalar dependências
npm install

# Criar arquivo .env.local (se necessário)
# Adicionar variáveis:
# VITE_DJANGO_API_URL=http://127.0.0.1:8000/api
# VITE_FLASK_API_URL=http://127.0.0.1:5000/api

# Iniciar servidor de desenvolvimento
npm run dev
```

**Saída esperada:**
```
  VITE v4.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

---

## 4. Verificar se Tudo Está Funcionando

### 4.1 Verificar Django

```bash
# Em um novo terminal, testar endpoint de equipamentos
curl http://localhost:8000/api/equipamentos/

# Resposta esperada:
# {
#   "count": 4,
#   "next": null,
#   "previous": null,
#   "results": [...]
# }
```

### 4.2 Verificar Flask

```bash
# Testar endpoint de status em tempo real
curl http://localhost:5000/api/realtime/status/L01_ENCH_01

# Resposta esperada:
# {
#   "equipamento": "L01_ENCH_01",
#   "status": "online",
#   "timestamp": "2025-11-28T10:30:45Z",
#   "medicoes": {...}
# }
```

### 4.3 Verificar React

Abrir navegador e acessar: `http://localhost:5173`

**Você deve ver:**
- ✅ Header com título "MIS-Core"
- ✅ Cards de equipamentos com dados
- ✅ Visão consolidada da linha
- ✅ Timeline de equipamentos

---

## 5. Estrutura de Dados Esperada

### 5.1 Django Admin

Acessar `http://localhost:8000/admin` com credenciais do superusuário.

**Criar dados de teste:**

1. **Linhas de Produção**
   - Nome: "Linha 01"
   - Código: "L01"

2. **Equipamentos**
   - Nome: "Enchedor 01"
   - Código: "L01_ENCH_01"
   - Tipo: "Enchedor"
   - Linha: "Linha 01"
   - Velocidade Nominal: 100
   - Velocidade Máxima: 120
   - Meta OEE: 85

3. **Produtos**
   - Código: "SKU001"
   - Descrição: "Suco Natural 1L"
   - Formato: 1000g

4. **Ordens de Produção**
   - Número: "OP-2025-001"
   - Produto: "SKU001"
   - Linha: "Linha 01"
   - Meta: 600 toneladas

### 5.2 InfluxDB

Se tiver dados no InfluxDB, eles aparecerão automaticamente no Flask e depois no React.

**Estrutura esperada:**
```
Database: efficiency
├── Measurement: equipamento_metrics
│   └── Tags: equipamento, linha, tipo
│       Fields: estado, velocidade_atual, temperatura, pressao, etc
│
└── Measurement: linha_metrics
    └── Tags: linha
        Fields: oee, toneladas_produzidas, vazao
```

---

## 6. Fluxo de Dados Esperado

### 6.1 Ao Acessar a Home

```
1. React carrega
   └─ useEffect dispara fetchEquipamentos()

2. Django é consultado
   GET /api/equipamentos/
   └─ Retorna lista de equipamentos configurados

3. Flask é consultado para cada equipamento
   GET /api/realtime/status/{equipamento}
   └─ Retorna dados em tempo real do InfluxDB

4. Django é consultado novamente
   GET /api/metricas_fabrica_consolidadas/
   └─ Retorna métricas consolidadas

5. React agrupa dados por linha
   └─ Cria estrutura: LinhaAgrupada[]

6. React renderiza
   ├─ LineOverview (visão consolidada)
   ├─ EquipamentoCard[] (cards de equipamento)
   └─ MultiEquipmentTimeline (gráfico)

7. A cada 5 segundos, o processo se repete
   └─ Dados são atualizados em tempo real
```

---

## 7. Páginas Disponíveis

### 7.1 Home (`/`)
- **O que é:** Dashboard principal com visão de todas as linhas
- **Dados exibidos:**
  - OEE de cada linha
  - SKU e descrição do produto
  - Ordem de produção
  - Tonelagem produzida
  - Vazão
  - Cards de equipamentos
  - Timeline de estados

### 7.2 Factory Dashboard (`/factory-dashboard`)
- **O que é:** Visão consolidada de TODAS as linhas
- **Abas:**
  - **Visão Geral** - LineOverview de cada linha
  - **Análise Estratégica** - Análise de perdas e oportunidades

### 7.3 Factory Management (`/factory-management`)
- **O que é:** Gerenciamento de iniciativas estratégicas
- **Funcionalidades:**
  - Criar nova iniciativa
  - Editar iniciativa
  - Visualizar status
  - Filtrar por status

### 7.4 Linha Detalhes (`/linha/:id`)
- **O que é:** Visão detalhada de uma linha específica
- **Dados exibidos:**
  - Todos os equipamentos da linha
  - Histórico de produção
  - Análise de perdas

### 7.5 Equipamento Detalhes (`/equipamento/:id`)
- **O que é:** Visão detalhada de um equipamento
- **Dados exibidos:**
  - Estado atual
  - Velocidade
  - OEE
  - Histórico de estados
  - Gráficos de performance

---

## 8. Variáveis de Ambiente

### 8.1 Django (`.env` ou `settings.py`)

```python
# Banco de dados
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',  # ou postgresql
        'NAME': 'db.sqlite3',
    }
}

# CORS (para React acessar)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
]

# InfluxDB (se usar)
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "seu_token"
INFLUXDB_ORG = "sua_org"
INFLUXDB_BUCKET = "efficiency"
```

### 8.2 Flask (`.env`)

```
FLASK_ENV=development
FLASK_DEBUG=1

INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=seu_token
INFLUXDB_ORG=sua_org
INFLUXDB_BUCKET=efficiency
```

### 8.3 React (`.env.local`)

```
VITE_DJANGO_API_URL=http://127.0.0.1:8000/api
VITE_FLASK_API_URL=http://127.0.0.1:5000/api
```

---

## 9. Troubleshooting

### 9.1 Erro: "Cannot GET /api/equipamentos/"

**Causa:** Django não está rodando ou CORS não está configurado

**Solução:**
```bash
# Verificar se Django está rodando
curl http://localhost:8000/api/equipamentos/

# Se não funcionar, iniciar Django
cd backend-django
python manage.py runserver
```

### 9.2 Erro: "Cannot GET /api/realtime/status/..."

**Causa:** Flask não está rodando ou InfluxDB não tem dados

**Solução:**
```bash
# Verificar se Flask está rodando
curl http://localhost:5000/api/realtime/status/L01_ENCH_01

# Se não funcionar, iniciar Flask
cd backend-flask
python app.py

# Verificar se InfluxDB tem dados
influx query 'from(bucket:"efficiency") |> range(start: -1h)'
```

### 9.3 Erro: "CORS policy: No 'Access-Control-Allow-Origin' header"

**Causa:** Django CORS não está configurado

**Solução:**
```bash
# Instalar django-cors-headers
pip install django-cors-headers

# Adicionar em settings.py
INSTALLED_APPS = [
    ...
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    ...
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]
```

### 9.4 Erro: "No such table: equipamentos_equipamento"

**Causa:** Migrações não foram aplicadas

**Solução:**
```bash
cd backend-django
python manage.py migrate
```

### 9.5 React não carrega dados

**Causa:** APIs não estão respondendo ou URLs estão erradas

**Solução:**
1. Abrir DevTools (F12) no navegador
2. Ir para aba "Network"
3. Atualizar página
4. Verificar requisições HTTP
5. Checar se status é 200 OK
6. Se não, verificar console para erros

---

## 10. Comandos Úteis

### 10.1 Django

```bash
# Criar superusuário
python manage.py createsuperuser

# Criar migração
python manage.py makemigrations

# Aplicar migração
python manage.py migrate

# Shell interativo
python manage.py shell

# Limpar banco de dados
python manage.py flush

# Criar dados de teste
python manage.py loaddata fixture_name
```

### 10.2 Flask

```bash
# Rodar em modo debug
FLASK_ENV=development FLASK_DEBUG=1 python app.py

# Rodar em porta específica
python app.py --port 5001
```

### 10.3 React

```bash
# Build para produção
npm run build

# Preview do build
npm run preview

# Lint (verificar erros)
npm run lint

# Format (formatar código)
npm run format
```

### 10.4 InfluxDB

```bash
# Entrar no CLI
influx

# Listar buckets
buckets

# Listar dados
from(bucket:"efficiency") |> range(start: -1h)

# Deletar dados
delete(predicate: fn: (r) => r._measurement == "equipamento_metrics")
```

---

## 11. Checklist de Deployment

Antes de colocar em produção:

- [ ] Todos os 3 serviços estão rodando (Django, Flask, React)
- [ ] Dados aparecem no dashboard
- [ ] Dados atualizam a cada 5 segundos
- [ ] Tema claro/escuro funciona
- [ ] Botão de atualizar funciona
- [ ] Nenhum erro no console do navegador
- [ ] Nenhum erro nos logs do Django/Flask
- [ ] Banco de dados está backup
- [ ] Variáveis de ambiente estão configuradas
- [ ] CORS está configurado corretamente
- [ ] InfluxDB está rodando e com dados
- [ ] PostgreSQL está rodando (se usar em produção)

---

## 12. Próximos Passos

### 12.1 Melhorias Futuras
- [ ] Autenticação de usuários
- [ ] Permissões por linha
- [ ] Alertas e notificações
- [ ] Relatórios PDF
- [ ] Integração com ERP
- [ ] Mobile app

### 12.2 Otimizações
- [ ] Cache de dados
- [ ] Compressão de imagens
- [ ] Lazy loading de componentes
- [ ] Índices no banco de dados

---

## 13. Suporte

Se encontrar problemas:

1. Verificar logs do Django: `python manage.py runserver` (mostra erros)
2. Verificar logs do Flask: Saída do terminal
3. Verificar console do navegador: F12 → Console
4. Verificar InfluxDB: `influx query`
5. Verificar conectividade: `curl` para testar endpoints

---

**Desenvolvido por:** Manus AI  
**Última atualização:** 28 de Novembro de 2025  
**Versão:** 2.0 - Restauração Completa
