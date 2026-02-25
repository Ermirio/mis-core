# Configuração do Proxy Reverso Remoto (Máquina B)

Este pacote contém os arquivos necessários para configurar um Proxy na Máquina B que redireciona o tráfego para a Máquina A (MIS Core).

## O que contém aqui:
1. `docker-compose.yml`: Definição do serviço.
2. `nginx.conf`: Regras de redirecionamento.
3. `nginx_alpine.tar`: Imagem do Docker (para instalação offline).

## Passo a Passo (Manual):

### 1. Preparação
Copie esta pasta inteira (`remote-proxy-setup`) para a Máquina B.

### 2. Configuração
Abra o arquivo `nginx.conf` em um editor de texto e verifique a linha `proxy_pass`.
Ela deve apontar para o IP da Máquina A.
Exemplo:
`proxy_pass http://192.168.15.21:3000;`

### 3. Carregar a Imagem (Offline)
Abra o terminal dentro desta pasta e execute:
```bash
docker load -i nginx_alpine.tar
```
*Aguarde a mensagem "Loaded image: nginx:alpine"*

### 4. Iniciar o Serviço
Ainda no terminal, execute:
```bash
docker-compose up -d
```

### 5. Testar
Acesse no navegador da Máquina B: `http://localhost`
Se tudo estiver correto, você verá a tela de login do MIS Core.
