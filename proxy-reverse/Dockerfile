# Dockerfile: proxy-reverse/Dockerfile
# Proxy Reverso Nginx para MIS-Core

FROM nginx:alpine

# Remove configuração padrão do Nginx
RUN rm /etc/nginx/conf.d/default.conf

# Copia configuração customizada
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expõe porta 80 (será mapeada para 3000 no host)
EXPOSE 80

# Comando padrão do Nginx
CMD ["nginx", "-g", "daemon off;"]
