FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json tsconfig.base.json ./
COPY apps ./apps
COPY packages ./packages

RUN npm ci
RUN npm run build:admin

FROM nginx:1.27-alpine AS production

ENV API_UPSTREAM=http://backend:8000

COPY docker/frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/apps/subpilot-admin/dist /usr/share/nginx/html

EXPOSE 80
