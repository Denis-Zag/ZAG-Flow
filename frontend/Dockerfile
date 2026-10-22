FROM node:22-alpine AS build
WORKDIR /frontend
ARG PUBLIC_BASE_PATH=""
ENV PUBLIC_BASE_PATH=$PUBLIC_BASE_PATH
COPY package.json build.mjs index.html styles.css app.js admin.html admin.css admin.js behavior-metrics.js favicon.svg ./
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /frontend/dist/ /usr/share/nginx/html/

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q --spider http://127.0.0.1/healthz || exit 1
