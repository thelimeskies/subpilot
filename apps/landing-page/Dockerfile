FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_MERCHANT_APP_URL=https://app.subpilot.kylodo.com
ARG VITE_CUSTOMER_PORTAL_URL=https://portal.subpilot.kylodo.com
ARG VITE_PLATFORM_ADMIN_URL=https://platform-admin.subpilot.kylodo.com

ENV VITE_MERCHANT_APP_URL=$VITE_MERCHANT_APP_URL
ENV VITE_CUSTOMER_PORTAL_URL=$VITE_CUSTOMER_PORTAL_URL
ENV VITE_PLATFORM_ADMIN_URL=$VITE_PLATFORM_ADMIN_URL

COPY package.json package-lock.json tsconfig.base.json ./
COPY apps ./apps
COPY packages ./packages

RUN npm ci
RUN npm run build:landing

FROM nginx:1.27-alpine AS production

ENV API_UPSTREAM=http://backend:8000

COPY docker/frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/apps/landing-page/dist /usr/share/nginx/html

EXPOSE 80
