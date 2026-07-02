FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_CUSTOMER_PORTAL_URL=https://portal.subpilot.kylodo.com
ARG VITE_PUBLIC_API_BASE_URL=https://api.subpilot.kylodo.com/api/v1
ENV VITE_CUSTOMER_PORTAL_URL=$VITE_CUSTOMER_PORTAL_URL
ENV VITE_PUBLIC_API_BASE_URL=$VITE_PUBLIC_API_BASE_URL

COPY package.json package-lock.json tsconfig.base.json ./
COPY apps ./apps
COPY packages ./packages

RUN npm ci
RUN npm run build:merchant

FROM nginx:1.27-alpine AS production

ENV API_UPSTREAM=http://backend:8000

COPY docker/frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/apps/merchant-dashboard/dist /usr/share/nginx/html

EXPOSE 80
