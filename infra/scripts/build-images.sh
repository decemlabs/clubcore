#!/usr/bin/env bash
# build-images.sh — Build all clubcore container images tagged with the git short-SHA.
#
# IMG-04: Images are tagged clubcore/<component>:<git-short-sha>. Every deployment
#          pins an explicit immutable tag (no latest tags are produced).
#
# Components built:
#   1. clubcore/backend:<sha>   — shared Python base image for ALL 4 Python workloads:
#      - backend      → CMD ["uvicorn", "app.main:create_app", "--factory", ...]  (default)
#      - telegram-bot → command: python -m app.workers.telegram_bot  (Helm/compose override)
#      - arq-worker   → command: arq app.workers.WorkerSettings       (Helm/compose override)
#      - migrate      → command: alembic upgrade head                 (Helm/compose override)
#      No separate Dockerfile is needed for the other 3 Python workloads.
#   2. clubcore/admin-app:<sha> — staff admin panel (React 18 + TanStack, nginx static)
#   3. clubcore/client-pwa:<sha>— client PWA (React 18 + vite-plugin-pwa, nginx static)
#
# Usage:
#   cd /path/to/clubcore && bash infra/scripts/build-images.sh
#
# The resolved $TAG is echoed at the end so Helm values (plans 02–04) can pin image.tag.

set -euo pipefail

# Determine repo root so the script works from any working directory.
REPO_ROOT="$(git rev-parse --show-toplevel)"

# Derive the immutable tag from the current git commit short-SHA.
# IMG-04: the tag must be immutable — two builds with the same tag must have
# identical contents. If the working tree is dirty, the parent commit SHA no
# longer uniquely identifies the build, so append "-dirty" to avoid silently
# sharing a tag between a clean build and an uncommitted one.
TAG="$(git rev-parse --short HEAD)"
if ! git diff --quiet || ! git diff --cached --quiet; then
    TAG="${TAG}-dirty"
    echo "WARNING: working tree is dirty — tagging images '${TAG}'." >&2
    echo "         Commit your changes for a reproducible, immutable tag (IMG-04)." >&2
fi

echo "=== clubcore image build ==="
echo "Repo root : $REPO_ROOT"
echo "Image tag : $TAG"
echo ""

# ── 1. Backend base image ─────────────────────────────────────────────────────
# Build context is apps/backend/ (pyproject.toml, uv.lock, app/, alembic/, alembic.ini).
echo "[1/3] Building clubcore/backend:${TAG} …"
docker build \
    -f "${REPO_ROOT}/infra/docker/backend.Dockerfile" \
    -t "clubcore/backend:${TAG}" \
    "${REPO_ROOT}/apps/backend"
echo "      → clubcore/backend:${TAG} OK"
echo ""

# ── 2. admin-app frontend image ───────────────────────────────────────────────
# Build context is repo root (pnpm workspace lockfile + packages/api-client).
echo "[2/3] Building clubcore/admin-app:${TAG} …"
docker build \
    -f "${REPO_ROOT}/infra/docker/admin-app.Dockerfile" \
    -t "clubcore/admin-app:${TAG}" \
    "${REPO_ROOT}"
echo "      → clubcore/admin-app:${TAG} OK"
echo ""

# ── 3. client-pwa frontend image ──────────────────────────────────────────────
# Build context is repo root (pnpm workspace lockfile + packages/api-client).
echo "[3/3] Building clubcore/client-pwa:${TAG} …"
docker build \
    -f "${REPO_ROOT}/infra/docker/client-pwa.Dockerfile" \
    -t "clubcore/client-pwa:${TAG}" \
    "${REPO_ROOT}"
echo "      → clubcore/client-pwa:${TAG} OK"
echo ""

# ── Summary ───────────────────────────────────────────────────────────────────
echo "=== Build complete ==="
echo ""
echo "Built images:"
docker images --format "  {{.Repository}}:{{.Tag}}\t({{.Size}})" \
    | grep "clubcore/.*:${TAG}"
echo ""
echo "TAG=${TAG}"
echo ""
echo "Helm pin:  image.tag=${TAG}"
echo "Next step: bash infra/scripts/scan-images.sh"
