# Guia Completo de Deploy Offline - Sistema de Monitoramento Industrial

Este guia detalha o processo completo para criar, salvar e implantar a aplicação em ambientes offline usando Docker.

---

## 📋 Pré-requisitos

### Máquina de Desenvolvimento (Online)
- Docker Desktop instalado
- Git (para clonar o repositório)
- Acesso à internet

### Máquina de Produção (Offline)
- Docker Desktop instalado
- Sistema operacional: Windows 10/11 ou Linux
- Mínimo 8GB RAM, 50GB disco disponível

---

## 🔧 PARTE 1: Preparação na Máquina de Desenvolvimento

### Passo 1.1: Configurar Variáveis de Ambiente

1. **Copie o arquivo de exemplo**:
   ```bash
   cp .env.example .env
   ```

2. **Edite o arquivo `.env`** com as configurações corretas:
   ```bash
   # Portas dos Serviços
   FLASK_PORT=5000
   DJANGO_PORT=8001
   REACT_PORT=3000

   # InfluxDB
   INFLUXDB_HOST=influxdb
   INFLUXDB_PORT=8086
   INFLUXDB_DATABASE=industrial_db
   INFLUXDB_USER=admin
   INFLUXDB_USER_PASSWORD=admin123

   # MySQL
   MYSQL_DATABASE=industrial_db
   MYSQL_USER=admin
   MYSQL_PASSWORD=admin123
   MYSQL_HOST=mysql
   MYSQL_PORT=3306

   # URLs Internas (Docker Network)
   DJANGO_API_URL=http://backend-django:8000/api

   # URLs Externas (Navegador)
   VITE_DJANGO_API_URL=http://localhost:8001/api
   VITE_FLASK_API_URL=http://localhost:5000/api
   ```

### Passo 1.2: Construir as Imagens Docker

Execute o build usando o arquivo de produção:

```bash
docker-compose -f docker-compose.prod.yml build
```

**Tempo estimado**: 10-15 minutos (depende da velocidade da internet e CPU)

### Passo 1.3: Verificar Imagens Criadas

Liste as imagens criadas:

```bash
docker images | grep -E "projeto-monitoramento|influxdb|postgres"
```

Você deve ver algo como:
```
projeto-monitoramento-industrial-completo-frontend-react    latest
projeto-monitoramento-industrial-completo-backend-flask     latest
projeto-monitoramento-industrial-completo-backend-django    latest
influxdb                                                     1.8
mysql                                                        8.0
```

### Passo 1.4: Salvar Imagens para Arquivo

**Comandos para Salvar Manualmente:**

Crie a pasta `docker-images` e execute:

```bash
mkdir docker-images

echo "Salvando Backend Django..."
docker save -o docker-images/backend-django.tar projeto-monitoramento-industrial-completo-backend-django:latest

echo "Salvando Backend Flask..."
docker save -o docker-images/backend-flask.tar projeto-monitoramento-industrial-completo-backend-flask:latest

echo "Salvando Frontend React..."
docker save -o docker-images/frontend-react.tar projeto-monitoramento-industrial-completo-frontend-react:latest

echo "Salvando InfluxDB..."
docker save -o docker-images/influxdb.tar influxdb:1.8

echo "Salvando MySQL..."
docker save -o docker-images/mysql.tar mysql:8.0
```

**Opção B: Comando Manual Único**

```bash
docker save -o offline-images-all.tar \
  projeto-monitoramento-industrial-completo-backend-django:latest \
  projeto-monitoramento-industrial-completo-backend-flask:latest \
  projeto-monitoramento-industrial-completo-frontend-react:latest \
  influxdb:1.8 \
  mysql:8.0
```

### Passo 1.5: Preparar Pacote de Transferência

Crie uma pasta `deploy-package` com os seguintes arquivos:

```
deploy-package/
├── docker-images/
│   ├── backend-django.tar
│   ├── backend-flask.tar
│   ├── frontend-react.tar
│   ├── influxdb.tar
│   └── mysql.tar
├── docker-compose.prod.yml
├── .env.example
├── docker-compose.prod.yml
├── .env.example
└── README-DEPLOY.md
└── README-DEPLOY.md
```

---

## 📦 PARTE 2: Transferência para Máquina Offline

### Opções de Transferência

1. **Pen Drive / HD Externo**: Copie a pasta `deploy-package` completa
2. **Rede Local**: Use compartilhamento de rede ou FTP
3. **CD/DVD**: Grave os arquivos (se couber)

**Tamanho estimado**: 2-4 GB (dependendo das imagens)

---

## 🚀 PARTE 3: Implantação na Máquina Offline

### Passo 3.1: Preparar Ambiente

1. **Criar diretório de instalação**:
   ```bash
   # Windows
   mkdir C:\monitoramento-industrial
   cd C:\monitoramento-industrial

   # Linux
   mkdir -p /opt/monitoramento-industrial
   cd /opt/monitoramento-industrial
   ```

2. **Copiar arquivos do pacote** para este diretório

### Passo 3.2: Carregar Imagens Docker

**Comandos para Carregar Manualmente:**

Navegue até a pasta onde estão os arquivos `.tar` e execute:

```bash
echo "Carregando Backend Django..."
docker load -i docker-images/backend-django.tar

echo "Carregando Backend Flask..."
docker load -i docker-images/backend-flask.tar

echo "Carregando Frontend React..."
docker load -i docker-images/frontend-react.tar

echo "Carregando InfluxDB..."
docker load -i docker-images/influxdb.tar

echo "Carregando MySQL..."
docker load -i docker-images/mysql.tar
```

### Passo 3.3: Configurar Variáveis de Ambiente

1. **Copie o arquivo de exemplo**:
   ```bash
   cp .env.example .env
   ```

2. **Edite `.env` conforme o ambiente de produção**:

   ```bash
   # IMPORTANTE: Ajuste estas variáveis conforme a máquina de produção

   # Portas (mude se houver conflito)
   FLASK_PORT=5000
   DJANGO_PORT=8001
   REACT_PORT=3000

   # URLs Externas - AJUSTE O IP DA MÁQUINA
   # Se a máquina tem IP 192.168.1.100:
   VITE_DJANGO_API_URL=http://192.168.1.100:8001/api
   VITE_FLASK_API_URL=http://192.168.1.100:5000/api

   # Senhas de Produção (MUDE ESTAS!)
   INFLUXDB_USER_PASSWORD=SenhaSegura123!
   MYSQL_PASSWORD=OutraSenhaSegura456!

   # Resto mantém igual ao desenvolvimento
   ```

### Passo 3.4: Iniciar Aplicação

```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Verificar status**:
```bash
docker-compose -f docker-compose.prod.yml ps
```

Todos os serviços devem estar com status `Up` e `healthy`.

### Passo 3.5: Verificação e Testes

1. **Acessar a aplicação**:
   - Abra o navegador em `http://localhost:3000`
   - Ou use o IP da máquina: `http://192.168.1.100:3000`

2. **Verificar logs**:
   ```bash
   # Ver todos os logs
   docker-compose -f docker-compose.prod.yml logs -f

   # Ver log de um serviço específico
   docker-compose -f docker-compose.prod.yml logs -f backend-flask
   ```

3. **Testar conectividade**:
   - Backend Flask: `http://localhost:5000/api/health`
   - Backend Django: `http://localhost:8001/api/health/`

---

## 🔄 Comandos Úteis de Manutenção

### Gerenciamento Básico

```bash
# Iniciar serviços
docker-compose -f docker-compose.prod.yml up -d

# Parar serviços
docker-compose -f docker-compose.prod.yml down

# Reiniciar todos os serviços
docker-compose -f docker-compose.prod.yml restart

# Reiniciar um serviço específico
docker-compose -f docker-compose.prod.yml restart backend-flask

# Ver status
docker-compose -f docker-compose.prod.yml ps

# Ver logs em tempo real
docker-compose -f docker-compose.prod.yml logs -f

# Ver uso de recursos
docker stats
```

### Backup de Dados

```bash
# Backup do banco MySQL
docker exec mysql-industrial-prod mysqldump -u admin -p industrial_db > backup_mysql.sql

# Backup do InfluxDB
docker exec influxdb-industrial-prod influxd backup -portable /tmp/backup
docker cp influxdb-industrial-prod:/tmp/backup ./backup_influxdb
```

### Atualização de Imagens

Quando houver uma nova versão:

1. Receba o novo pacote de imagens
2. Pare os serviços: `docker-compose -f docker-compose.prod.yml down`
3. Carregue as novas imagens manualmente (docker load...)
4. Inicie novamente: `docker-compose -f docker-compose.prod.yml up -d`

---

## 🛠️ Solução de Problemas

### Problema: Porta já em uso

**Erro**: `Bind for 0.0.0.0:5000 failed: port is already allocated`

**Solução**: Edite `.env` e mude a porta:
```env
FLASK_PORT=5001
```

### Problema: Serviço não inicia (unhealthy)

**Verificar logs**:
```bash
docker-compose -f docker-compose.prod.yml logs backend-django
```

**Causas comuns**:
- Banco de dados não está pronto (aguarde 30s)
- Erro de configuração no `.env`
- Falta de memória

### Problema: Frontend não conecta ao backend

**Verificar**:
1. As URLs em `.env` estão corretas?
2. O IP da máquina mudou?
3. Firewall bloqueando as portas?

**Solução**:
```bash
# Reconstruir frontend com novas variáveis
docker-compose -f docker-compose.prod.yml up -d --build frontend-react
```

---

## 📝 Checklist de Deploy

- [ ] Imagens Docker construídas
- [ ] Imagens salvas em arquivos .tar
- [ ] Arquivo `.env` configurado
- [ ] Comandos de load testados
- [ ] Pacote transferido para máquina offline
- [ ] Docker instalado na máquina de produção
- [ ] Imagens carregadas com sucesso
- [ ] Variáveis de ambiente ajustadas (IPs, portas)
- [ ] Serviços iniciados e healthy
- [ ] Aplicação acessível no navegador
- [ ] Testes de conectividade realizados

---

## 🔐 Segurança em Produção

1. **Mude todas as senhas padrão** no `.env`
2. **Desabilite DEBUG** (já configurado no docker-compose.prod.yml)
3. **Configure firewall** para permitir apenas portas necessárias
4. **Faça backups regulares** dos volumes Docker
5. **Monitore logs** para detectar problemas

---

## 📞 Suporte

Para problemas ou dúvidas:
1. Verifique os logs: `docker-compose logs -f`
2. Consulte a documentação do Docker
3. Entre em contato com a equipe de desenvolvimento
