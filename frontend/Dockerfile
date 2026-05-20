# Frontend container — multi-stage build: node builds, nginx serves.

# ── Stage 1: build ─────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# Install deps separately so a source change doesn't bust the npm-install layer.
COPY frontend/package.json frontend/package-lock.json* /app/
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY frontend /app
RUN npm run build

# ── Stage 2: serve ─────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# Custom nginx config — proxies /api, /media, /status, /openapi.json,
# /ask, /render etc. to the backend service, serves the SPA otherwise.
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/proxy_params.conf /etc/nginx/proxy_params.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O - http://localhost/ >/dev/null || exit 1
