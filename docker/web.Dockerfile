FROM node:22-alpine AS build
RUN corepack enable && corepack prepare pnpm@10.11.0 --activate
WORKDIR /web
ENV NEXT_TELEMETRY_DISABLED=1
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/web ./
RUN pnpm build
FROM node:22-alpine AS runtime
RUN apk upgrade --no-cache
WORKDIR /web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=8080
COPY --from=build --chown=node:node /web/.next/standalone ./
COPY --from=build --chown=node:node /web/.next/static ./.next/static
COPY --from=build --chown=node:node /web/public ./public
USER node
EXPOSE 8080
CMD ["node", "server.js"]
