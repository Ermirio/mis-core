# Multi-stage build para Frontend React

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Copiar arquivos de dependências
COPY package.json pnpm-lock.yaml ./

# Instalar pnpm e dependências
RUN npm install -g pnpm@10.4.1 && \
    pnpm install --frozen-lockfile

# Copiar código fonte
COPY . .

# Build da aplicação
ARG VITE_DJANGO_API_URL
ARG VITE_FLASK_API_URL
ENV VITE_DJANGO_API_URL=$VITE_DJANGO_API_URL
ENV VITE_FLASK_API_URL=$VITE_FLASK_API_URL

RUN pnpm build

# Stage 2: Production
FROM nginx:alpine

# Copiar arquivos buildados
COPY --from=builder /app/dist /usr/share/nginx/html

# Copiar configuração customizada do Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expor porta
EXPOSE 80

# Script para substituir variáveis de ambiente em runtime
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
