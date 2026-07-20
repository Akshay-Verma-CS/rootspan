FROM node:24-alpine AS build

RUN corepack enable && corepack prepare pnpm@11.9.0 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY index.html tsconfig.app.json tsconfig.json tsconfig.node.json vite.config.ts ./
COPY src ./src
RUN pnpm run build

FROM nginx:1.29-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=12 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1/ || exit 1
