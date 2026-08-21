# 🏭 Sistema de Monitoramento Industrial - Projeto Completo

Sistema completo de monitoramento e análise de produção industrial com gestão de linhas, equipamentos e sensores.

## 📦 Estrutura do Projeto

```
projeto-monitoramento-industrial-completo/
├── frontend-react/          # Dashboard React (Porta 3000)
├── backend-django/          # API Django + Admin (Porta 8000)
├── backend-flask/           # API Flask Tempo Real (Porta 5000)
├── simulador/              # Simulador de Produção
├── docs/                   # Documentação
├── docker-compose.yml      # InfluxDB + PostgreSQL
├── .env.example            # Variáveis de ambiente (exemplo)
└── README.md              # Este arquivo
```

## 🚀 Início Rápido

### **Pré-requisitos**

- Python 3.11+
- Node.js 18+ e pnpm
- Docker e Docker Compose
- Git

### **1. Configuração Inicial**

```bash
# Copiar arquivo de ambiente
cp .env.example .env

# Editar .env se necessário (senhas, portas, etc.)
nano .env
```

### **2. Iniciar Containers Docker**

```bash
# Iniciar InfluxDB e PostgreSQL
docker compose up -d

# Verificar se estão rodando
docker ps
```

### **3. Configurar Backend Django**

```bash
cd backend-django

# Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Criar banco de dados
python manage.py makemigrations
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser
# Usuário: admin
# Email: admin@example.com
# Senha: admin123

# Popular dados iniciais
python manage.py shell << 'EOF'
from equipamentos.models import LinhaProducao, Equipamento, Sensor

# Criar Linha L01
linha, _ = LinhaProducao.objects.get_or_create(
    codigo='L01',
    defaults={
        'nome': 'Linha de Envase 01',
        'descricao': 'Linha completa de envase de bebidas',
        'localizacao': 'Galpão A',
        'velocidade_planejada': 100.0,
        'meta_producao_hora': 6000,
        'meta_producao_turno': 48000,
        'ativa': True
    }
)

# Criar Equipamentos
equipamentos = [
    {'nome': 'Enchedora_01', 'codigo': 'ENC-01', 'tipo': 'ENCHEDORA', 'ordem_na_linha': 1, 
     'velocidade_nominal': 100.0, 'velocidade_maxima': 120.0},
    {'nome': 'Balanca_01', 'codigo': 'BAL-01', 'tipo': 'BALANCA', 'ordem_na_linha': 2,
     'velocidade_nominal': 80.0, 'velocidade_maxima': 100.0},
    {'nome': 'Encaixotadora_01', 'codigo': 'ECX-01', 'tipo': 'ENCAIXOTADORA', 'ordem_na_linha': 3,
     'velocidade_nominal': 60.0, 'velocidade_maxima': 75.0},
    {'nome': 'Envolvedora_01', 'codigo': 'ENV-01', 'tipo': 'ENVOLVEDORA', 'ordem_na_linha': 4,
     'velocidade_nominal': 50.0, 'velocidade_maxima': 65.0},
]

for eq_data in equipamentos:
    Equipamento.objects.get_or_create(
        codigo=eq_data['codigo'],
        defaults={**eq_data, 'linha': linha}
    )

print("✓ Dados iniciais criados!")
EOF

# Iniciar servidor Django
python manage.py runserver 0.0.0.0:8000
```

**Deixe este terminal aberto!**

### **4. Configurar Backend Flask**

Abra um **novo terminal**:

```bash
cd backend-flask

# Usar o mesmo ambiente virtual ou criar novo
source ../backend-django/venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Iniciar Flask API
python app.py
```

**Deixe este terminal aberto!**

### **5. Iniciar Simulador**

Abra um **novo terminal**:

```bash
cd simulador

# Usar o mesmo ambiente virtual
source ../backend-django/venv/bin/activate

# Iniciar simulador
python simulador_producao.py
```

**Deixe este terminal aberto!**

### **6. Configurar Frontend React**

Abra um **novo terminal**:

```bash
cd frontend-react

# Instalar dependências
pnpm install

# Iniciar servidor de desenvolvimento
pnpm dev
```

**Deixe este terminal aberto!**

## 🌐 Acessar o Sistema

Após iniciar todos os serviços:

### **Dashboard React (Frontend)**
- URL: http://localhost:3000
- Visualização em tempo real dos equipamentos
- Auto-atualização a cada 5 segundos

### **Django Admin (Configuração)**
- URL: http://localhost:8000/admin
- Usuário: `admin`
- Senha: `admin123`
- Cadastro de linhas, equipamentos e sensores

### **Django API REST**
- Base URL: http://localhost:8000/api/
- Endpoints:
  - `GET /linhas/` - Listar linhas
  - `GET /equipamentos/` - Listar equipamentos
  - `GET /sensores/` - Listar sensores

### **Flask API (Tempo Real)**
- Base URL: http://localhost:5000/api/
- Endpoints:
  - `GET /health` - Health check
  - `GET /realtime/status/<equipamento>` - Status em tempo real
  - `POST /dados/inserir` - Inserir dados no InfluxDB

## 🧪 Testes

### **1. Testar Django Admin**

```bash
# Acessar http://localhost:8000/admin
# Login: admin / admin123
# Verificar se existem:
# - 1 Linha de Produção (L01)
# - 4 Equipamentos (Enchedora, Balança, Encaixotadora, Envolvedora)
```

### **2. Testar Flask API**

```bash
# Health check
curl http://localhost:5000/api/health

# Status de equipamento
curl http://localhost:5000/api/realtime/status/Enchedora_01 | python -m json.tool
```

### **3. Testar Dashboard React**

```bash
# Acessar http://localhost:3000
# Verificar se aparecem 4 cards de equipamentos
# Verificar se os dados atualizam a cada 5 segundos
# Testar botão de tema (dark/light)
```

### **4. Testar Simulador**

```bash
# Verificar logs do simulador
# Deve mostrar mensagens como:
# ✓ Dados enviados: Enchedora_01 - Produzindo
# ✓ Dados enviados: Balanca_01 - Produzindo
```

## 🛑 Parar o Sistema

Para parar todos os serviços:

1. Pressione `Ctrl+C` em cada terminal (Django, Flask, Simulador, React)
2. Parar containers Docker:
   ```bash
   docker compose down
   ```

## 📊 Fluxo de Dados

```
Simulador → Flask API → InfluxDB 1.8 (dados em tempo real)
                ↓
             Django (configurações + métricas agregadas)
                ↓
          React Dashboard (visualização)
```

## 🔧 Troubleshooting

### **Django não conecta no PostgreSQL**

```bash
# Verificar se PostgreSQL está rodando
docker ps | grep postgres

# Verificar logs
docker logs postgres-industrial

# Recriar container
docker compose down
docker compose up -d
```

### **Flask não conecta no InfluxDB**

```bash
# Verificar se InfluxDB está rodando
docker ps | grep influxdb

# Testar conexão
curl http://localhost:8086/ping

# Recriar container
docker compose down
docker compose up -d
```

### **React não mostra dados**

```bash
# Verificar se Flask está rodando
curl http://localhost:5000/api/health

# Verificar se simulador está enviando dados
# (ver logs do terminal do simulador)

# Verificar console do navegador (F12)
# Procurar por erros de CORS ou conexão
```

### **Simulador não envia dados**

```bash
# Verificar se Flask está rodando
curl http://localhost:5000/api/health

# Verificar se InfluxDB está acessível
curl http://localhost:8086/ping

# Reiniciar simulador
# Ctrl+C e executar novamente: python simulador_producao.py
```

## 📚 Documentação Adicional

- `docs/ARQUITETURA.md` - Arquitetura detalhada do sistema
- `docs/API.md` - Documentação completa das APIs
- `docs/MODELOS.md` - Modelos de dados Django
- `docs/DEPLOY.md` - Guia de deploy em produção

## 🎯 Funcionalidades Implementadas

✅ Django Admin completo para configuração
✅ Gestão de linhas de produção
✅ Gestão de equipamentos (4 tipos)
✅ Configuração de sensores de entrada/saída
✅ Cálculo automático de descarte
✅ Velocidade planejada vs real
✅ Cálculo de KPIs (Disponibilidade, Performance, Qualidade, OEE)
✅ Dashboard React em tempo real
✅ Auto-atualização a cada 5 segundos
✅ Tema dark/light
✅ Simulador de produção
✅ APIs REST completas

## 🚀 Próximos Passos

- [ ] Implementar Celery para agregação horária
- [ ] Adicionar autenticação JWT
- [ ] Criar relatórios em PDF
- [ ] Implementar alertas por email
- [ ] Dashboard de análise de descarte
- [ ] Integração com ERP

## 📞 Suporte

Para dúvidas ou problemas, consulte a documentação em `docs/` ou os logs dos serviços.

---

**Desenvolvido com:** React 19, Django 5.0, Flask 3.0, InfluxDB 1.8, PostgreSQL 15
