# Build stage
FROM node:20 AS builder

WORKDIR /app

# Copy package.json and pnpm-lock.yaml
COPY package.json pnpm-lock.yaml ./

# Copy patches directory
COPY patches ./patches

# Install pnpm
RUN npm install -g pnpm

# Install dependencies
RUN pnpm install

# Copy source code (after dependencies are installed)
COPY . .

# Set build-time environment variables for Vite
ARG VITE_DJANGO_API_URL=http://localhost:8001/api
ARG VITE_FLASK_API_URL=http://localhost:5005/api
ARG VITE_APP_TITLE="Monitoramento Industrial"
ARG VITE_APP_LOGO="/favicon.ico"

ENV VITE_DJANGO_API_URL=$VITE_DJANGO_API_URL
ENV VITE_FLASK_API_URL=$VITE_FLASK_API_URL
ENV VITE_APP_TITLE=$VITE_APP_TITLE
ENV VITE_APP_LOGO=$VITE_APP_LOGO

# Build the application
RUN pnpm run build

# Production stage
FROM node:20-slim

WORKDIR /app

# Copy package.json and pnpm-lock.yaml for server dependencies
COPY package.json pnpm-lock.yaml ./

# Copy patches directory (needed for pnpm install)
COPY patches ./patches

# Install pnpm
RUN npm install -g pnpm

# Install only production dependencies (for the server)
RUN pnpm install --prod

# Copy built assets from builder stage
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/server ./server

# Expose port 3000
EXPOSE 3000

# Set environment to production
ENV NODE_ENV=production

# Start the server
CMD ["node", "dist/index.js"]
