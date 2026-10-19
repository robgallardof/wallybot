FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:782bb89768cc87b7f95c18b95baa1af250e5d451f26794f59363540161147c01
USER root
RUN apk upgrade --no-cache
USER 101
COPY docker/gateway.conf /etc/nginx/conf.d/default.conf
