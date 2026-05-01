# Phase 3: Tests, Dev Infrastructure & Documentation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 03-tests-dev-infrastructure-documentation
**Areas discussed:** Dockerfile pattern, Docs language + ADR

Areas user explicitly deferred to Claude's Discretion: Test DB & fixtures, compose & alembic.

---

## Dockerfile pattern

### Q1 — Base image strategy

| Option | Description | Selected |
|--------|-------------|----------|
| python:3.12-slim + install uv | Multi-stage; copy uv binary from ghcr.io/astral-sh/uv builder. Standard, predictable, smallest blast radius. | ✓ |
| ghcr.io/astral-sh/uv:python3.12-bookworm-slim | Use the official uv-bundled image directly. One image to track; ties Python patch version to uv release cadence. | |
| python:3.12-slim, no multi-stage | Single-stage `pip install uv && uv sync`. Smallest Dockerfile; final image carries build tools. | |

**User's choice:** python:3.12-slim + install uv (Recommended)
**Notes:** matches Phase 2 D-00 signal — canonical/idiomatic patterns.

### Q2 — uv install layer strategy

| Option | Description | Selected |
|--------|-------------|----------|
| `uv sync --frozen --no-install-project`, then `--no-dev` | Two passes: deps cached in their own layer; project installed second; dev deps stripped. Maximum cache hit. | ✓ |
| Single `uv sync --frozen` after COPY everything | One layer, deps + project together, includes dev deps. Simpler but rebuilds on every source change and ships dev tools. | |
| `uv export` + `pip install` | Drops uv from runtime entirely. Adds an export step; loses uv's resolver guarantees inside the image. | |

**User's choice:** Two-pass uv sync (Recommended)
**Notes:** dovetails with `[tool.uv] dev-dependencies` from Phase 2 D-15.

### Q3 — Final image runtime user + entrypoint

| Option | Description | Selected |
|--------|-------------|----------|
| Non-root `app` user, CMD uvicorn --factory | Create app:app, USER app, CMD matches Phase 2 verification command. No alembic in entrypoint. | ✓ |
| Root user, CMD uvicorn --factory | Skip user creation; runs as root. Acceptable pet-project; bad practice for prod. | |
| Non-root + entrypoint script with `alembic upgrade head` then uvicorn | Couples migration to container start. Adds an extra file. | |

**User's choice:** Non-root `app` user, CMD uvicorn --factory (Recommended)
**Notes:** alembic is intentionally pushed to compose orchestration (see D-12 Discretion).

### Q4 — Hot-reload location

| Option | Description | Selected |
|--------|-------------|----------|
| compose `command:` override + bind-mount | Dockerfile CMD stays prod-shape; compose adds --reload + bind-mount. One Dockerfile. | ✓ |
| Separate Dockerfile.dev with --reload baked in | Two Dockerfiles. Cleaner separation; doubles surface; INFRA-01 implies one file. | |
| No hot-reload — rebuild on changes | Skip reload; user runs `docker compose up --build`. Painful for active dev. | |

**User's choice:** compose command override + bind-mount (Recommended)

---

## Docs language + ADR

### Q1 — Language for the four docs

| Option | Description | Selected |
|--------|-------------|----------|
| Russian | Matches PROJECT.md/REQUIREMENTS.md tone. Code/CLI tools stay English. | |
| English | Matches code comments + prior CONTEXT.md/VERIFICATION.md. Diverges from planning docs. | |
| Mixed — Russian narrative + English code/quick-start | Headings + prose RU; commands + ADR Context blocks EN. Greppable + working-language. | ✓ |

**User's choice:** Mixed — Russian narrative + English commands
**Notes:** explicit signal — downstream doc-writer agent must NOT fully translate code blocks.

### Q2 — ADR template

| Option | Description | Selected |
|--------|-------------|----------|
| MADR 4.0 | Status / Context / Decision Drivers / Considered Options / Decision Outcome / Consequences / Pros and Cons. Modern community standard. | ✓ |
| Nygard classic | Title / Status / Context / Decision / Consequences. Short and direct. No alternatives section. | |
| Freeform / lightweight | Plain markdown without fixed sections. Fast to write; harder to scale. | |

**User's choice:** MADR 4.0 (Recommended)
**Notes:** ADR catalog will grow (events, ЮKassa, auth) — drop a `docs/adr/template.md` skeleton too.

### Q3 — Depth of architecture.md / conventions.md

| Option | Description | Selected |
|--------|-------------|----------|
| Reference level | Overview + slices + invariants + ADR backref. Read once. Not a cookbook. | ✓ |
| Cookbook | Step-by-step examples for adding a module, writing a test, adding a migration. More writing now; faster onboarding. | |
| Minimum viable | One-two paragraphs; minimal doc-debt now; expand later. | |

**User's choice:** Reference level (Recommended)

### Q4 — README quick-start contents

| Option | Description | Selected |
|--------|-------------|----------|
| Two paths: local uv + docker-compose | Both first-class. uv: needs external Postgres. compose: everything included. Plus pytest/ruff/mypy/lint-imports/alembic. | ✓ |
| compose-only | Single path: `cp .env.example .env` + `docker compose up`. Simplest onboarding; local dev hidden. | |
| local uv only | uv sync + uvicorn; compose in a separate section below. Fastest local; needs external Postgres. | |

**User's choice:** Two paths (Recommended)

### Q5 — Where the testing-approach narrative lives

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated `## Testing` section in conventions.md | ASGITransport, pytest-asyncio auto, fixtures, layout tests/{integration,unit,factories}/. No README duplication. | ✓ |
| Separate `docs/testing.md` | New file outside REQUIREMENTS DOCS-01..04 — extends doc set. | |
| Only in README quick-start | One paragraph + `uv run pytest`. Details in conftest.py docstring. Risk: pattern not pinned. | |

**User's choice:** Section in conventions.md (Recommended)

---

## Claude's Discretion

User explicitly deferred two areas; Claude locked sensible defaults in CONTEXT.md (D-10..D-15):

- **Test DB strategy (D-10):** require docker-compose Postgres up (NOT testcontainers). `tests/integration/test_healthz.py` and `tests/unit/test_security.py` need no DB; `db_session` fixture is defined but unused in Phase A bodies (Phase B+ exercises it).
- **Test fixtures shape (D-11):** per-test `create_app()` (function-scope), `asgi-lifespan.LifespanManager` for ASGITransport correctness, `pytest-asyncio` in `auto` mode.
- **compose orchestration (D-12):** `alembic upgrade head` runs as a separate one-shot `migrate` service with `depends_on: postgres (healthy, pg_isready)`. Named volume `postgres-data`. Bind-mount `./app:/app/app:ro` for hot reload.
- **scripts/ design (D-13):** `seed_demo_data.py` pure-print exit-0 (no DB connect); `backup_db.sh` uses `docker compose exec postgres pg_dump` piped through gzip into `./backups/sportzal-<UTC>.sql.gz`. `.dockerignore` added in this phase.
- **pytest config (D-14):** `[tool.pytest.ini_options]` in pyproject.toml — `asyncio_mode = "auto"`, `testpaths = ["tests"]`, strict `filterwarnings`.
- **New dev dep (D-15):** `asgi-lifespan>=2.1` added to `[tool.uv] dev-dependencies` — required for FastAPI lifespan to fire under ASGITransport.

## Deferred Ideas

(Mirrors the `<deferred>` block in CONTEXT.md — preserved for audit trail.)

- CI/CD pipelines — Phase X+
- Production Dockerfile variants (distroless, multi-arch) — Phase X+
- `testcontainers-python` — reconsider in Phase B+ if test parallelism demands it
- `factory-boy` / `model_bakery` factories — Phase B+ when business models exist
- `mermaid` diagrams in architecture.md — ASCII-only for Phase 3
- CORS middleware config — Phase 7+ when frontend `VITE_API_MODE=http` flips
- Permanent CI script for synthetic-violation check — Phase X+ if needed
- `scripts/restore_db.sh` — Phase X+ when there's actual data
- `docs/operations.md` / runbook — Phase X+ deploy concern
- uv `dev-dependencies` → PEP-735 `[dependency-groups]` migration — informational, non-blocking
