# Frontend React/Vite - Predição Genérica

## Configuração Docker

### Arquivos Importantes

- `Dockerfile` - Imagem Docker multi-stage
- `nginx.conf` - Configuração do Nginx para servir a SPA
- `vite.config.js` - Configuração do Vite com base URL
- `src/lib/api.js` - Cliente API configurado para proxy

### Configurações de Proxy

#### Base URL
A aplicação é servida em `/prediction-app/` através do proxy Nginx principal.

**vite.config.js:**
```javascript
base: '/prediction-app/'
```

#### API Client
O cliente API detecta automaticamente se está rodando via proxy:

```javascript
// Produção (via proxy): /predicao-api
// Desenvolvimento: http://localhost:5004/api
```

### Build e Run

```bash
# Build
docker build -t predicao-frontend:latest .

# Run (standalone)
docker run -d \
  -p 3007:3007 \
  --name predicao-frontend \
  predicao-frontend:latest

# Acessar
http://localhost:3007/prediction-app/
```

### Desenvolvimento Local

```bash
# Instalar dependências
pnpm install

# Rodar em modo desenvolvimento
pnpm run dev

# Acessar
http://localhost:3007
```

### Build Manual

```bash
# Build
pnpm run build

# Preview
pnpm run preview
```

### Estrutura de Rotas

A aplicação usa React Router com as seguintes rotas:

- `/` → Redirect para `/dashboard`
- `/dashboard` → Dashboard principal
- `/lines` → Gerenciamento de linhas
- `/targets` → Gerenciamento de targets
- `/models` → Gerenciamento de modelos
- `/data` → Coleta de dados
- `/prediction` → Visualização de predições
- `/opc` → Configuração OPC

**Importante:** Todas as rotas funcionam com a base `/prediction-app/`

### Integração com Backend

O frontend se comunica com o backend através do proxy Nginx:

```
Frontend: http://192.168.15.13:3000/prediction-app/
API: http://192.168.15.13:3000/predicao-api/
```

O Nginx principal redireciona:
- `/prediction-app/*` → Container frontend (porta 3007)
- `/predicao-api/*` → Container backend (porta 5004)

### Troubleshooting

#### Erro 404 ao acessar rotas
```
# Verificar se o Nginx está configurado corretamente
docker exec predicao-frontend cat /etc/nginx/conf.d/default.conf

# Verificar se o index.html existe
docker exec predicao-frontend ls -la /usr/share/nginx/html/prediction-app/
```

#### Assets não carregam
```
# Verificar base URL no build
docker exec predicao-frontend cat /usr/share/nginx/html/prediction-app/index.html | grep base

# Deve mostrar: <base href="/prediction-app/">
```

#### API não responde
```
# Verificar URL da API
# Abrir console do navegador e procurar por: [API Client] Base URL

# Deve mostrar: /predicao-api (em produção)
```

### Logs

```bash
# Logs do Nginx
docker logs predicao-frontend

# Logs de acesso
docker exec predicao-frontend cat /var/log/nginx/prediction-app-access.log

# Logs de erro
docker exec predicao-frontend cat /var/log/nginx/prediction-app-error.log
```

