---
phase: 118-container-images-helm-chart-core-stack
plan: "01"
subsystem: infra/container-images
tags: [docker, nginx, pnpm, python, img-01, img-02, img-03, img-04]
dependency_graph:
  requires: []
  provides:
    - "infra/docker/backend.Dockerfile (shared backend-base for 4 Python workloads)"
    - "infra/docker/admin-app.Dockerfile (nginx static SPA)"
    - "infra/docker/client-pwa.Dockerfile (nginx PWA static with cache rules)"
    - "infra/nginx/admin-app.conf"
    - "infra/nginx/client-pwa.conf"
    - "infra/scripts/build-images.sh"
    - "infra/scripts/scan-images.sh"
  affects:
    - "Phase 118 plans 02/03/04 (Helm chart and Deployments reference these image tags)"
tech_stack:
  added:
    - "infra/docker/*.Dockerfile — multi-stage Docker builds"
    - "infra/nginx/*.conf — custom nginx config (non-root, :8080, SPA fallback, PWA rules)"
    - "infra/scripts/build-images.sh — git-SHA image tagging"
    - "infra/scripts/scan-images.sh — trivy HIGH/CRITICAL gate"
  patterns:
    - "Multi-stage Docker build: uv builder → slim runtime (backend)"
    - "Multi-stage Docker build: node pnpm builder → nginx runtime (frontend)"
    - "Base image pinned by @sha256: digest (supply-chain integrity, T-118-01)"
    - "Shared backend-base image: 4 Python workloads via CMD/command override (no separate images)"
    - "Non-root users: app (backend), nginx uid=101 (frontends) — T-118-04"
    - "nginx on :8080 unprivileged + writable /tmp paths for non-root nginx worker"
    - "PWA cache rules: sw.js/manifest no-cache, /api/* no-store always — T-118-05/P10"
key_files:
  created:
    - infra/docker/backend.Dockerfile
    - infra/docker/admin-app.Dockerfile
    - infra/docker/client-pwa.Dockerfile
    - infra/nginx/admin-app.conf
    - infra/nginx/client-pwa.conf
    - infra/docker/.dockerignore.web
    - infra/scripts/build-images.sh
    - infra/scripts/scan-images.sh
  modified:
    - apps/backend/.dockerignore
decisions:
  - "Shared backend-base: telegram-bot/arq-worker/migrate reuse clubcore/backend via CMD override — no separate Pythong images (matches docker-compose.yml pattern)"
  - "nginx non-root on :8080: add_header entries use `always` flag for no-store on 404 /api/* location"
  - "add_header Cache-Control no-store always for /api/*: nginx sends add_header only on 2xx/3xx by default; `always` required to emit header on 404 return"
  - "trivy operator-pending: trivy not installed in this environment; scan gate wired correctly in scan-images.sh, honest OPERATOR-PENDING output per D-V40-LOCAL-VALIDATE"
metrics:
  duration: "~25 minutes"
  completed_date: "2026-06-16"
  tasks_completed: 3
  tasks_total: 3
  files_created: 8
  files_modified: 1
---

# Phase 118 Plan 01: Container Images Summary

Production-hardened Docker images for all 6 runtime components: shared Python backend-base (4 workloads via CMD override) + 2 nginx frontend static images; git-SHA tagging with trivy HIGH/CRITICAL scan gate wired (operator-pending — trivy not installed in build environment).

## Resolved Values

| Item | Value |
|------|-------|
| Build-time git SHA | `934d2d8b` (at build; advances with each plan commit) |
| ghcr.io/astral-sh/uv:python3.12-bookworm-slim digest | `sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58` |
| python:3.12-slim-bookworm digest | `sha256:76d4b7b6305788c6b4c6a19d6a22a3921bf802e9af4d5e1e5bd771208dba74bf` |
| node:20-alpine digest | `sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293` |
| nginx:1.27-alpine digest | `sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10` |

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Backend-base Dockerfile hardening + .dockerignore (IMG-01, IMG-02) | `ce61968a` | infra/docker/backend.Dockerfile, apps/backend/.dockerignore |
| 2 | admin-app + client-pwa nginx images with SPA fallback + PWA cache rules (IMG-03) | `934d2d8b` | infra/docker/admin-app.Dockerfile, infra/docker/client-pwa.Dockerfile, infra/nginx/admin-app.conf, infra/nginx/client-pwa.conf, infra/docker/.dockerignore.web |
| 3 | git-SHA build script + trivy scan gate (IMG-04) | `6e42d106` | infra/scripts/build-images.sh, infra/scripts/scan-images.sh |

## Acceptance Criteria Status

### Task 1 — Backend-base (IMG-01, IMG-02)

| Criterion | Status |
|-----------|--------|
| `docker build` succeeds | PASSED — build completes without error |
| Runs as `app` user (non-root) | PASSED — `whoami` returns `app` |
| Both FROM lines pin `@sha256:` digest | PASSED — 2 digests pinned |
| HEALTHCHECK present, probes /healthz:8000, no curl | PASSED — python urllib one-liner |
| tzdata installed + ENV TZ=UTC | PASSED — `echo $TZ` returns `UTC` |
| alembic, uvicorn, arq packages present | PASSED — importlib.util confirms all 3 present |
| No .env or secrets in any layer | PASSED — no COPY of .env; .dockerignore excludes .env* |

### Task 2 — Frontend nginx images (IMG-03)

| Criterion | Status |
|-----------|--------|
| Both images build with pnpm --frozen-lockfile | PASSED — clean build, no lockfile violations |
| nginx runs non-root (:8080) | PASSED — uid=101 (nginx user) |
| Deep SPA route returns 200 (try_files) — admin-app | PASSED — /clients/some/nested/route → 200 |
| Deep SPA route returns 200 (try_files) — client-pwa | PASSED — /some/deep/spa/route → 200 |
| client-pwa sw.js Cache-Control: no-cache | PASSED |
| client-pwa manifest.json Cache-Control: no-cache | PASSED |
| client-pwa /api/* Cache-Control: no-store | PASSED — `always` flag applied for 404 responses |
| public/ assets (sw.js, manifest, icons) in dist/ | PASSED — Vite PWA plugin copies from public/ |

### Task 3 — Build script + trivy gate (IMG-04)

| Criterion | Status |
|-----------|--------|
| build-images.sh syntax (bash -n) | PASSED |
| scan-images.sh syntax (bash -n) | PASSED |
| Tags every image with git short-SHA | PASSED — TAG=$(git rev-parse --short HEAD) |
| No :latest tag produced | PASSED — grep :latest returns empty |
| Documents telegram-bot/arq-worker/migrate reuse | PASSED — header comment in build-images.sh |
| trivy --severity HIGH,CRITICAL --exit-code 1 per image | PASSED — wired correctly |
| Trivy scan result | OPERATOR-PENDING — trivy not installed in environment |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] nginx add_header not sent on 404 responses**
- **Found during:** Task 2 verification
- **Issue:** `add_header Cache-Control "no-store"` in `location /api/` was not emitted because nginx only sends `add_header` directives on 2xx/3xx responses by default; the location returns 404.
- **Fix:** Added `always` flag: `add_header Cache-Control "no-store" always;` — nginx then emits the header on any status code including 404.
- **Files modified:** infra/nginx/client-pwa.conf
- **Commit:** `934d2d8b`

## Operator-Pending Items

### IMG-04 Trivy Scan Gate

`trivy` is not installed in this build environment. The scan gate script is correctly wired and will run when trivy is available.

**To complete the gate:**
```bash
# Install trivy (macOS)
brew install aquasecurity/trivy/trivy

# Run scan gate against the current images
bash infra/scripts/scan-images.sh
```

**Or manually:**
```bash
SHA=$(git rev-parse --short HEAD)
trivy image --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed clubcore/backend:$SHA
trivy image --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed clubcore/admin-app:$SHA
trivy image --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed clubcore/client-pwa:$SHA
```

## Threat Coverage

All 6 STRIDE threats mitigated per plan:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-118-01 Tampering (base images) | @sha256: digest pins on all 4 base images | DONE |
| T-118-02 Tampering (dep installs) | uv sync --frozen + pnpm --frozen-lockfile | DONE |
| T-118-03 Info Disclosure (layers) | .dockerignore excludes .env*, .git/, tests/ | DONE |
| T-118-04 EoP (runtime root) | USER app / USER nginx; nginx on :8080 | DONE |
| T-118-05 Info Disclosure (PWA SW) | sw.js/manifest no-cache, /api/* no-store always | DONE |
| T-118-SC Tampering (supply chain) | trivy gate wired (operator-pending); no :latest | WIRED |

## Self-Check: PASSED

**Files created:**
- `/Users/andre/Workspace/Development/clubcore/infra/docker/backend.Dockerfile` — EXISTS
- `/Users/andre/Workspace/Development/clubcore/infra/docker/admin-app.Dockerfile` — EXISTS
- `/Users/andre/Workspace/Development/clubcore/infra/docker/client-pwa.Dockerfile` — EXISTS
- `/Users/andre/Workspace/Development/clubcore/infra/nginx/admin-app.conf` — EXISTS
- `/Users/andre/Workspace/Development/clubcore/infra/nginx/client-pwa.conf` — EXISTS
- `/Users/andre/Workspace/Development/clubcore/infra/docker/.dockerignore.web` — EXISTS
- `/Users/andre/Workspace/Development/clubcore/infra/scripts/build-images.sh` — EXISTS
- `/Users/andre/Workspace/Development/clubcore/infra/scripts/scan-images.sh` — EXISTS

**Commits:**
- `ce61968a` — feat(118-01): backend-base Dockerfile (Task 1)
- `934d2d8b` — feat(118-01): frontend nginx images (Task 2)
- `6e42d106` — feat(118-01): git-SHA build + trivy scan gate (Task 3)
