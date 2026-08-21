FROM nginx:1.27-alpine

RUN apk add --no-cache gettext

COPY nginx-render/nginx.conf.template /etc/nginx/nginx.conf.template
COPY nginx-render/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
