# Guia Rápido - Predição Genérica Docker

## 🚀 Instalação em 4 Passos

### Passo 1: Extrair Arquivos
```bash
# Extrair o ZIP
unzip predicao_generica_completo.zip

# A estrutura deve ficar:
# 07-Predict Generic/
# ├── backend/
# ├── frontend/
# ├── Docker-Compose.yaml
# ├── docker-compose-build.yml
# └── ...
```

### Passo 2: Build das Imagens
```bash
# Navegar até a pasta
cd "07-Predict Generic"

# Build das imagens
docker-compose -f docker-compose-build.yml build

# Aguarde... (pode levar alguns minutos)
```

### Passo 3: Configurar Proxy Nginx

1. **Abra o arquivo de configuração do Nginx principal:**
   ```bash
   # Exemplo: 01-Proxy/nginx.conf
   nano ../01-Proxy/nginx.conf
   ```

2. **Adicione as configurações** (copie de `nginx-proxy-config.conf`):
   ```nginx
   server {
       listen 3000;
       
       # ADICIONE AQUI (antes das outras locations)
       location /prediction-app/ {
           proxy_pass http://predicao_frontend_container:3007/prediction-app/;
           # ... resto da config ...
       }
       
       location /predicao-api/ {
           proxy_pass http://predicao_backend_container:5004/api/;
           # ... resto da config ...
       }
       
       # ... outras locations existentes ...
   }
   ```

3. **Teste e recarregue:**
   ```bash
   docker exec nginx_container nginx -t
   docker exec nginx_container nginx -s reload
   ```

### Passo 4: Iniciar Aplicação
```bash
# Iniciar containers
docker-compose -f Docker-Compose.yaml up -d

# Verificar status
docker ps | grep predicao
```

**Pronto! Acesse:** `http://192.168.15.13:3000/prediction-app/` ✅

---

## 🔧 Configurações Importantes

### Alterar IP do Servidor OPC

1. **Edite o arquivo `.env.docker`:**
   ```bash
   cd backend
   nano .env.docker
   ```

2. **Altere a linha:**
   ```
   OPC_SERVER_URL=opc.tcp://192.168.15.189:49320
   ```
   Para o IP correto do seu servidor OPC.

3. **Reinicie o backend:**
   ```bash
   docker restart predicao_backend_container
   ```

### Alterar Conexão MySQL

Se precisar mudar a conexão do banco:

1. **Edite `.env.docker`:**
   ```
   DATABASE_URL=mysql+pymysql://root:senha@host.docker.internal:3307/density_db
   ```

2. **Reinicie o backend:**
   ```bash
   docker restart predicao_backend_container
   ```

---

## ✅ Checklist de Instalação

- [ ] Extrair arquivos do ZIP
- [ ] Build das imagens: `docker-compose -f docker-compose-build.yml build`
- [ ] Adicionar configuração ao nginx.conf principal
- [ ] Testar Nginx: `docker exec nginx_container nginx -t`
- [ ] Recarregar Nginx: `docker exec nginx_container nginx -s reload`
- [ ] Iniciar containers: `docker-compose -f Docker-Compose.yaml up -d`
- [ ] Verificar containers: `docker ps | grep predicao`
- [ ] Acessar frontend: `http://192.168.15.13:3000/prediction-app/`
- [ ] Testar API: `http://192.168.15.13:3000/predicao-api/health`

---

## 🐛 Problemas Comuns

### Frontend não carrega (tela branca)
```bash
# Ver logs
docker logs predicao_frontend_container

# Verificar se o build foi feito corretamente
docker exec predicao_frontend_container ls -la /usr/share/nginx/html/prediction-app/
```

### API não responde
```bash
# Ver logs do backend
docker logs predicao_backend_container

# Verificar se o backend está rodando
curl http://localhost:5004/api/health
```

### Erro de conexão com MySQL
```bash
# Verificar se MySQL está rodando
docker ps | grep mysql

# Testar conexão do container
docker exec predicao_backend_container python -c "from models import get_db; next(get_db())"
```

### Erro de conexão com OPC
```bash
# Verificar URL configurada
docker exec predicao_backend_container env | grep OPC

# Alterar se necessário (ver seção acima)
```

---

## 📞 Comandos Úteis

```bash
# Ver logs em tempo real
docker-compose -f Docker-Compose.yaml logs -f

# Reiniciar um serviço
docker restart predicao_backend_container
docker restart predicao_frontend_container

# Parar todos os serviços
docker-compose -f Docker-Compose.yaml down

# Rebuild forçado (sem cache)
docker-compose -f docker-compose-build.yml build --no-cache

# Acessar shell do container
docker exec -it predicao_backend_container /bin/sh
```

---

## 📚 Documentação Completa

Para mais detalhes, consulte:
- **README.md** - Documentação completa
- **backend/README_DOCKER.md** - Configuração do backend
- **frontend/README_DOCKER.md** - Configuração do frontend
- **nginx-proxy-config.conf** - Configuração do proxy

---

**Desenvolvido para:** Sistema de Predição Genérica  
**Data:** 2025-10-25  
**Versão:** 1.0.0

