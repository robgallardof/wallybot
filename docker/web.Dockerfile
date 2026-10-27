FROM node:26-alpine AS build
# Node 25+ no longer bundles Corepack, so install the pinned pnpm through the bundled npm.
RUN npm install -g pnpm@10.11.0
WORKDIR /web
ENV NEXT_TELEMETRY_DISABLED=1
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/web ./
RUN pnpm build
FROM node:26-alpine AS runtime
# The standalone server only needs Node. Bundled package managers bring unused vulnerable
# dependencies into the shipped image; retain them only in the build stage above.
RUN apk upgrade --no-cache \
    && rm -rf /usr/local/lib/node_modules /opt/yarn-* \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
       /usr/local/bin/yarn /usr/local/bin/yarnpkg
WORKDIR /web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=8080
COPY --from=build --chown=node:node /web/.next/standalone ./
COPY --from=build --chown=node:node /web/.next/static ./.next/static
COPY --from=build --chown=node:node /web/public ./public
USER node
EXPOSE 8080
CMD ["node", "server.js"]
