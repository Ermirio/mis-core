# 🏭 MIS-Core - Sistema de Monitoramento Industrial

## 🚀 Deploy com Docker (Recomendado)

Este guia apresenta o método **mais simples e rápido** para executar o MIS-Core usando Docker e Docker Compose.

### ✅ Pré-requisitos

- **Docker** 20.10 ou superior
- **Docker Compose** 2.0 ou superior
- **8GB RAM** mínimo recomendado
- **10GB** de espaço em disco

### 📦 Instalação Rápida

#### 1. Clone o repositório

```bash
git clone https://github.com/Ermirio/mis-core.git
cd mis-core
git checkout manus-docker
```

#### 2. Configure as variáveis de ambiente

O arquivo `.env` já está pré-configurado com valores padrão. **Para produção**, edite o arquivo e altere:

- Todas as senhas
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=False`
- URLs das APIs (se necessário)

```bash
# Opcional: editar configurações
nano .env
```

#### 3. Execute o deploy automatizado

```bash
./scripts/deploy.sh
```

O script irá:
- Construir todas as imagens Docker
- Iniciar todos os serviços
- Aplicar migrações do banco de dados
- Criar o superusuário automaticamente
- Verificar a saúde de todos os serviços

### 🌐 Acessar o Sistema

Após o deploy, acesse:

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| **Frontend (Dashboard)** | http://localhost:3000 | - |
| **Django Admin** | http://localhost:8000/admin | admin / admin_password_2025 |
| **Flask API** | http://localhost:5000/api/health | - |

### 🔧 Comandos Úteis

```bash
# Ver logs de todos os serviços
docker compose logs -f

# Ver logs de um serviço específico
docker compose logs -f django
docker compose logs -f flask
docker compose logs -f frontend

# Parar todos os serviços
docker compose down

# Parar e remover volumes (ATENÇÃO: apaga dados)
docker compose down -v

# Reiniciar um serviço específico
docker compose restart django

# Ver status dos serviços
docker compose ps

# Executar comandos no Django
docker compose exec django python manage.py shell
docker compose exec django python manage.py createsuperuser

# Acessar banco de dados PostgreSQL
docker compose exec postgres psql -U mis_user -d mis_core_db
```

## 📦 Deploy Offline (Ambiente Sem Internet)

Para ambientes industriais sem acesso à internet:

### 1. Exportar imagens (em máquina com internet)

```bash
./scripts/export-images.sh
```

Isso criará o arquivo `docker-images/mis-core-images.tar.gz` (~2GB).

### 2. Transferir para ambiente offline

Copie os seguintes arquivos para a máquina de destino:

- `docker-images/mis-core-images.tar.gz`
- `docker-compose.yml`
- `.env`
- `scripts/import-images.sh`

### 3. Importar imagens (em máquina offline)

```bash
./scripts/import-images.sh
```

### 4. Iniciar sistema

```bash
docker compose up -d
```

## 🔐 Configuração de Portas

Todas as portas são configuráveis no arquivo `.env`:

```env
DJANGO_PORT=8000
FLASK_PORT=5000
FRONTEND_PORT=3000
POSTGRES_PORT=5432
INFLUXDB_PORT=8086
```

## 🗄️ Persistência de Dados

Os dados são armazenados em volumes Docker:

- `mis-core-postgres-data` - Banco de dados PostgreSQL
- `mis-core-influxdb-data` - Dados de série temporal
- `mis-core-django-static` - Arquivos estáticos do Django

Para fazer backup:

```bash
# Backup PostgreSQL
docker compose exec postgres pg_dump -U mis_user mis_core_db > backup.sql

# Backup InfluxDB
docker compose exec influxdb influxd backup -portable /tmp/backup
docker compose cp influxdb:/tmp/backup ./influxdb-backup
```

## 🔄 Atualização do Sistema

```bash
# Parar sistema
docker compose down

# Atualizar código
git pull origin manus-docker

# Reconstruir e reiniciar
docker compose up -d --build
```

## 🐛 Troubleshooting

### Porta já em uso

Se alguma porta estiver em uso, edite o arquivo `.env` e altere as portas:

```env
DJANGO_PORT=8001
FLASK_PORT=5001
FRONTEND_PORT=3001
```

### Serviço não inicia

Verifique os logs:

```bash
docker compose logs django
docker compose logs flask
docker compose logs frontend
```

### Resetar completamente o sistema

```bash
# ATENÇÃO: Isso apaga TODOS os dados
docker compose down -v
docker compose up -d
```

### Problemas de memória

Se o sistema estiver lento, aumente os recursos do Docker:

- Docker Desktop: Settings → Resources → Memory (mínimo 8GB)

## 📚 Documentação Adicional

- `GUIA_EXECUCAO_FINAL.md` - Guia de execução manual (sem Docker)
- `FLUXO_DADOS_HARMONICO.md` - Arquitetura e fluxo de dados
- `GUIA_DIAGNOSTICOS.md` - Diagnóstico de problemas
- `docs/GUIA_TESTES.md` - Guia de testes

## 🆘 Suporte

Para problemas ou dúvidas:

1. Verifique os logs: `docker compose logs -f`
2. Consulte a documentação em `docs/`
3. Abra uma issue no GitHub

---

**Desenvolvido com:** Docker, React 18, Django 5.0, Flask 3.0, PostgreSQL 15, InfluxDB 1.8
