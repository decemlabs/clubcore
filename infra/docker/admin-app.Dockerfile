# syntax=docker/dockerfile:1.7
#
# admin-app production image: pnpm workspace build → nginx static serving.
# Build context: repo root (needed for pnpm-lock.yaml + workspace packages).
#
# IMG-03: non-root nginx user, listen :8080, SPA try_files fallback.
# T-118-04: runs as nginx user (non-root).
#
# Build: docker build -f infra/docker/admin-app.Dockerfile -t clubcore/admin-app:<tag> .

# ---- Stage 1: node build ----------------------------------------------------
# Pinned digest: node:20-alpine (resolved 2026-06-16)
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS builder

# Enable corepack and activate pnpm at the exact lockfile version.
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate

WORKDIR /workspace

# Copy workspace manifests first — layer cache: dep changes bust this, source
# changes don't (pnpm lockfile is shared at root).
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

# Copy only the packages that @clubcore/admin-app depends on.
# packages/api-client: workspace:* dependency.
COPY packages/api-client/package.json ./packages/api-client/
COPY packages/ui/package.json ./packages/ui/

# Copy the target app manifest.
COPY apps/admin-app/package.json ./apps/admin-app/

# Install dependencies with frozen lockfile (T-118-02 supply-chain integrity).
# --filter admin-app... includes transitive workspace deps (api-client, ui).
RUN pnpm install --frozen-lockfile --filter @clubcore/admin-app...

# Copy source for build (after deps to preserve cache).
COPY packages/api-client/ ./packages/api-client/
COPY packages/ui/ ./packages/ui/
COPY apps/admin-app/ ./apps/admin-app/

# Build the admin-app (tsc -b && vite build → dist/).
RUN pnpm --filter @clubcore/admin-app build

# ---- Stage 2: nginx runtime -------------------------------------------------
# Pinned digest: nginx:1.27-alpine (resolved 2026-06-16)
FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10 AS runtime

# Patch base-image OS CVEs flagged by the trivy IMG-04 gate (e.g. nghttp2-libs,
# zlib HIGH/CRITICAL). The pinned digest keeps the build reproducible; `apk upgrade`
# pulls the latest alpine security patches available at build time.
RUN apk upgrade --no-cache

# Configure nginx to run as the built-in `nginx` user (non-root, T-118-04).
# Create writable directories the nginx worker needs (owned by nginx user).
RUN mkdir -p /var/cache/nginx /tmp/client_body /tmp/proxy /tmp/fastcgi /tmp/uwsgi /tmp/scgi \
    && chown -R nginx:nginx /var/cache/nginx /tmp/client_body /tmp/proxy /tmp/fastcgi /tmp/uwsgi /tmp/scgi \
    && chmod -R 755 /var/cache/nginx

# Copy nginx config (listen :8080, SPA try_files, static asset caching).
COPY infra/nginx/admin-app.conf /etc/nginx/nginx.conf

# Copy built static assets from build stage.
COPY --from=builder --chown=nginx:nginx /workspace/apps/admin-app/dist /usr/share/nginx/html

USER nginx
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
