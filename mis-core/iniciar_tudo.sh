#!/bin/bash

echo "======================================================================"
echo "🏭 SISTEMA DE MONITORAMENTO INDUSTRIAL - INICIALIZAÇÃO RÁPIDA"
echo "======================================================================"
echo ""

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar se está no diretório correto
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Erro: Execute este script no diretório raiz do projeto${NC}"
    exit 1
fi

# 1. Iniciar Docker
echo -e "${YELLOW}[1/6]${NC} Iniciando containers Docker..."
docker compose up -d
sleep 5
echo -e "${GREEN}✓${NC} Containers iniciados"
echo ""

# 2. Verificar containers
echo -e "${YELLOW}[2/6]${NC} Verificando containers..."
docker ps --format "table {{.Names}}\t{{.Status}}"
echo ""

# 3. Configurar Django
echo -e "${YELLOW}[3/6]${NC} Configurando Django..."
cd backend-django

# Criar venv se não existir
if [ ! -d "venv" ]; then
    echo "  → Criando ambiente virtual..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

# Aplicar migrações
echo "  → Aplicando migrações..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# Criar superusuário se não existir
echo "  → Criando superusuário..."
python manage.py shell << 'PYEOF'
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print("    ✓ Superusuário criado")
else:
    print("    ○ Superusuário já existe")
PYEOF

# Popular dados
echo "  → Populando dados iniciais..."
python manage.py shell << 'PYEOF'
from equipamentos.models import LinhaProducao, Equipamento

linha, created = LinhaProducao.objects.get_or_create(
    codigo='L01',
    defaults={
        'nome': 'Linha de Envase 01',
        'velocidade_planejada': 100.0,
        'meta_producao_hora': 6000,
        'ativa': True
    }
)

equipamentos = [
    {'nome': 'Enchedora_01', 'codigo': 'ENC-01', 'tipo': 'ENCHEDORA', 'ordem_na_linha': 1, 'velocidade_nominal': 100.0},
    {'nome': 'Balanca_01', 'codigo': 'BAL-01', 'tipo': 'BALANCA', 'ordem_na_linha': 2, 'velocidade_nominal': 80.0},
    {'nome': 'Encaixotadora_01', 'codigo': 'ECX-01', 'tipo': 'ENCAIXOTADORA', 'ordem_na_linha': 3, 'velocidade_nominal': 60.0},
    {'nome': 'Envolvedora_01', 'codigo': 'ENV-01', 'tipo': 'ENVOLVEDORA', 'ordem_na_linha': 4, 'velocidade_nominal': 50.0},
]

for eq_data in equipamentos:
    Equipamento.objects.get_or_create(codigo=eq_data['codigo'], defaults={**eq_data, 'linha': linha})

print("✓ Dados iniciais criados")
PYEOF

echo -e "${GREEN}✓${NC} Django configurado"
cd ..
echo ""

# 4. Instalar dependências React
echo -e "${YELLOW}[4/6]${NC} Instalando dependências React..."
cd frontend-react
if [ ! -d "node_modules" ]; then
    pnpm install --silent
fi
cd ..
echo -e "${GREEN}✓${NC} Dependências React instaladas"
echo ""

# 5. Criar scripts de inicialização individual
echo -e "${YELLOW}[5/6]${NC} Criando scripts de inicialização..."

cat > start_django.sh << 'EOF'
#!/bin/bash
cd backend-django
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
EOF
chmod +x start_django.sh

cat > start_flask.sh << 'EOF'
#!/bin/bash
cd backend-flask
source ../backend-django/venv/bin/activate
python app.py
EOF
chmod +x start_flask.sh

cat > start_simulador.sh << 'EOF'
#!/bin/bash
cd simulador
source ../backend-django/venv/bin/activate
python simulador_producao.py
EOF
chmod +x start_simulador.sh

cat > start_react.sh << 'EOF'
#!/bin/bash
cd frontend-react
pnpm dev
EOF
chmod +x start_react.sh

echo -e "${GREEN}✓${NC} Scripts criados"
echo ""

# 6. Resumo
echo -e "${YELLOW}[6/6]${NC} Configuração concluída!"
echo ""
echo "======================================================================"
echo "📊 PRÓXIMOS PASSOS"
echo "======================================================================"
echo ""
echo "Abra 4 terminais e execute:"
echo ""
echo "  ${GREEN}Terminal 1:${NC} ./start_django.sh      # Django (porta 8000)"
echo "  ${GREEN}Terminal 2:${NC} ./start_flask.sh       # Flask (porta 5000)"
echo "  ${GREEN}Terminal 3:${NC} ./start_simulador.sh   # Simulador"
echo "  ${GREEN}Terminal 4:${NC} ./start_react.sh       # React (porta 3000)"
echo ""
echo "======================================================================"
echo "🌐 ACESSAR SISTEMA"
echo "======================================================================"
echo ""
echo "  Dashboard React:  http://localhost:3000"
echo "  Django Admin:     http://localhost:8000/admin (admin/admin123)"
echo "  Flask API:        http://localhost:5000/api/health"
echo ""
echo "======================================================================"
echo ""
echo -e "${GREEN}✓ Sistema pronto para uso!${NC}"
echo ""
