FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:442753882674b49ae2c1de83ed67896131c0777f56df5005e356e62bc3f7e7ce
USER root
RUN apk upgrade --no-cache
USER 101
COPY docker/gateway.conf /etc/nginx/conf.d/default.conf
