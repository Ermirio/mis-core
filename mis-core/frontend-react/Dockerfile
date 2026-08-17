# Multi-stage build para Frontend React

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Copiar arquivos de dependências
COPY package.json pnpm-lock.yaml ./

# ✅ Necessário para patchedDependencies / patch-package
COPY patches ./patches

# Instalar pnpm e dependências
RUN npm install -g pnpm@10.4.1 && \
    pnpm install

# Copiar código fonte
COPY . .

# Build da aplicação
ARG VITE_DJANGO_API_URL
ARG VITE_FLASK_API_URL
ARG VITE_FASTAPI_V2_URL
ENV VITE_DJANGO_API_URL=$VITE_DJANGO_API_URL
ENV VITE_FLASK_API_URL=$VITE_FLASK_API_URL
ENV VITE_FASTAPI_V2_URL=$VITE_FASTAPI_V2_URL

ARG VITE_APP_LOGO
ARG VITE_APP_TITLE
ARG VITE_ANALYTICS_ENDPOINT
ARG VITE_ANALYTICS_WEBSITE_ID

ENV VITE_APP_LOGO=$VITE_APP_LOGO
ENV VITE_APP_TITLE=$VITE_APP_TITLE
ENV VITE_ANALYTICS_ENDPOINT=$VITE_ANALYTICS_ENDPOINT
ENV VITE_ANALYTICS_WEBSITE_ID=$VITE_ANALYTICS_WEBSITE_ID
RUN pnpm build

# Stage 2: Production
FROM nginx:alpine

# Copiar arquivos buildados
# Copiar arquivos buildados
COPY --from=builder /app/dist/public /usr/share/nginx/html

# Criar symlink para suportar base path /mis-core/
RUN ln -s . /usr/share/nginx/html/mis-core

# Instalar dependências básicas se necessário (sed já vem no alpine)
# RUN apk add --no-cache ...

# Copiar configuração customizada do Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expor porta
EXPOSE 80

# Script para substituir variáveis de ambiente em runtime
COPY docker-entrypoint.sh /docker-entrypoint.sh
# Usar sed para remover caracteres \r (CR) caso o arquivo tenha sido salvo no Windows
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
