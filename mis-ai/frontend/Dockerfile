# Dockerfile - Frontend React/Vite (Predição Genérica)
# Build multi-stage para otimizar tamanho da imagem

# ==================== STAGE 1: Build ====================
FROM node:22-alpine AS builder

# Definir diretório de trabalho
WORKDIR /app

# Habilitar pnpm
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

# Copiar package files
COPY package.json pnpm-lock.yaml ./

# Instalar dependências
RUN pnpm install --frozen-lockfile

# Copiar código fonte
COPY . .

# Build da aplicação
# A base URL já está configurada no vite.config.js
RUN pnpm run build

# ==================== STAGE 2: Production ====================
FROM nginx:alpine

# Copiar build do stage anterior
COPY --from=builder /app/dist /usr/share/nginx/html/prediction-app

# Copiar configuração customizada do Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expor porta
EXPOSE 3007

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3007/prediction-app/ || exit 1

# Comando para iniciar Nginx
CMD ["nginx", "-g", "daemon off;"]

