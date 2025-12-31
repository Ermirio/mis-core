# Alterações Necessárias nos Arquivos Existentes

Este documento lista as alterações que você precisa fazer nos arquivos existentes da aplicação de predição genérica.

## 📝 Arquivos que Precisam Ser Substituídos

### 1. Frontend - vite.config.js

**Localização:** `prediction-app-frontend/vite.config.js`

**Ação:** Substituir o arquivo completo pelo novo `frontend/vite.config.js`

**Motivo:** Adiciona configuração de `base: '/prediction-app/'` para funcionar com proxy.

**Ou aplicar manualmente:**
```javascript
// ADICIONAR estas linhas ao vite.config.js existente:

export default defineConfig({
  // ... configurações existentes ...
  
  // ADICIONAR:
  base: '/prediction-app/',
  
  server: {
    host: '0.0.0.0',
    port: 3007,
    strictPort: true,
  },
  
  // ... resto das configurações ...
})
```

---

### 2. Frontend - src/lib/api.js

**Localização:** `prediction-app-frontend/src/lib/api.js`

**Ação:** Substituir o arquivo completo pelo novo `frontend/src/lib/api.js`

**Motivo:** Adiciona detecção automática de URL da API (proxy vs desenvolvimento).

**Ou aplicar manualmente:**
```javascript
// SUBSTITUIR estas linhas no início do arquivo:

// ANTES:
const API_BASE_URL = 'http://localhost:5001/api'

// DEPOIS:
const getApiBaseUrl = () => {
  // Se estiver rodando via proxy (produção)
  if (window.location.pathname.startsWith('/prediction-app')) {
    return '/predicao-api'
  }
  
  // Desenvolvimento local
  return 'http://localhost:5004/api'
}

const API_BASE_URL = getApiBaseUrl()

console.log('[API Client] Base URL:', API_BASE_URL)
```

---

### 3. Backend - Porta da Aplicação

**Localização:** `backend/app.py` (final do arquivo)

**Ação:** Verificar se o Gunicorn está configurado para porta 5004

**Motivo:** Padronizar porta para evitar conflitos.

**Se estiver usando `app.run()` no final do app.py:**
```python
# ALTERAR de:
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

# PARA:
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004, debug=True)
```

**Nota:** O Dockerfile já usa Gunicorn na porta 5004, então esta alteração é apenas para desenvolvimento local.

---

## 📂 Arquivos Novos a Serem Criados

Estes arquivos devem ser criados nas respectivas pastas:

### Backend

1. `backend/Dockerfile` ✅
2. `backend/.env.docker` ✅
3. `backend/.dockerignore` ✅
4. `backend/README_DOCKER.md` ✅

### Frontend

1. `frontend/Dockerfile` ✅
2. `frontend/nginx.conf` ✅
3. `frontend/.dockerignore` ✅
4. `frontend/README_DOCKER.md` ✅

### Raiz do Projeto

1. `Docker-Compose.yaml` ✅
2. `docker-compose-build.yml` ✅
3. `nginx-proxy-config.conf` ✅
4. `README.md` ✅

---

## 🔧 Configuração do Nginx Principal

**Localização:** `01-Proxy/nginx.conf`

**Ação:** Adicionar as configurações de proxy para a aplicação de predição

**Como fazer:**

1. Abra o arquivo `01-Proxy/nginx.conf`

2. Localize o bloco `server { listen 3000; ... }`

3. **ANTES** do bloco `location / { ... }`, adicione:

```nginx
# ==================== PREDIÇÃO GENÉRICA ====================
location /prediction-app/ {
    proxy_pass http://predicao_frontend_container:3007/prediction-app/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cache_bypass $http_upgrade;
    proxy_read_timeout 300;
    proxy_connect_timeout 300;
    proxy_send_timeout 300;
}

location /predicao-api/ {
    proxy_pass http://predicao_backend_container:5004/api/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cache_bypass $http_upgrade;
    proxy_read_timeout 600;
    proxy_connect_timeout 300;
    proxy_send_timeout 300;
    proxy_buffering on;
    proxy_buffer_size 4k;
    proxy_buffers 8 4k;
    proxy_busy_buffers_size 8k;
}
```

4. Salve o arquivo

5. Teste e recarregue:
```bash
docker exec nginx_container nginx -t
docker exec nginx_container nginx -s reload
```

---

## ⚙️ Variáveis de Ambiente a Configurar

### Servidor OPC UA

**Arquivo:** `backend/.env.docker`

**Variável:** `OPC_SERVER_URL`

**Valor atual:** `opc.tcp://192.168.15.189:49320`

**Ação:** Altere para o IP e porta corretos do seu servidor OPC UA.

---

### Banco de Dados MySQL

**Arquivo:** `backend/.env.docker`

**Variável:** `DATABASE_URL`

**Valor atual:** `mysql+pymysql://root:ixvq10A%4010@host.docker.internal:3307/density_db`

**Ação:** Se necessário, altere:
- Usuário (`root`)
- Senha (`ixvq10A@10`)
- Porta (`3307`)
- Nome do banco (`density_db`)

**Nota:** A senha `@` está codificada como `%40` na URL.

---

## 📋 Checklist de Alterações

Use este checklist para garantir que todas as alterações foram feitas:

### Frontend
- [ ] Substituir/modificar `vite.config.js`
- [ ] Substituir/modificar `src/lib/api.js`
- [ ] Criar `Dockerfile`
- [ ] Criar `nginx.conf`
- [ ] Criar `.dockerignore`

### Backend
- [ ] Verificar porta no `app.py` (se aplicável)
- [ ] Criar `Dockerfile`
- [ ] Criar `.env.docker`
- [ ] Configurar `OPC_SERVER_URL` no `.env.docker`
- [ ] Criar `.dockerignore`

### Raiz do Projeto
- [ ] Criar `Docker-Compose.yaml`
- [ ] Criar `docker-compose-build.yml`
- [ ] Criar `nginx-proxy-config.conf`

### Nginx Principal
- [ ] Adicionar configuração de proxy ao `nginx.conf`
- [ ] Testar configuração: `nginx -t`
- [ ] Recarregar Nginx: `nginx -s reload`

### Testes
- [ ] Build das imagens: `docker-compose -f docker-compose-build.yml build`
- [ ] Iniciar containers: `docker-compose -f Docker-Compose.yaml up -d`
- [ ] Verificar containers: `docker ps | grep predicao`
- [ ] Acessar frontend: `http://192.168.15.13:3000/prediction-app/`
- [ ] Testar API: `http://192.168.15.13:3000/predicao-api/health`

---

## 🎯 Resumo

**Alterações Mínimas Necessárias:**

1. **Frontend:** Modificar `vite.config.js` e `src/lib/api.js`
2. **Backend:** Nenhuma alteração no código (apenas criar arquivos Docker)
3. **Nginx:** Adicionar configuração de proxy
4. **Variáveis:** Configurar OPC_SERVER_URL no `.env.docker`

**Arquivos Novos:** Todos os arquivos Docker (Dockerfile, docker-compose, etc.)

**Tempo Estimado:** 15-30 minutos

---

**Dica:** Use o arquivo `nginx-proxy-config.conf` como referência para copiar e colar a configuração do Nginx.

