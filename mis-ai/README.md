# Aplicação de Predição Genérica - Docker & Proxy

Este documento descreve a arquitetura e os passos para fazer o build, deploy e integração da **Aplicação de Predição Genérica** com o sistema principal via proxy Nginx.

## 📋 Arquitetura

A aplicação é composta por dois serviços principais:

1.  **Backend (Flask):**
    -   Responsável pela lógica de negócio, machine learning e comunicação com banco de dados e OPC UA.
    -   Roda na porta **5004**.
    -   Acessado via proxy em `/predicao-api/`.

2.  **Frontend (React/Vite):**
    -   Interface do usuário construída com React e Vite.
    -   Servido por um container Nginx leve.
    -   Roda na porta **3007**.
    -   Acessado via proxy em `/prediction-app/`.

### Fluxo de Rede

```mermaid
graph TD
    subgraph Rede Externa
        Usuario[👤 Usuário]
    end

    subgraph Servidor Principal
        Proxy[🌐 Nginx Proxy Principal<br>(Porta 3000)]
    end

    subgraph Rede Docker (shared-network)
        Frontend[🚀 Predição Frontend<br>(Container, Porta 3007)]
        Backend[⚙️ Predição Backend<br>(Container, Porta 5004)]
        MIS_App[📦 Outras Aplicações...]
    end
    
    subgraph Host
        MySQL[🛢️ MySQL<br>(Porta 3307)]
        OPC_Server[🏭 Servidor OPC UA]
    end

    Usuario -- "http://...:3000/prediction-app/" --> Proxy
    Proxy -- "/prediction-app/" --> Frontend
    Proxy -- "/predicao-api/" --> Backend
    Frontend -- "Chamadas API" --> Proxy
    Backend -- "SQL" --> MySQL
    Backend -- "OPC" --> OPC_Server
```

## 📂 Estrutura de Diretórios

```
predicao-generica/
├── backend/
│   ├── Dockerfile
│   ├── .env.docker
│   ├── .dockerignore
│   ├── README_DOCKER.md
│   └── ... (código fonte)
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── vite.config.js (modificado)
│   ├── src/lib/api.js (modificado)
│   ├── .dockerignore
│   └── README_DOCKER.md
├── Docker-Compose.yaml
├── docker-compose-build.yml
├── nginx-proxy-config.conf
└── README.md (este arquivo)
```

## 🚀 Guia de Deploy - Passo a Passo

Siga estes passos na ordem para integrar a aplicação.

### Passo 1: Build das Imagens Docker

Use o `docker-compose-build.yml` para criar as imagens do frontend e backend.

```bash
# Navegue até a pasta 07-Predict Generic
cd /caminho/para/PACKING PROCESS SOFTWARE/07-Predict Generic/

# Execute o build
# O -f especifica o arquivo de build
docker-compose -f docker-compose-build.yml build
```

Este comando irá:
1.  Criar a imagem `predicao-backend:latest`.
2.  Criar a imagem `predicao-frontend:latest`.

### Passo 2: Atualizar o Proxy Nginx Principal

Agora, vamos configurar o Nginx principal para rotear o tráfego para os novos containers.

1.  **Copie o conteúdo** do arquivo `nginx-proxy-config.conf`.

2.  **Abra o arquivo de configuração do Nginx principal**, que está em `01-Proxy/nginx.conf`.

3.  **Cole o conteúdo** dentro do bloco `server { ... }`, preferencialmente antes das outras `location`.

    ```nginx
    # Exemplo de como deve ficar o nginx.conf principal
    server {
        listen 3000;
        # ... outras configs ...

        # ================================================
        # COLE A CONFIGURAÇÃO DA PREDIÇÃO GENÉRICA AQUI
        # ================================================
        location /prediction-app/ { ... }
        location /predicao-api/ { ... }

        # --- Configurações existentes ---
        location / {
            # proxy para o MIS frontend
        }
        
        location /api/ {
            # proxy para o MIS backend
        }

        # ... etc ...
    }
    ```

4.  **Teste e recarregue o Nginx:**

    ```bash
    # Testar a sintaxe da configuração
    docker exec nginx_proxy_container nginx -t
    # Se retornar "syntax is ok", prossiga

    # Recarregar o Nginx para aplicar as mudanças
    docker exec nginx_proxy_container nginx -s reload
    ```

### Passo 3: Iniciar os Novos Serviços

Com as imagens buildadas e o proxy configurado, inicie os containers da aplicação de predição.

```bash
# Navegue até a pasta 07-Predict Generic
cd /caminho/para/PACKING PROCESS SOFTWARE/07-Predict Generic/

# Inicie os serviços em background
docker-compose -f Docker-Compose.yaml up -d
```

Este comando irá:
1.  Criar e iniciar os containers `predicao_backend_container` e `predicao_frontend_container`.
2.  Conectá-los à `shared-network` para que o proxy possa encontrá-los.

### Passo 4: Verificar e Acessar

1.  **Verifique os containers:**

    ```bash
    docker ps
    ```
    Você deve ver `predicao_backend_container` e `predicao_frontend_container` com status `Up`.

2.  **Acesse a aplicação no navegador:**

    -   **Frontend:** `http://<IP_DO_SERVIDOR>:3000/prediction-app/`

3.  **Teste a API:**

    -   **API Health:** `http://<IP_DO_SERVIDOR>:3000/predicao-api/health`

## ⚙️ Detalhes de Configuração

### Backend (Flask)

-   **Porta:** `5004`
-   **Imagem:** `predicao-backend:latest`
-   **Variáveis de Ambiente:** Configuradas em `.env.docker` e passadas pelo `Docker-Compose.yaml`.
    -   `DATABASE_URL`: `mysql+pymysql://root:ixvq10A%4010@host.docker.internal:3307/density_db`
    -   `OPC_SERVER_URL`: `opc.tcp://192.168.15.189:49320` (altere conforme necessário).
-   **Volumes:**
    -   `./backend/logs` para persistir logs.
    -   `./backend/models` para persistir modelos de ML.

### Frontend (React/Vite)

-   **Porta:** `3007`
-   **Imagem:** `predicao-frontend:latest`
-   **Base URL:** `/prediction-app/` (configurado em `vite.config.js`).
-   **API URL:** `/predicao-api/` (configurado em `src/lib/api.js`).

## 🐛 Troubleshooting

-   **Frontend com tela branca:** Verifique o console do navegador. Se houver erros 404, a `base` no `vite.config.js` ou a configuração do proxy Nginx podem estar incorretas.
-   **API não responde (erro de rede):**
    -   Verifique se o backend está rodando (`docker ps`).
    -   Verifique se a URL da API em `src/lib/api.js` está correta (`/predicao-api/`).
    -   Verifique os logs do Nginx principal para erros de proxy.
-   **Backend não inicia (erro de DB ou OPC):**
    -   Verifique os logs do backend: `docker logs predicao_backend_container`.
    -   Confirme que o MySQL está acessível no `host.docker.internal:3307`.
    -   Confirme que o servidor OPC está acessível no IP e porta configurados.

## 🔄 Comandos Úteis

```bash
# Build de todas as imagens
docker-compose -f docker-compose-build.yml build

# Iniciar todos os serviços
docker-compose -f Docker-Compose.yaml up -d

# Parar todos os serviços
docker-compose -f Docker-Compose.yaml down

# Ver logs de um serviço
docker-compose -f Docker-Compose.yaml logs -f predicao-backend
docker-compose -f Docker-Compose.yaml logs -f predicao-frontend

# Acessar o shell de um container
docker exec -it predicao_backend_container /bin/sh
```

