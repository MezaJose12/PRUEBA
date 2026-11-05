# Frontend estatico servido por nginx. Se publica en el puerto 8080 (ver docker-compose.yml).
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY src /usr/share/nginx/html
