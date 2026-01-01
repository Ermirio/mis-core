# Proxy Reverso MIS-Core

Configuração de proxy reverso Nginx para o sistema MIS-Core.

## Descrição

Este diretório contém a configuração do proxy reverso que direciona o tráfego para:
- **`/`**: Frontend React do MIS-Core (raiz)
- **`/admin`**: Interface administrativa Django
- **`/api/`**: API Django (necessária para o frontend)
- **`/static/`**: Arquivos estáticos do Django

## Arquitetura

```
Cliente (Browser)
    ↓
[nginx-proxy:3000]
    ↓
    ├─→ / → [frontend:81] (React)
    ├─→ /admin → [django:8001/admin] (Django Admin)
    ├─→ /api/ → [django:8001/api] (Django API)
    └─→ /static/ → [django:8001/static] (Static Files)
```

## Uso

### Iniciar o Proxy

```bash
# Build e start do proxy
docker-compose up -d nginx-proxy

# Ver logs
docker-compose logs -f nginx-proxy
```

### Acessar Aplicação

- **Frontend**: http://localhost:3000/
- **Admin**: http://localhost:3000/admin
- **API**: http://localhost:3000/api/

## Configuração

O arquivo `nginx.conf` define:
- **Upstreams**: Serviços internos (frontend:80, django:8000)
- **Locations**: Regras de roteamento e proxy
- **Headers**: Headers necessários para proxy reverso e WebSocket

## Troubleshooting

Se houver problemas com assets 404:
1. Verificar logs: `docker-compose logs nginx-proxy`
2. Verificar se frontend e django estão healthy: `docker ps`
3. Testar diretamente os serviços sem proxy
