# Backend Flask - Predição Genérica

## Configuração Docker

### Arquivos Importantes

- `Dockerfile` - Imagem Docker do backend
- `.env.docker` - Variáveis de ambiente para Docker
- `.dockerignore` - Arquivos ignorados no build

### Variáveis de Ambiente

#### DATABASE_URL
Conexão com MySQL no host:
```
DATABASE_URL=mysql+pymysql://root:senha@host.docker.internal:3307/density_db
```

**Importante:** 
- Usa `host.docker.internal` para acessar MySQL no host
- Porta `3307` (mesma do MIS)
- Database `density_db`

#### OPC_SERVER_URL
Conexão com servidor OPC UA:
```
OPC_SERVER_URL=opc.tcp://192.168.15.189:49320
```

**Como alterar:**
1. Edite `.env.docker`
2. Altere o IP para o servidor OPC na rede
3. Reinicie o container

### Build e Run

```bash
# Build
docker build -t predicao-backend:latest .

# Run (standalone)
docker run -d \
  -p 5004:5004 \
  --env-file .env.docker \
  --name predicao-backend \
  predicao-backend:latest

# Logs
docker logs -f predicao-backend
```

### Endpoints

- `GET /` - Home
- `GET /api/health` - Health check
- `GET /api/lines` - Listar linhas
- `POST /api/models/{id}/train` - Treinar modelo
- `POST /api/models/{id}/predict` - Fazer predição

Documentação completa: Ver `app.py`

### Troubleshooting

#### Erro de conexão com MySQL
```
# Verificar se MySQL está rodando
docker ps | grep mysql

# Testar conexão
docker exec predicao-backend python -c "from models import get_db; next(get_db())"
```

#### Erro de conexão com OPC
```
# Verificar URL do OPC
docker exec predicao-backend env | grep OPC

# Testar conexão
docker exec predicao-backend python check_opc_connection.py
```

#### Logs
```
# Ver logs da aplicação
docker exec predicao-backend cat logs/app.log

# Ver logs do Gunicorn
docker logs predicao-backend
```

