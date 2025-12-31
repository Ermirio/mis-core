# Manual de Instalação Offline - MIS Core

Este pacote contém todos os arquivos necessários para implantar o sistema MIS Core em um ambiente sem acesso à internet (Offline).

## Estrutura do Pacote

*   `docker-compose.yml`: Arquivo de orquestração dos serviços (Django, Flask, Frontend, Bancos de Dados, etc).
*   `export_images.ps1`: Script para GERAR este pacote (Executar na máquina com acesso à internet/origem).
*   `import_images.ps1`: Script para INSTALAR no ambiente offline (Executar no servidor de destino).
*   `mis-core-images.tar`: (Será gerado pelo script de exportação) Contém todas as imagens Docker.

## Pré-requisitos no Servidor de Destino

1.  **Docker** instalado e rodando.
2.  **Docker Compose** instalado.
3.  Sistema Operacional compatível (Windows com WSL2 ou Linux).

## Passo a Passo para Instalação

### 1. Na Máquina de Origem (Com Internet/Código)
1.  Abra o PowerShell na pasta deste pacote.
2.  Execute o script de exportação:
    ```powershell
    ./export_images.ps1
    ```
3.  Aguarde o término. O arquivo `mis-core-images.tar` será criado (pode ter vários GBs).
4.  Copie toda a pasta `mis-core-offline` (com o .tar gerado) para um Pen Drive ou HD Externo.

### 2. No Servidor Offline (Destino)
1.  Copie a pasta do Pen Drive para o disco local (ex: `C:\mis-core-offline`).
2.  Abra o PowerShell (ou Terminal) nesta pasta.
3.  Execute o script de importação e start:
    ```powershell
    ./import_images.ps1
    ```
    *Se estiver no Linux, use os comandos equivalentes:*
    ```bash
    docker load -i mis-core-images.tar
    docker-compose up -d
    ```

4.  Aguarde o carregamento das imagens e a inicialização dos containers.

## Acesso aos Serviços

Como este pacote **não inclui o Proxy** (conforme solicitado), os serviços estarão disponíveis diretamente nas seguintes portas:

*   **Frontend (Aplicação Web):** [http://localhost:81](http://localhost:81)
*   **Backend Django (API/Admin):** [http://localhost:8001](http://localhost:8001)
    *   *Admin:* [http://localhost:8001/mis-core-admin/](http://localhost:8001/mis-core-admin/)
*   **Backend Flask (Analytics):** [http://localhost:5002](http://localhost:5002)

## Notas Importantes

*   **Persistência de Dados:** O Docker criará volumes automáticos (`mis-core-mysql-data`, `mis-core-influxdb-data`, etc) para salvar os dados. Eles não serão perdidos se reiniciar a máquina.
*   **Proxy Externo:** Se você for configurar um Proxy Corporativo na frente deste servidor, aponte as rotas para estas portas locais (81, 8001, 5002).
*   **Frontend Config:** O Frontend foi recompilado para rodar no subdiretório `/mis-core/` (e com APIs usando caminhos relativos).
*   **Requisito Obrigatório do Proxy Externo:**
    Configure seu Proxy Corporativo para redirecionar as seguintes rotas:

    1.  `hostname/mis-core/` -> `http://localhost:81/mis-core/` (Frontend)
    2.  `hostname/api/`      -> `http://localhost:8001/api/` (Django)
    3.  `hostname/flask-api/`-> `http://localhost:5002/api/` (Flask - **Rewrite obrigatório**)

    **Exemplo (Nginx):**
    ```nginx
    # 1. Frontend
    location /mis-core/ {
        proxy_pass http://localhost:81/;
    }

    # 2. Django
    location /api/ {
        proxy_pass http://localhost:8001/api/;
    }

    # 3. Flask (Analytics)
    location /flask-api/ {
        rewrite ^/flask-api/(.*)$ /api/$1 break;
        proxy_pass http://localhost:5002;
    }

    # 4. Chronograf (Admin InfluxDB)
    location /chronograf/ {
        proxy_pass http://localhost:8889/chronograf/;
    }
    ```

## Lista de Portas Específicas
Para referência da sua equipe de infraestrutura, estas são as portas que o servidor offline irá escutar no localhost:

*   **81**: Frontend (Redirecionado pelo Proxy `/mis-core/`)
*   **8001**: Django (Redirecionado pelo Proxy `/api/`)
*   **5002**: Flask (Redirecionado pelo Proxy `/flask-api/`)
*   **8087**: InfluxDB (Acesso direto ou ferramentas externas)
*   **3308**: MySQL (Acesso direto ou ferramentas externas)
*   **8889**: Chronograf (Redirecionado pelo Proxy `/chronograf/`)
