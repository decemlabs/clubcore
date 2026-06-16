# syntax=docker/dockerfile:1.7
#
# client-pwa production image: pnpm workspace build → nginx static serving.
# Build context: repo root (needed for pnpm-lock.yaml + workspace packages).
#
# IMG-03: non-root nginx user, listen :8080, SPA try_files + PWA cache rules.
# T-118-04: runs as nginx user (non-root).
# T-118-05: sw.js/manifest.json served no-cache; /api/* served no-store.
#
# Build: docker build -f infra/docker/client-pwa.Dockerfile -t clubcore/client-pwa:<tag> .

# ---- Stage 1: node build ----------------------------------------------------
# Pinned digest: node:20-alpine (resolved 2026-06-16)
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS builder

# Enable corepack and activate pnpm at the exact lockfile version.
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate

WORKDIR /workspace

# Copy workspace manifests first — layer cache: dep changes bust this, source
# changes don't (pnpm lockfile is shared at root).
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

# Copy only the packages that @clubcore/client-pwa depends on.
# packages/api-client: workspace:* dependency.
COPY packages/api-client/package.json ./packages/api-client/
COPY packages/ui/package.json ./packages/ui/

# Copy the target app manifest.
COPY apps/client-pwa/package.json ./apps/client-pwa/

# Install dependencies with frozen lockfile (T-118-02 supply-chain integrity).
# --filter client-pwa... includes transitive workspace deps.
RUN pnpm install --frozen-lockfile --filter @clubcore/client-pwa...

# Copy source for build (after deps to preserve cache).
COPY packages/api-client/ ./packages/api-client/
COPY packages/ui/ ./packages/ui/
COPY apps/client-pwa/ ./apps/client-pwa/

# Build the client-pwa (tsc -b && vite build → dist/).
# public/ assets (sw.js, manifest.json, offline.html, icons) are copied by Vite
# automatically from apps/client-pwa/public/ into dist/.
RUN pnpm --filter @clubcore/client-pwa build

# ---- Stage 2: nginx runtime -------------------------------------------------
# Pinned digest: nginx:1.27-alpine (resolved 2026-06-16)
FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10 AS runtime

# Configure nginx to run as the built-in `nginx` user (non-root, T-118-04).
# Create writable directories the nginx worker needs (owned by nginx user).
RUN mkdir -p /var/cache/nginx /tmp/client_body /tmp/proxy /tmp/fastcgi /tmp/uwsgi /tmp/scgi \
    && chown -R nginx:nginx /var/cache/nginx /tmp/client_body /tmp/proxy /tmp/fastcgi /tmp/uwsgi /tmp/scgi \
    && chmod -R 755 /var/cache/nginx

# Copy nginx config (listen :8080, SPA try_files, PWA cache rules: sw.js no-cache, /api/* no-store).
COPY infra/nginx/client-pwa.conf /etc/nginx/nginx.conf

# Copy built static assets from build stage.
# Includes public/ assets: sw.js, manifest.json, offline.html, icons (Vite copies them to dist/).
COPY --from=builder --chown=nginx:nginx /workspace/apps/client-pwa/dist /usr/share/nginx/html

USER nginx
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
