# =============================================================================
# Frontend React — multi-stage build com versionamento determinístico
# =============================================================================
#
# Build args expostos:
#   MIS_VERSION       — versão semântica (ex: 1.5.2)
#   MIS_GIT_HASH      — hash curto do git (passar via --build-arg)
#   MIS_BUILD_TIME    — ISO 8601 do build (passar via --build-arg)
#   VITE_*_URL        — endpoints relativos (defaults funcionam em standalone)
#
# Esses valores são gravados em:
#   /etc/mis-version           (legível pelo entrypoint)
#   bundle (via define do Vite, em version.ts)
#   /usr/share/nginx/html/version.json (gerado em runtime pelo entrypoint)
# =============================================================================

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

ARG MIS_VERSION=0.0.0-dev
ARG MIS_GIT_HASH=no-git
ARG MIS_BUILD_TIME=unknown

ENV VITE_APP_VERSION=$MIS_VERSION \
    VITE_GIT_HASH=$MIS_GIT_HASH \
    VITE_BUILD_TIME=$MIS_BUILD_TIME

# Dependências
COPY package.json pnpm-lock.yaml ./
COPY patches ./patches

RUN npm install -g pnpm@10.4.1 && \
    pnpm install

# Código
COPY . .

# Build args do Vite (URLs)
ARG VITE_DJANGO_API_URL
ARG VITE_FLASK_API_URL
ARG VITE_FASTAPI_V2_URL
ARG VITE_APP_LOGO
ARG VITE_APP_TITLE
ARG VITE_ANALYTICS_ENDPOINT
ARG VITE_ANALYTICS_WEBSITE_ID

ENV VITE_DJANGO_API_URL=$VITE_DJANGO_API_URL \
    VITE_FLASK_API_URL=$VITE_FLASK_API_URL \
    VITE_FASTAPI_V2_URL=$VITE_FASTAPI_V2_URL \
    VITE_APP_LOGO=$VITE_APP_LOGO \
    VITE_APP_TITLE=$VITE_APP_TITLE \
    VITE_ANALYTICS_ENDPOINT=$VITE_ANALYTICS_ENDPOINT \
    VITE_ANALYTICS_WEBSITE_ID=$VITE_ANALYTICS_WEBSITE_ID

RUN pnpm build && \
    echo "${MIS_VERSION}|${MIS_GIT_HASH}|${MIS_BUILD_TIME}" > /app/dist/public/.mis-build-stamp

# Stage 2: Production (nginx)
FROM nginx:alpine

# Versão fica DISPONÍVEL como ENV no container (entrypoint usa)
ARG MIS_VERSION=0.0.0-dev
ARG MIS_GIT_HASH=no-git
ARG MIS_BUILD_TIME=unknown
ENV MIS_VERSION=$MIS_VERSION \
    MIS_GIT_HASH=$MIS_GIT_HASH \
    MIS_BUILD_TIME=$MIS_BUILD_TIME

# Bundle
COPY --from=builder /app/dist/public /usr/share/nginx/html

# Symlink permite que /mis-core/index.html resolva para /index.html
# (mantém compat com o try_files do nginx.conf)
RUN ln -s . /usr/share/nginx/html/mis-core

# Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Stamp da versão como label da imagem (visível em docker inspect)
LABEL org.opencontainers.image.version="${MIS_VERSION}" \
      org.opencontainers.image.revision="${MIS_GIT_HASH}" \
      org.opencontainers.image.created="${MIS_BUILD_TIME}" \
      org.opencontainers.image.title="mis-core-frontend"

# Também grava num arquivo dentro da imagem para `docker exec ... cat` debug
RUN echo "version=${MIS_VERSION}" > /etc/mis-version && \
    echo "git=${MIS_GIT_HASH}" >> /etc/mis-version && \
    echo "build_time=${MIS_BUILD_TIME}" >> /etc/mis-version

EXPOSE 80

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
