# syntax=docker/dockerfile:1.7
# Multi-stage build per Phase 3 CONTEXT D-01..D-04.
# Builder: official astral-sh/uv image with Python 3.12 (carries `uv` binary).
# Runtime: bare python:3.12-slim-bookworm (no `uv`, smaller image).

# ---- Stage 1: builder -------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Make uv predictable inside CI/Docker.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Layer split (D-02): deps-only first so source changes don't bust the deps cache.
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
FROM python:3.12-slim-bookworm AS runtime

# Non-root system user (D-03).
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Carry the prebuilt venv + project from the builder.
COPY --from=builder --chown=app:app /app /app

# The venv lives at /app/.venv (UV_PROJECT_ENVIRONMENT). Put it on PATH so
# `uvicorn` and `alembic` resolve without `uv run`.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

# Production-shape CMD (D-03). Hot-reload is a compose override (D-04), not here.
# Matches Phase 2 verification command exactly.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
