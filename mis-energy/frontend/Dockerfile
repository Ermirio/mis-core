# Dockerfile - Frontend React/Vite (MIS-Energy)
# Multi-stage build for production

# ==================== STAGE 1: Build ====================
FROM node:22-alpine AS builder

WORKDIR /app

# Enable pnpm
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install

# Copy source code
COPY . .

# Build application
RUN pnpm run build

# ==================== STAGE 2: Production ====================
FROM nginx:alpine

# Copy build from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html/energy-app

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 3008

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3008/mis-energy/ || exit 1

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
