# syntax=docker/dockerfile:1.7
#
# Backend-base image — shared by ALL four Python workloads:
#   - backend (uvicorn factory, default CMD)
#   - telegram-bot  → command: python -m app.workers.telegram_bot
#   - arq-worker    → command: arq app.workers.WorkerSettings
#   - migrate       → command: alembic upgrade head
#
# Workloads differentiate only via Helm/compose command: override (same
# pattern as apps/backend/docker-compose.yml). No separate Python images needed.
#
# IMG-01: both FROM lines pinned by @sha256: digest (supply-chain integrity).
# IMG-02: non-root `app` user; no secrets in any layer.
# Build context: apps/backend/ (pyproject.toml, uv.lock, app/, alembic/, alembic.ini).

# ---- Stage 1: builder -------------------------------------------------------
# Pinned digest: ghcr.io/astral-sh/uv:python3.12-bookworm-slim (resolved 2026-06-16)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS builder

# Make uv predictable inside CI/Docker.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Layer split: deps-only first so source changes don't bust the deps cache.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Bring in the project source and finalize the install.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- Stage 2: runtime -------------------------------------------------------
# Pinned digest: python:3.12-slim-bookworm (resolved 2026-06-16)
FROM python:3.12-slim-bookworm@sha256:76d4b7b6305788c6b4c6a19d6a22a3921bf802e9af4d5e1e5bd771208dba74bf AS runtime

# Install tzdata (not present in slim-bookworm) and clean up in a single layer.
# P9: TZ=UTC on all pods — prevents datetime drift across container restarts.
RUN apt-get update \
    && apt-get install --no-install-recommends -y tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=UTC

# Non-root system user (IMG-02 / T-118-04).
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Carry the prebuilt venv + project from the builder.
COPY --from=builder --chown=app:app /app /app

# The venv lives at /app/.venv (UV_PROJECT_ENVIRONMENT). Put it on PATH so
# `uvicorn`, `alembic`, and `arq` resolve without `uv run`.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

# HEALTHCHECK: probe /healthz (liveness route, port 8000).
# Uses python stdlib urllib — no curl dependency added to the image.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"

# Production CMD for the backend workload (default; other workloads override
# this via Helm command: or compose command:).
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
